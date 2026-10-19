"""The worker: every five minutes, read again the spreadsheets whose Drive version changed.

One process, one loop. Each tick serves the pending read requests, checks the Drive version
of every source, waits until a changed spreadsheet has had no edit for two minutes (ten at
most), and reads its CARGA and DERIVADA tabs: a snapshot is stored only where the hash changed.
After the tick, a pg_dump of the database once a day. Events and printed lines carry
identifiers and counts, never cell values.
"""

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from craftech_os import events
from craftech_os.ingest import importer
from craftech_os.ingest.google import Google

TICK_S = 300
POLL_S = 30
QUIET = timedelta(minutes=2)
CAP = timedelta(minutes=10)
READ_CLASSES = ("CARGA", "DERIVADA")
DUMP_HOUR = 3
DUMP_KEEP = 14
BACKUPS_DIR = Path("/backups")


class DumpFailed(Exception):
    pass


def _now() -> datetime:
    return datetime.now().astimezone()


def _known_versions(conn: psycopg.Connection) -> dict[int, str]:
    """The Drive version of each source at its last read with no failed tab."""
    rows = conn.execute(
        "SELECT DISTINCT ON (source_id) source_id, details->>'drive_version' FROM system_event"
        " WHERE kind = 'source_read' AND details ? 'drive_version' ORDER BY source_id, id DESC"
    ).fetchall()
    return dict(rows)


def _wait_until_quiet(conn, google, source_id, file_id, version, now, sleep) -> dict:
    """Poll modifiedTime every 30 s until two minutes pass without an edit, or ten minutes.

    Returns the last version seen.
    """
    started = now()
    capped = False
    while now() - datetime.fromisoformat(version["modifiedTime"]) < QUIET:
        if now() - started >= CAP:
            capped = True
            break
        sleep(POLL_S)
        version = google.version(file_id, importer.retry_logger(conn, source_id))
    waited_s = round((now() - started).total_seconds())
    events.record(conn, "calm_wait", source_id=source_id, waited_s=waited_s, capped=capped)
    return version


def tick(conn: psycopg.Connection, google: Google, now=_now, sleep=time.sleep) -> dict:
    """One pass over every source with a drive_id. Returns {checked, read, stored}."""
    started = now()
    known = _known_versions(conn)
    pending = dict(
        conn.execute("SELECT source_id, id FROM read_request WHERE served_at IS NULL").fetchall()
    )
    rows = conn.execute(
        "SELECT id, title, drive_id, default_class FROM source"
        " WHERE drive_id IS NOT NULL ORDER BY id"
    ).fetchall()
    counts = {"checked": 0, "read": 0, "stored": 0}
    # Requested sources go first: they are read without waiting. A request is served once
    # every tab was read; until then it stays pending and is retried next tick.
    for source_id, title, drive_id, default_class in sorted(
        rows, key=lambda r: r[0] not in pending
    ):
        counts["checked"] += 1
        requested = source_id in pending
        try:
            version = google.version(drive_id, importer.retry_logger(conn, source_id))
            changed = version["version"] != known.get(source_id)
            if changed:
                events.record(
                    conn,
                    "version_changed",
                    source_id=source_id,
                    old=known.get(source_id),
                    new=version["version"],
                )
                if not requested:
                    version = _wait_until_quiet(
                        conn, google, source_id, drive_id, version, now, sleep
                    )
        except (*importer.READ_ERRORS, KeyError, ValueError) as e:
            events.record(conn, "source_failed", source_id=source_id, **importer.error_details(e))
            continue
        if not (changed or requested):
            continue
        source = {"title": title, "drive_id": drive_id, "default_class": default_class}
        result = importer.import_source(conn, google, source, READ_CLASSES, version["version"])
        counts["read"] += 1
        counts["stored"] += result["stored"]
        if requested and not result["failed"]:
            conn.execute(
                "UPDATE read_request SET served_at = now(), snapshot_count = %s WHERE id = %s",
                (result["stored"], pending[source_id]),
            )
    duration_ms = round((now() - started).total_seconds() * 1000)
    events.record(conn, "worker_tick", duration_ms=duration_ms, **counts)
    print(
        f"{started:%Y-%m-%d %H:%M:%S} tick: checked {counts['checked']}, read {counts['read']},"
        f" stored {counts['stored']}, {duration_ms} ms",
        flush=True,
    )
    return counts


def _dumps(directory: Path) -> list[Path]:
    return sorted(directory.glob("craftech-os-*.dump"))


def dump_due(directory: Path, now: datetime) -> bool:
    """True if there is no dump from the last 24 hours, or none since today's 03:00."""
    dumps = _dumps(directory)
    if not dumps:
        return True
    last = datetime.fromtimestamp(max(p.stat().st_mtime for p in dumps)).astimezone()
    today_at_three = now.replace(hour=DUMP_HOUR, minute=0, second=0, microsecond=0)
    return now - last >= timedelta(days=1) or last < today_at_three <= now


def dump(conn: psycopg.Connection, url: str, directory: Path, now=_now) -> Path:
    """pg_dump the database to directory/craftech-os-YYYY-MM-DD.dump and keep the last 14."""
    started = time.monotonic()
    path = directory / f"craftech-os-{now():%Y-%m-%d}.dump"
    partial = directory / "craftech-os.partial"
    # The password goes in pg_dump's environment, not its command line (visible with ps).
    params = conninfo_to_dict(url)
    env = dict(os.environ)
    if "password" in params:
        env["PGPASSWORD"] = params.pop("password")
    dbname = make_conninfo(**params)
    try:
        subprocess.run(
            ["pg_dump", "--format=custom", "--file", str(partial), "--dbname", dbname],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        partial.replace(path)
        for old in _dumps(directory)[:-DUMP_KEEP]:
            old.unlink()
        size_bytes = path.stat().st_size
    except subprocess.CalledProcessError as e:
        # Only pg_dump's own last line is kept: it names the failure without the full output.
        lines = e.stderr.strip().splitlines()
        error = lines[-1] if lines else f"pg_dump exited with {e.returncode}"
        partial.unlink(missing_ok=True)
        events.record(conn, "dump_failed", error=error)
        raise DumpFailed(error) from None
    except OSError as e:
        partial.unlink(missing_ok=True)
        events.record(conn, "dump_failed", error=str(e))
        raise DumpFailed(str(e)) from e
    duration_ms = round((time.monotonic() - started) * 1000)
    events.record(conn, "dump", duration_ms=duration_ms, file=path.name, size_bytes=size_bytes)
    return path


def run(conn, google, url: str, backups: Path, now=_now, sleep=time.sleep) -> None:
    """Tick every five minutes, forever. An unexpected error ends the process."""
    while True:
        started = now()
        tick(conn, google, now, sleep)
        if dump_due(backups, now()):
            try:
                path = dump(conn, url, backups, now)
                print(f"dumped {path.name}", flush=True)
            except DumpFailed as e:
                print(f"dump failed: {e}", file=sys.stderr, flush=True)
        sleep(max(0, TICK_S - (now() - started).total_seconds()))
