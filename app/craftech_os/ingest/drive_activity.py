"""Drive Activity of each source: who did what and when, as Google reports it.

Only opaque actor ids are stored (people/..., or deletedUser for any deleted account), never
names. Events carry identifiers and counts.
"""

import hashlib
import json
import time
from datetime import datetime, timedelta

import psycopg

from craftech_os import events
from craftech_os.ingest import importer
from craftech_os.ingest.google import Google

# Google publishes some activity late: a later fetch asks again for the last ten minutes.
OVERLAP = timedelta(minutes=10)


def parse(activity: dict) -> dict:
    """The columns of drive_activity for one activity as Google returns it."""
    actor = activity["actors"][0]
    user = actor.get("user")
    if user is None:
        actor_id = list(actor)[0]  # administrator, system, anonymous, impersonation
    elif "knownUser" in user:
        actor_id = user["knownUser"]["personName"]
    else:
        actor_id = list(user)[0]  # deletedUser, unknownUser
    at = activity.get("timestamp") or activity["timeRange"]["endTime"]
    canonical = json.dumps(activity, sort_keys=True, ensure_ascii=False)
    return {
        "activity_at": datetime.fromisoformat(at),
        "actor_id": actor_id,
        "action_type": list(activity["primaryActionDetail"])[0],
        "raw": canonical,
        "content_hash": hashlib.sha256(canonical.encode()).hexdigest(),
    }


def fetch(conn: psycopg.Connection, google: Google, source_id: int, drive_id: str, now):
    """Store the new activity of one source. Returns {inserted, through}, or None if it failed.

    The first fetch reads the whole history; later ones, from the latest activity of the last
    completed fetch minus OVERLAP. Everything is inserted at the end, oldest first, so a fetch
    that fails stores nothing and the next one asks again for the same range.
    """
    through = now()
    started = time.monotonic()
    last = conn.execute(
        "SELECT details->>'latest' FROM system_event WHERE kind = 'activity_read'"
        " AND source_id = %s ORDER BY id DESC LIMIT 1",
        (source_id,),
    ).fetchone()
    since = datetime.fromisoformat(last[0]) - OVERLAP if last and last[0] else None
    try:
        found = google.activities(drive_id, importer.retry_logger(conn, source_id), since)
        rows = sorted([parse(a) for a in found], key=lambda r: r["activity_at"])
    except (*importer.READ_ERRORS, KeyError, IndexError, ValueError) as e:
        events.record(conn, "activity_failed", source_id=source_id, **importer.error_details(e))
        return None
    inserted = 0
    with conn.transaction():
        for r in rows:
            inserted += conn.execute(
                "INSERT INTO drive_activity"
                " (source_id, activity_at, actor_id, action_type, raw, content_hash)"
                " VALUES (%s, %s, %s, %s, %s::jsonb, %s) ON CONFLICT (content_hash) DO NOTHING",
                (source_id, r["activity_at"], r["actor_id"], r["action_type"], r["raw"],
                 r["content_hash"]),
            ).rowcount  # fmt: skip
        (latest,) = conn.execute(
            "SELECT max(activity_at) FROM drive_activity WHERE source_id = %s", (source_id,)
        ).fetchone()
        events.record(
            conn,
            "activity_read",
            source_id=source_id,
            duration_ms=round((time.monotonic() - started) * 1000),
            inserted=inserted,
            through=through.isoformat(),
            latest=latest and latest.isoformat(),
        )
    return {"inserted": inserted, "through": through}
