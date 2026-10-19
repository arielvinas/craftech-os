"""Initial import: one snapshot per tab of every source, skipped when the content is unchanged.

Events and printed lines carry identifiers and counts, never cell values.
"""

import time

import httplib2
import psycopg
from googleapiclient.errors import HttpError

from craftech_os import events
from craftech_os.ingest import document
from craftech_os.ingest.google import Google, GoogleError, status

UNCLASSIFIED = "SIN_CLASIFICAR"
READ_ERRORS = (
    HttpError,
    GoogleError,
    OSError,
    httplib2.HttpLib2Error,
    httplib2.decode.DecodeRatioError,
    httplib2.decode.DecodeLimitError,
)


class ImportFailed(Exception):
    pass


def error_details(e: Exception) -> dict:
    details = {"error": type(e).__name__}
    if isinstance(e, HttpError):
        details["status"] = status(e)
    return details


def retry_logger(conn, source_id, source_tab_id=None):
    def on_retry(**details):
        events.record(
            conn, "api_retry", source_id=source_id, source_tab_id=source_tab_id, **details
        )

    return on_retry


def register_tabs(
    conn: psycopg.Connection, source_id: int, default_class: str | None, google_tabs: list[dict]
) -> list[tuple[int, str]]:
    """Match Google's tabs with source_tab (by sheet_id, else by name) and store their sheet_id.

    A Google tab with no active row is registered with the source's all_tabs class, or
    SIN_CLASIFICAR. An active row Google no longer has becomes inactive.
    Returns (source_tab_id, Google title) of every tab Google has, in Google's order.
    """
    rows = conn.execute(
        "SELECT id, sheet_id, name, active FROM source_tab WHERE source_id = %s", (source_id,)
    ).fetchall()
    google_ids = {props["sheetId"] for props in google_tabs}
    by_sheet = {r[1]: r for r in rows if r[1] is not None}
    # A row whose sheet_id Google no longer has (the tab was recreated) matches by name too.
    by_name = {r[2]: r for r in rows if r[1] is None or r[1] not in google_ids}
    found = []
    for props in google_tabs:
        sheet_id, title = props["sheetId"], props["title"]
        row, named = by_sheet.get(sheet_id), by_name.get(title)
        if named is not None and named[3] and (row is None or not row[3]):
            # The tab was renamed in sources.yaml: the active row with the new name wins.
            if row is not None:
                conn.execute("UPDATE source_tab SET sheet_id = NULL WHERE id = %s", (row[0],))
            row = named
        cls = default_class or UNCLASSIFIED
        if row is None:
            (tab_id,) = conn.execute(
                "INSERT INTO source_tab (source_id, sheet_id, name, class)"
                " VALUES (%s, %s, %s, %s) RETURNING id",
                (source_id, sheet_id, title, cls),
            ).fetchone()
        elif not row[3]:
            tab_id = row[0]
            conn.execute(
                "UPDATE source_tab SET sheet_id = %s, class = %s, active = true WHERE id = %s",
                (sheet_id, cls, tab_id),
            )
        else:
            tab_id, cls = row[0], None
            conn.execute("UPDATE source_tab SET sheet_id = %s WHERE id = %s", (sheet_id, tab_id))
        if cls == UNCLASSIFIED:
            events.record(
                conn, "tab_unclassified", source_id=source_id, source_tab_id=tab_id, tab=title
            )
        found.append((tab_id, title))
    found_ids = {tab_id for tab_id, _ in found}
    for tab_id, _, name, active in rows:
        if active and tab_id not in found_ids:
            conn.execute("UPDATE source_tab SET active = false WHERE id = %s", (tab_id,))
            events.record(conn, "tab_missing", source_id=source_id, source_tab_id=tab_id, tab=name)
    return found


