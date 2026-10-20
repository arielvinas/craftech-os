"""The SQL behind each screen. Parameters are always bound; filters arrive already validated."""

from datetime import timedelta

import psycopg
from psycopg.rows import dict_row

PAGE_SIZE = 100
NOT_ATTRIBUTED = "sin_atribuir"

CHANGE_FROM = """
FROM cell_change c
JOIN source_tab t ON t.id = c.source_tab_id
JOIN source s ON s.id = t.source_id
"""


def _change_where(f: dict) -> tuple[str, list]:
    """WHERE clause for the Cambios filters (each one optional)."""
    clauses, params = [], []
    if f["planilla"] is not None:
        clauses.append("s.id = %s")
        params.append(f["planilla"])
    if f["pestana"] is not None:
        clauses.append("t.id = %s")
        params.append(f["pestana"])
    if f["tipo"] is not None:
        clauses.append("c.change_type = %s")
        params.append(f["tipo"])
    if f["clave"]:
        clauses.append("c.row_key ILIKE %s")
        escaped = f["clave"].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params.append(f"%{escaped}%")
    if f["editor"] == NOT_ATTRIBUTED:
        clauses.append("coalesce(cardinality(c.attributed_editor_ids), 0) = 0")
    elif f["editor"]:
        clauses.append("%s = ANY(c.attributed_editor_ids)")
        params.append(f["editor"])
    if f["desde"] is not None:
        clauses.append("c.detected_at >= %s::date")
        params.append(f["desde"])
    if f["hasta"] is not None:
        clauses.append("c.detected_at < %s::date")
        params.append(f["hasta"] + timedelta(days=1))
    if f["snapshot"] is not None:
        clauses.append("%s IN (c.from_snapshot, c.to_snapshot)")
        params.append(f["snapshot"])
    return ("WHERE " + " AND ".join(clauses)) if clauses else "", params


def changes(conn: psycopg.Connection, f: dict, page: int) -> list[dict]:
    """One page of changes, newest first, plus one row to tell whether there is a next page."""
    where, params = _change_where(f)
    sql = f"""
        SELECT c.*, s.title AS source_title, t.name AS tab_name
        {CHANGE_FROM} {where}
        ORDER BY c.detected_at DESC, c.id DESC
        LIMIT %s OFFSET %s
    """
    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(sql, [*params, PAGE_SIZE + 1, (page - 1) * PAGE_SIZE]).fetchall()


def change_summary(conn: psycopg.Connection, f: dict) -> dict:
    """Changes of the filtered period by day and by type."""
    where, params = _change_where(f)
    by_day = conn.execute(
        f"SELECT c.detected_at::date, count(*) {CHANGE_FROM} {where} GROUP BY 1 ORDER BY 1 DESC",
        params,
    ).fetchall()
    by_type = conn.execute(
        f"SELECT c.change_type, count(*) {CHANGE_FROM} {where} GROUP BY 1 ORDER BY 2 DESC, 1",
        params,
    ).fetchall()
    return {"by_day": by_day, "by_type": by_type, "total": sum(n for _, n in by_type)}


def change(conn: psycopg.Connection, change_id: int) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(
            f"SELECT c.*, s.title AS source_title, t.name AS tab_name {CHANGE_FROM}"
            " WHERE c.id = %s",
            (change_id,),
        ).fetchone()


def editor_ids(conn: psycopg.Connection) -> list[str]:
    """Every editor identifier seen in a change, for the editor filter."""
    rows = conn.execute(
        "SELECT DISTINCT unnest(attributed_editor_ids) FROM cell_change ORDER BY 1"
    ).fetchall()
    return [r[0] for r in rows]


def editor_names(conn: psycopg.Connection) -> dict[str, str]:
    """The person associated with each editor identifier. The latest row per actor_id wins."""
    rows = conn.execute(
        "SELECT DISTINCT ON (actor_id) actor_id, person_name FROM editor_profile"
        " ORDER BY actor_id, created_at DESC, id DESC"
    ).fetchall()
    return dict(rows)


def sources(conn: psycopg.Connection) -> list[tuple[int, str]]:
    return conn.execute("SELECT id, title FROM source ORDER BY title").fetchall()


def tabs(conn: psycopg.Connection) -> list[tuple[int, str, str]]:
    return conn.execute(
        "SELECT t.id, s.title, t.name FROM source_tab t JOIN source s ON s.id = t.source_id"
        " ORDER BY s.title, t.name"
    ).fetchall()


ISSUE_FROM = """
FROM v_issue i
JOIN source s ON s.id = i.source_id
LEFT JOIN source_tab t ON t.id = i.source_tab_id
"""


