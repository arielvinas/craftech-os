"""Store the changes between two snapshots of a tab and the problems seen in the new one.

Events carry identifiers and counts; cell values go only to cell_change.
"""

from collections import Counter

import psycopg

from craftech_os import events
from craftech_os.diff.compare import compare
from craftech_os.issues import detect

FIELDS = (
    "change_type",
    "block",
    "row_key",
    "row_ordinal",
    "cell_ref",
    "old_value",
    "new_value",
    "old_formula",
    "new_formula",
    "old_color",
    "new_color",
)


def _snapshot(conn: psycopg.Connection, snapshot_id: int):
    """(read_at, drive_modified_at, content) of a snapshot."""
    return conn.execute(
        "SELECT read_at, drive_modified_at, content FROM snapshot WHERE id = %s", (snapshot_id,)
    ).fetchone()


def changes(conn: psycopg.Connection, tab_id: int, from_id: int, to_id: int) -> dict:
    """The comparison of two snapshots of a tab, with the tab's schema. Writes nothing."""
    (schema,) = conn.execute("SELECT schema FROM source_tab WHERE id = %s", (tab_id,)).fetchone()
    return compare(_snapshot(conn, from_id)[2], _snapshot(conn, to_id)[2], schema)


def record(
    conn: psycopg.Connection, source_id: int, tab_id: int, from_id: int | None, to_id: int
) -> Counter:
    """Insert the changes from from_id (None: the first snapshot) to to_id and its problems.

    Call it in the transaction that stores to_id. Returns the count of changes per type.
    """
    (schema,) = conn.execute("SELECT schema FROM source_tab WHERE id = %s", (tab_id,)).fetchone()
    read_at, window_end, new_doc = _snapshot(conn, to_id)
    found, counts = [], Counter()
    if from_id is not None:
        _, window_start, old_doc = _snapshot(conn, from_id)
        result = compare(old_doc, new_doc, schema)
        if result["positional"]:
            events.record(
                conn,
                "schema_mismatch",
                source_id=source_id,
                source_tab_id=tab_id,
                to_snapshot=to_id,
            )
        with conn.cursor() as cur:
            cur.executemany(
                f"""
                INSERT INTO cell_change (source_tab_id, from_snapshot, to_snapshot,
                    {", ".join(FIELDS)}, detected_at, window_start, window_end)
                VALUES (%s, %s, %s, {", ".join(["%s"] * len(FIELDS))}, %s, %s, %s)
                """,
                [
                    (
                        tab_id,
                        from_id,
                        to_id,
                        *(c[f] for f in FIELDS),
                        read_at,
                        window_start,
                        window_end,
                    )
                    for c in result["changes"]
                ],
            )
        counts = Counter(c["change_type"] for c in result["changes"])
        found = [
            ("alineacion_ambigua", f"{block}:{key}", {"block": block, "to_snapshot": to_id})
            for block, key in result["ambiguous"]
        ]
    found += detect.find(new_doc, schema)
    for issue_type, key, details in found:
        detect.upsert(conn, issue_type, f"{tab_id}:{key}", source_id, tab_id, details)
    events.record(
        conn,
        "tab_diffed",
        source_id=source_id,
        source_tab_id=tab_id,
        from_snapshot=from_id,
        to_snapshot=to_id,
        changes=dict(sorted(counts.items())),
        issues=len(found),
    )
    return counts
