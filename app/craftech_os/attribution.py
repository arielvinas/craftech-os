"""Who made each change: the editors with Drive activity in the change's window.

A change happened in (window_start, window_end]. Google stamps a batch of edits a minute or
two after the edit, so the window looks at activity until MARGIN after window_end, and a change
is attributed only once activity past that moment has been read. Only actor ids are written;
names come from v_editor when shown.
"""

from collections import Counter
from datetime import datetime, timedelta

import psycopg

from craftech_os import events

MARGIN = timedelta(minutes=5)


def attribute(conn: psycopg.Connection, source_id: int, through: datetime) -> Counter:
    """Attribute the pending changes of one source, with activity read until through.

    Returns how many came out cierta, una_de and sin_datos.
    """
    rows = conn.execute(
        """
        WITH found AS (
            SELECT c.id, a.actors, a.last_at
            FROM cell_change c
            JOIN source_tab t ON t.id = c.source_tab_id
            CROSS JOIN LATERAL (
                SELECT coalesce(array_agg(DISTINCT d.actor_id ORDER BY d.actor_id), '{}') AS actors,
                       max(d.activity_at) AS last_at
                FROM drive_activity d
                WHERE d.source_id = t.source_id AND d.action_type = 'edit'
                  AND d.activity_at > c.window_start
                  AND d.activity_at <= c.window_end + %(margin)s
            ) a
            WHERE t.source_id = %(source_id)s AND c.attribution_certainty IS NULL
              AND c.window_end IS NOT NULL AND c.window_end + %(margin)s < %(through)s
        )
        UPDATE cell_change c
        SET attributed_editor_ids = f.actors,
            attribution_certainty = CASE cardinality(f.actors)
                WHEN 0 THEN 'sin_datos' WHEN 1 THEN 'cierta' ELSE 'una_de' END,
            attributed_at = CASE WHEN cardinality(f.actors) = 1 THEN f.last_at END
        FROM found f
        WHERE c.id = f.id
        RETURNING c.attribution_certainty
        """,
        {"margin": MARGIN, "source_id": source_id, "through": through},
    ).fetchall()
    counts = Counter(certainty for (certainty,) in rows)
    if counts:
        events.record(conn, "attributed", source_id=source_id, **counts)
    return counts