def issues(conn: psycopg.Connection, f: dict) -> list[dict]:
    clauses, params = [], []
    for column, key in (("i.issue_type", "tipo"), ("i.status", "estado"), ("s.id", "planilla")):
        if f[key] is not None:
            clauses.append(f"{column} = %s")
            params.append(f[key])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(
            f"SELECT i.*, s.title AS source_title, t.name AS tab_name {ISSUE_FROM} {where}"
            " ORDER BY i.last_seen_at DESC, i.id DESC",
            params,
        ).fetchall()


def issue(conn: psycopg.Connection, issue_id: int) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        found = cur.execute(
            f"SELECT i.*, s.title AS source_title, t.name AS tab_name {ISSUE_FROM} WHERE i.id = %s",
            (issue_id,),
        ).fetchone()
        if found is not None:
            found["resolutions"] = cur.execute(
                "SELECT action, author, reason, created_at FROM issue_resolution"
                " WHERE issue_id = %s ORDER BY created_at DESC, id DESC",
                (issue_id,),
            ).fetchall()
        return found


def health(conn: psycopg.Connection) -> dict:
    """System health from system_event: worker ticks, the last dump, retries, database size."""
    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(
            """
            WITH ticks AS (
                SELECT occurred_at, occurred_at - lag(occurred_at) OVER (ORDER BY occurred_at)
                    AS gap
                FROM system_event WHERE kind = 'worker_tick'
            )
            SELECT
                (SELECT max(occurred_at) FROM ticks) AS last_tick,
                (SELECT max(gap) FROM ticks WHERE occurred_at > now() - interval '24 hours')
                    AS max_gap,
                d.occurred_at AS last_dump,
                (d.details->>'size_bytes')::bigint AS dump_bytes,
                d.occurred_at IS NULL OR d.occurred_at < now() - interval '48 hours'
                    AS dump_stale,
                pg_database_size(current_database()) AS db_bytes,
                (SELECT count(*) FROM system_event
                 WHERE kind = 'api_retry' AND occurred_at >= current_date) AS retries_today
            FROM (SELECT 1) one
            LEFT JOIN LATERAL (
                SELECT occurred_at, details FROM system_event WHERE kind = 'dump'
                ORDER BY occurred_at DESC, id DESC LIMIT 1
            ) d ON true
            """
        ).fetchone()


def source_rows(conn: psycopg.Connection) -> list[dict]:
    """Each source with its known Drive version, last worker check and pending read request."""
    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(
            """
            SELECT s.id, s.title, s.drive_id, s.default_class,
                v.drive_version,
                -- Every tick checks every source that has a drive_id.
                CASE WHEN s.drive_id IS NOT NULL THEN
                    (SELECT max(occurred_at) FROM system_event WHERE kind = 'worker_tick')
                END AS last_check,
                r.requested_at AS pending_since
            FROM source s
            LEFT JOIN LATERAL (
                SELECT details->>'drive_version' AS drive_version FROM system_event
                WHERE kind = 'source_read' AND source_id = s.id AND details ? 'drive_version'
                ORDER BY id DESC LIMIT 1
            ) v ON true
            LEFT JOIN read_request r ON r.source_id = s.id AND r.served_at IS NULL
            ORDER BY s.title
            """
        ).fetchall()


def tab_rows(conn: psycopg.Connection) -> list[dict]:
    """Each tab with its last snapshot, snapshot count and changes of the last 24 hours."""
    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(
            """
            SELECT t.id, t.source_id, t.name, t.class, t.sheet_id, t.active,
                last.read_at AS last_read_at, last.duration_ms AS last_duration_ms,
                (SELECT count(*) FROM snapshot WHERE source_tab_id = t.id) AS snapshots,
                (SELECT count(*) FROM cell_change WHERE source_tab_id = t.id
                 AND detected_at > now() - interval '24 hours') AS changes_24h
            FROM source_tab t
            LEFT JOIN LATERAL (
                SELECT read_at, duration_ms FROM snapshot WHERE source_tab_id = t.id
                ORDER BY read_at DESC, id DESC LIMIT 1
            ) last ON true
            ORDER BY t.source_id, t.active DESC, t.name
            """
        ).fetchall()


def request_read(conn: psycopg.Connection, source_id: int) -> str | None:
    """Insert a read_request unless one is pending (same rule as the read-now command).

    Returns created, pending or no_drive_id; None if the source does not exist.
    """
    row = conn.execute("SELECT drive_id FROM source WHERE id = %s", (source_id,)).fetchone()
    if row is None:
        return None
    if row[0] is None:
        return "no_drive_id"
    inserted = conn.execute(
        "INSERT INTO read_request (source_id, requested_by) VALUES (%s, 'web')"
        " ON CONFLICT DO NOTHING",
        (source_id,),
    ).rowcount
    return "created" if inserted else "pending"


