import json

import psycopg


def record(
    conn: psycopg.Connection,
    kind: str,
    *,
    source_id: int | None = None,
    source_tab_id: int | None = None,
    duration_ms: int | None = None,
    **details,
) -> None:
    """Insert a system_event. Details are identifiers and counts, never cell values."""
    conn.execute(
        "INSERT INTO system_event (kind, source_id, source_tab_id, duration_ms, details)"
        " VALUES (%s, %s, %s, %s, %s::jsonb)",
        (kind, source_id, source_tab_id, duration_ms, json.dumps(details, ensure_ascii=False)),
    )