def read_tab(
    conn: psycopg.Connection, google: Google, source_id: int, tab_id: int, file_id: str, title: str
) -> dict | None:
    """Read one tab and store a snapshot if its hash differs from the last one.

    Returns {duration_ms, stored}, or None if the read failed (a tab_failed event says why).
    """
    started = time.monotonic()
    on_retry = retry_logger(conn, source_id, tab_id)
    try:
        version = google.version(file_id, on_retry)
        drive_version, drive_modified_at = int(version["version"]), version["modifiedTime"]
        grid = google.grid(file_id, title, on_retry)
        doc = document.build(grid)
        serialized = document.canonical(doc)
    except (*READ_ERRORS, KeyError, ValueError, TypeError) as e:
        events.record(
            conn, "tab_failed", source_id=source_id, source_tab_id=tab_id, **error_details(e)
        )
        return None
    duration_ms = round((time.monotonic() - started) * 1000)
    content_hash = document.content_hash(serialized)
    last = conn.execute(
        "SELECT content_hash FROM snapshot WHERE source_tab_id = %s"
        " ORDER BY read_at DESC, id DESC LIMIT 1",
        (tab_id,),
    ).fetchone()
    stored = last != (content_hash,)
    cells = document.cell_count(doc)
    if stored:
        try:
            conn.execute(
                """
                INSERT INTO snapshot (source_tab_id, drive_version, drive_modified_at,
                    duration_ms, origin, content_hash, content, row_count, col_count, cell_count)
                VALUES (%s, %s, %s, %s, 'lectura', %s, %s::jsonb, %s, %s, %s)
                """,
                (
                    tab_id,
                    drive_version,
                    drive_modified_at,
                    duration_ms,
                    content_hash,
                    serialized,
                    doc["used"]["rows"],
                    doc["used"]["cols"],
                    cells,
                ),
            )
        except psycopg.DataError as e:
            events.record(
                conn, "tab_failed", source_id=source_id, source_tab_id=tab_id, **error_details(e)
            )
            return None
    events.record(
        conn,
        "tab_read",
        source_id=source_id,
        source_tab_id=tab_id,
        duration_ms=duration_ms,
        cell_count=cells,
        stored=stored,
    )
    return {"duration_ms": duration_ms, "stored": stored}


def import_source(
    conn: psycopg.Connection,
    google: Google,
    source: dict,
    classes: tuple[str, ...] | None = None,
    drive_version: str | None = None,
) -> dict:
    """Read every tab of one source, or only its tabs of these classes.

    Returns counts and the duration of each tab read. drive_version, when given, is recorded
    in source_read if every tab was read: the worker reads it back as the version it has.
    """
    (source_id,) = conn.execute(
        "SELECT id FROM source WHERE title = %s", (source["title"],)
    ).fetchone()
    result = {"title": source["title"], "stored": 0, "unchanged": 0, "failed": 0, "tabs": []}
    if source["drive_id"] is None:
        events.record(conn, "source_failed", source_id=source_id, error="drive_id missing")
        result["failed"] = 1
        return result
    started = time.monotonic()
    try:
        google_tabs = google.tabs(source["drive_id"], retry_logger(conn, source_id))
    except READ_ERRORS as e:
        events.record(conn, "source_failed", source_id=source_id, **error_details(e))
        result["failed"] = 1
        return result
    found = register_tabs(conn, source_id, source["default_class"], google_tabs)
    if classes is not None:
        wanted = {
            tab_id
            for (tab_id,) in conn.execute(
                "SELECT id FROM source_tab WHERE source_id = %s AND class = ANY(%s)",
                (source_id, list(classes)),
            )
        }
        found = [(tab_id, title) for tab_id, title in found if tab_id in wanted]
    for tab_id, title in found:
        read = read_tab(conn, google, source_id, tab_id, source["drive_id"], title)
        if read is None:
            result["failed"] += 1
            continue
        result["stored" if read["stored"] else "unchanged"] += 1
        result["tabs"].append((title, read["duration_ms"]))
    events.record(
        conn,
        "source_read",
        source_id=source_id,
        duration_ms=round((time.monotonic() - started) * 1000),
        stored=result["stored"],
        unchanged=result["unchanged"],
        failed=result["failed"],
        **({"drive_version": drive_version} if drive_version and not result["failed"] else {}),
    )
    return result