def invoice_months(conn: psycopg.Connection) -> list:
    return [r[0] for r in conn.execute("SELECT DISTINCT mes FROM mcp.facturas ORDER BY 1 DESC")]


def clients(conn: psycopg.Connection) -> list[tuple[int, str]]:
    return conn.execute("SELECT id, nombre FROM mcp.clientes ORDER BY nombre").fetchall()


def invoices(conn: psycopg.Connection, f: dict) -> list[dict]:
    """The month's invoices with their razón social, payment and source cell."""
    clauses, params = ["f.mes = %s"], [f["mes"]]
    for column, key in (("f.estado", "estado"), ("f.entidad_legal", "entidad"),
                        ("f.cliente_id", "cliente")):  # fmt: skip
        if f[key] is not None:
            clauses.append(f"{column} = %s")
            params.append(f[key])
    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(
            f"""
            SELECT f.*, c.fecha AS cobro_fecha, c.certeza AS cobro_certeza,
                c.origen_fecha AS cobro_origen, s.drive_id, t.sheet_id,
                (SELECT string_agg(r.razon_social, ', ' ORDER BY r.razon_social)
                 FROM mcp.razones_sociales r
                 WHERE r.cliente_id = f.cliente_id AND r.sociedad_craftech = f.entidad_legal)
                    AS razon_social
            FROM mcp.facturas f
            JOIN source_tab t ON t.id = f.pestaña_id
            JOIN source s ON s.id = t.source_id
            LEFT JOIN mcp.cobros c ON c.pestaña_id = f.pestaña_id
                AND c.lectura_id = f.lectura_id AND c.celda = f.celda
            WHERE {" AND ".join(clauses)}
            ORDER BY f.planilla, f.pestaña, f.cliente NULLS LAST, f.clave_fila, f.serie
            """,
            params,
        ).fetchall()


def invoice_parity(conn: psycopg.Connection, month) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(
            "SELECT * FROM mcp.paridad_pagos WHERE mes = %s ORDER BY planilla, pestaña", (month,)
        ).fetchall()


def fundings(conn: psycopg.Connection) -> list[dict]:
    """Every milestone, marked when an open funding_duplicado problem names its cell."""
    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(
            """
            SELECT f.*, s.drive_id, t.sheet_id,
                (SELECT min(i.id) FROM v_issue i
                 WHERE i.issue_type = 'funding_duplicado'
                   AND i.status IN ('abierto', 'reabierto')
                   AND jsonb_build_object('planilla', f.planilla, 'pestaña', f.pestaña,
                                          'cell_ref', f.celda)
                       IN (i.details -> 'tracker', i.details -> 'pagos')) AS duplicado_id
            FROM mcp.fundings f
            JOIN source_tab t ON t.id = f.pestaña_id
            JOIN source s ON s.id = t.source_id
            ORDER BY f.cliente NULLS LAST, f.programa NULLS LAST, f.orden_en_programa,
                f.origen, f.planilla, f.celda
            """
        ).fetchall()


def funding_parity(conn: psycopg.Connection) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(
            "SELECT * FROM mcp.paridad_fundings ORDER BY mes DESC, planilla, unidad_negocio"
        ).fetchall()


def client_rows(conn: psycopg.Connection) -> list[dict]:
    """Each client with its razones sociales and its current aliases."""
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute("SELECT id, nombre, hubspot_id FROM mcp.clientes ORDER BY nombre")
        found = {r["id"]: {**r, "razones": [], "aliases": []} for r in rows.fetchall()}
        for r in cur.execute(
            "SELECT * FROM mcp.razones_sociales ORDER BY razon_social, id"
        ).fetchall():
            found[r["cliente_id"]]["razones"].append(r)
        for a in cur.execute("SELECT * FROM mcp.aliases ORDER BY fuente, texto").fetchall():
            found[a["cliente_id"]]["aliases"].append(a)
    return list(found.values())


def rows_without_client(conn: psycopg.Connection) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        return cur.execute(
            f"SELECT i.*, s.title AS source_title, t.name AS tab_name {ISSUE_FROM}"
            " WHERE i.issue_type = 'alias_sin_cliente' AND i.status IN ('abierto', 'reabierto')"
            " ORDER BY s.title, t.name, i.details ->> 'text', i.id"
        ).fetchall()
