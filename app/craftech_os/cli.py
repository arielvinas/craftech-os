import argparse
import os
import sys
from collections import Counter
from pathlib import Path

import psycopg
from googleapiclient.errors import HttpError

from craftech_os import attribution, events, migrate, sources, worker
from craftech_os.diff import store
from craftech_os.ingest import drive_activity, importer
from craftech_os.ingest.google import Google, GoogleError


def _connect() -> psycopg.Connection:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("error: DATABASE_URL is not set")
    try:
        return psycopg.connect(url, autocommit=True)
    except psycopg.ProgrammingError:
        raise SystemExit("error: DATABASE_URL is not a valid connection string") from None


def cmd_migrate(args) -> None:
    with _connect() as conn:
        applied = migrate.migrate(conn)
    print("\n".join(f"applied {name}" for name in applied) or "nothing to apply")


def cmd_sources_load(args) -> None:
    parsed = sources.parse(args.file.read_text(encoding="utf-8"))
    with _connect() as conn:
        sources.load(conn, parsed)
    tabs = sum(len(s["tabs"]) for s in parsed)
    print(f"loaded {len(parsed)} sources and {tabs} named tabs from {args.file}")


def cmd_sources_list(args) -> None:
    with _connect() as conn:
        rows = sources.summary(conn)
    for title, default_class, counts in rows:
        detail = ", ".join(f"{cls} {n}" for cls, n in counts.items())
        if default_class:
            detail = f"all tabs {default_class}" + (f"; {detail}" if detail else "")
        print(f"{title!r}: {detail}")
    print(f"{len(rows)} sources")


def cmd_sources_resolve(args) -> None:
    """Find each source without drive_id by its exact title and write the id in the file."""
    text = args.file.read_text(encoding="utf-8")
    pending = [s["title"] for s in sources.parse(text) if s["drive_id"] is None]
    google = Google.from_environment()
    with _connect() as conn:

        def on_retry(**details):
            events.record(conn, "api_retry", **details)

        found, errors = {}, []
        for title in pending:
            ids = google.find_spreadsheets(title, on_retry)
            if len(ids) == 1:
                found[title] = ids[0]
            else:
                errors.append(f"{title!r}: {len(ids)} spreadsheets with that exact name")
        if found:
            text = sources.with_drive_ids(text, found)
            args.file.write_text(text, encoding="utf-8")
            sources.load(conn, sources.parse(text))
    print(f"resolved {len(found)} of {len(pending)} sources without drive_id")
    if errors:
        raise sources.SourcesError("; ".join(errors))


def cmd_import(args) -> None:
    """Read every tab of every source (or of one) and store a snapshot of what changed."""
    parsed = sources.parse(args.file.read_text(encoding="utf-8"))
    chosen = [s for s in parsed if args.source in (None, s["title"])]
    if not chosen:
        raise sources.SourcesError(f"no source titled {args.source!r} in {args.file}")
    google = Google.from_environment()
    with _connect() as conn:
        sources.load(conn, parsed)
        results = [importer.import_source(conn, google, s) for s in chosen]
    for r in results:
        print(
            f"{r['title']!r}: {r['stored']} stored, {r['unchanged']} unchanged,"
            f" {r['failed']} failed"
        )
    timed = sorted(((ms, r["title"], tab) for r in results for tab, ms in r["tabs"]), reverse=True)
    print("slowest tabs:")
    for ms, title, tab in timed[:10]:
        print(f"  {ms} ms  {title!r} / {tab!r}")
    failed = sum(r["failed"] for r in results)
    if failed:
        raise importer.ImportFailed(f"{failed} reads failed: see system_event")


def cmd_drive_import(args) -> None:
    """Store the Drive activity of every source (or of one) and attribute the pending changes."""
    google = Google.from_environment()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, title, drive_id FROM source WHERE drive_id IS NOT NULL"
            " AND (%(title)s::text IS NULL OR title = %(title)s) ORDER BY id",
            {"title": args.source},
        ).fetchall()
        if not rows:
            raise sources.SourcesError(f"no source titled {args.source!r} with a drive_id")
        failed = 0
        for source_id, title, drive_id in rows:
            fetched = drive_activity.fetch(conn, google, source_id, drive_id, worker._now)
            if fetched is None:
                failed += 1
                print(f"{title!r}: failed")
                continue
            counts = attribution.attribute(conn, source_id, fetched["through"])
            detail = ", ".join(f"{c} {n}" for c, n in sorted(counts.items()))
            print(
                f"{title!r}: {fetched['inserted']} new activities,"
                f" {counts.total()} changes attributed" + (f": {detail}" if detail else "")
            )
    if failed:
        raise importer.ImportFailed(f"{failed} activity reads failed: see system_event")


