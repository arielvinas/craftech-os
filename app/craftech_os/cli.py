import argparse
import os
import sys
from pathlib import Path

import psycopg

from craftech_os import migrate, sources


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
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (migrate.MigrationError, sources.SourcesError, psycopg.OperationalError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0