def cmd_editors(args) -> None:
    """Each actor of the Drive activity: edits, spreadsheets, hours and dates (UTC)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT e.label, e.actor_id, count(*) FILTER (WHERE a.action_type = 'edit'),"
            " array_agg(DISTINCT s.title ORDER BY s.title),"
            " min(extract(hour FROM a.activity_at AT TIME ZONE 'UTC'))::int,"
            " max(extract(hour FROM a.activity_at AT TIME ZONE 'UTC'))::int,"
            " min(a.activity_at AT TIME ZONE 'UTC')::date,"
            " max(a.activity_at AT TIME ZONE 'UTC')::date"
            " FROM v_editor e JOIN drive_activity a USING (actor_id)"
            " JOIN source s ON s.id = a.source_id"
            " GROUP BY e.label, e.actor_id, e.number ORDER BY e.number NULLS LAST"
        ).fetchall()
    for label, actor_id, edits, titles, first_h, last_h, first, last in rows:
        print(
            f"{label}  {actor_id}  {edits} edits  {', '.join(map(repr, titles))}"
            f"  {first_h}-{last_h} h UTC  {first}..{last}"
        )
    print(f"{len(rows)} editors")


def cmd_read_now(args) -> None:
    """Ask the worker to read this spreadsheet on its next tick, without the calm wait."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, drive_id FROM source WHERE title = %s", (args.title,)
        ).fetchone()
        if row is None:
            raise sources.SourcesError(f"no source titled {args.title!r}")
        if row[1] is None:
            raise sources.SourcesError(f"{args.title!r} has no drive_id")
        inserted = conn.execute(
            "INSERT INTO read_request (source_id, requested_by) VALUES (%s, 'cli')"
            " ON CONFLICT DO NOTHING",
            (row[0],),
        ).rowcount
    print("read requested" if inserted else "already pending")


def cmd_diff(args) -> None:
    """Recompute the changes between two snapshots of a tab and print counts. Writes nothing."""
    title, name = args.tab
    with _connect() as conn:
        row = conn.execute(
            "SELECT t.id FROM source_tab t JOIN source s ON s.id = t.source_id"
            " WHERE s.title = %s AND t.name = %s",
            (title, name),
        ).fetchone()
        if row is None:
            raise sources.SourcesError(f"no tab {name!r} in {title!r}")
        (tab_id,) = row
        to_id = (
            args.to_id
            or conn.execute(
                "SELECT max(id) FROM snapshot WHERE source_tab_id = %s", (tab_id,)
            ).fetchone()[0]
        )
        from_id = (
            args.from_id
            or conn.execute(
                "SELECT max(id) FROM snapshot WHERE source_tab_id = %s AND id < %s", (tab_id, to_id)
            ).fetchone()[0]
        )
        if from_id is None or to_id is None:
            raise sources.SourcesError(f"{name!r} in {title!r} has fewer than two snapshots")
        mine = {
            r[0]
            for r in conn.execute(
                "SELECT id FROM snapshot WHERE source_tab_id = %s AND id IN (%s, %s)",
                (tab_id, from_id, to_id),
            )
        }
        if mine != {from_id, to_id}:
            raise sources.SourcesError(f"snapshots {from_id} and {to_id} are not both of {name!r}")
        result = store.changes(conn, tab_id, from_id, to_id)
    counts = Counter(c["change_type"] for c in result["changes"])
    print(
        f"snapshots {from_id} -> {to_id}"
        + (" (by position: schema not found)" if result["positional"] else "")
    )
    for change_type, n in sorted(counts.items()):
        print(f"  {change_type} {n}")
    print(f"{sum(counts.values())} changes, ambiguous {len(result['ambiguous'])}")


def cmd_worker(args) -> None:
    google = Google.from_environment()
    with _connect() as conn:
        worker.run(conn, google, os.environ["DATABASE_URL"], args.dir)


def cmd_dump(args) -> None:
    with _connect() as conn:
        path = worker.dump(conn, os.environ["DATABASE_URL"], args.dir)
    print(f"dumped {path}")


def cmd_web(args) -> None:
    import uvicorn

    uvicorn.run("craftech_os.web.app:app", host=args.host, port=args.port)


def cmd_mcp(args) -> None:
    from craftech_os.mcp import server

    server.main()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="craftech-os")
    commands = parser.add_subparsers(required=True)
    commands.add_parser("migrate", help="apply pending SQL migrations").set_defaults(
        func=cmd_migrate
    )
    sources_cmd = commands.add_parser("sources", help="spreadsheets and tabs from sources.yaml")
    sources_sub = sources_cmd.add_subparsers(required=True)
    load_cmd = sources_sub.add_parser("load", help="load config/sources.yaml into the database")
    load_cmd.add_argument("--file", type=Path, default=sources.SOURCES_FILE)
    load_cmd.set_defaults(func=cmd_sources_load)
    sources_sub.add_parser("list", help="sources with active tab counts per class").set_defaults(
        func=cmd_sources_list
    )
    resolve_cmd = sources_sub.add_parser(
        "resolve", help="find the Drive id of each source by its exact title"
    )
    resolve_cmd.add_argument("--file", type=Path, default=sources.SOURCES_FILE)
    resolve_cmd.set_defaults(func=cmd_sources_resolve)
    import_cmd = commands.add_parser("import", help="read every tab and store snapshots")
    import_cmd.add_argument("--source", help="only the spreadsheet with this exact title")
    import_cmd.add_argument("--file", type=Path, default=sources.SOURCES_FILE)
    import_cmd.set_defaults(func=cmd_import)
    drive_cmd = commands.add_parser("drive", help="Drive activity: who edited and when")
    drive_sub = drive_cmd.add_subparsers(required=True)
    drive_import_cmd = drive_sub.add_parser(
        "import", help="store the Drive activity of every source and attribute the changes"
    )
    drive_import_cmd.add_argument("--source", help="only the spreadsheet with this exact title")
    drive_import_cmd.set_defaults(func=cmd_drive_import)
    commands.add_parser(
        "editors", help="actors of the Drive activity, to tell who is who (read-only)"
    ).set_defaults(func=cmd_editors)
    read_now_cmd = commands.add_parser(
        "read-now", help="ask the worker to read a spreadsheet on its next tick"
    )
    read_now_cmd.add_argument("title", help="the exact title in sources.yaml")
    read_now_cmd.set_defaults(func=cmd_read_now)
    diff_cmd = commands.add_parser(
        "diff", help="recompute the changes between two snapshots of a tab (counts only)"
    )
    diff_cmd.add_argument(
        "--tab", nargs=2, required=True, metavar=("SPREADSHEET", "TAB"), help="exact names"
    )
    diff_cmd.add_argument("--from", dest="from_id", type=int, help="default: the one before --to")
    diff_cmd.add_argument("--to", dest="to_id", type=int, help="default: the latest snapshot")
    diff_cmd.set_defaults(func=cmd_diff)
    worker_cmd = commands.add_parser("worker", help="read changed spreadsheets every five minutes")
    worker_cmd.add_argument("--dir", type=Path, default=worker.BACKUPS_DIR, help="for the dumps")
    worker_cmd.set_defaults(func=cmd_worker)
    dump_cmd = commands.add_parser("dump", help="pg_dump the database now")
    dump_cmd.add_argument("--dir", type=Path, default=worker.BACKUPS_DIR)
    dump_cmd.set_defaults(func=cmd_dump)
    web_cmd = commands.add_parser(
        "web", help="serve the read-only screens Cambios, Problemas, Fuentes"
    )
    web_cmd.add_argument("--host", default="127.0.0.1", help="0.0.0.0 inside the container")
    web_cmd.add_argument("--port", type=int, default=8000)
    web_cmd.set_defaults(func=cmd_web)
    commands.add_parser(
        "mcp", help="serve the MCP server for Claude Desktop over stdio"
    ).set_defaults(func=cmd_mcp)
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (
        migrate.MigrationError,
        sources.SourcesError,
        importer.ImportFailed,
        worker.DumpFailed,
        GoogleError,
        psycopg.OperationalError,
        OSError,
    ) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except HttpError as e:
        # The message may quote the request; the status is enough.
        print(f"error: Google answered {e.resp.status}", file=sys.stderr)
        return 1
    return 0
