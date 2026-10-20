"""Facts of the last read of a tab (ADR-002): accruals from VENTAS; invoices, payments, churn,
totals and funding milestones from Pagos; the same plus exchange rates from Pagos ARG; funding
milestones from the FUNDINGS tracker.

Each tab with an interpreter has its facts replaced as a whole on every new read. Facts carry
no client: the views resolve it through client_alias, so loading an alias needs no rerun.
Events and problem details carry identifiers and counts, never amounts.
"""

import time

import psycopg

from craftech_os import clients, events
from craftech_os.interpret import fundings, pagos, ventas
from craftech_os.issues import detect

RULES_VERSION = "v0.9"
INTERPRETERS = {
    "VENTAS": lambda doc, schema, title: ventas.interpret(doc, schema),
    "Pagos": pagos.interpret,
    "Pagos ARG": pagos.interpret_arg,
    "FUNDINGS": fundings.interpret,
}
COLUMNS = {
    "accrual": (
        "block",
        "row_key",
        "series_order",
        "month",
        "amount_usd",
        "business_unit",
        "pod",
        "alias_source",
        "alias_text",
        "cell_ref",
    ),
    "fx_rate": ("rate_type", "month", "value", "type_to_confirm", "cell_ref"),
    "invoice": (
        "block",
        "row_key",
        "series_order",
        "month",
        "legal_entity",
        "state",
        "amount",
        "currency",
        "net_ars",
        "fx_rate",
        "fx_rate_type",
        "fx_rate_to_confirm",
        "inferred_usd",
        "sent_change_id",
        "alias_source",
        "alias_text",
        "cell_ref",
    ),
    "payment": ("block", "row_key", "series_order", "month", "legal_entity", "cell_change_id"),
    "client_churn": (
        "block",
        "row_key",
        "series_order",
        "month",
        "color",
        "color_to_confirm",
        "alias_source",
        "alias_text",
        "cell_ref",
    ),
    "payment_total": ("row_key", "month", "amount", "cell_ref"),
    "funding_milestone": (
        "origin",
        "block",
        "row_key",
        "program",
        "opportunity",
        "fund_claim_id",
        "program_order",
        "provisional_key",
        "month",
        "amount_usd",
        "status",
        "business_unit",
        "load_date",
        "estimated_signoff",
        "estimated_collection",
        "invoice_loaded",
        "paid_on",
        "alias_source",
        "alias_text",
        "cell_ref",
    ),
}
# Rule R28: a funding in the tracker and in Pagos is kept on both sides and reported. Pagos has
# no opportunity column, so the same funding is the same amount for the same client: the same
# text, or texts whose aliases point to the same client.
DUPLICATES = """
    WITH m AS (
        SELECT f.*, t.name AS tab, s.title, t.source_id,
               (SELECT x.client_id FROM client_alias x
                WHERE x.source = f.alias_source AND x.text = f.alias_text
                ORDER BY x.created_at DESC, x.id DESC LIMIT 1) AS client_id
        FROM funding_milestone f
        JOIN source_tab t ON t.id = f.source_tab_id AND t.active
        JOIN source s ON s.id = t.source_id
    )
    SELECT k.source_id, k.source_tab_id, k.row_key, k.title, k.tab, k.cell_ref,
           p.source_tab_id, p.block, p.row_key, p.month, p.title, p.tab, p.cell_ref
    FROM m k JOIN m p ON k.origin = 'tracker' AND p.origin = 'pagos'
        AND k.amount_usd = p.amount_usd
        AND (k.alias_text = p.alias_text OR k.client_id = p.client_id)
    WHERE %s IN (k.source_tab_id, p.source_tab_id)
    ORDER BY k.source_tab_id, k.cell_ref, p.source_tab_id, p.cell_ref
"""


def run(conn: psycopg.Connection, snapshot_id: int) -> dict | None:
    """Replace the facts of the tab of this snapshot with the ones in it.

    Returns the counts, or None if the tab has no interpreter (nothing is touched then).
    """
    started = time.monotonic()
    tab_id, source_id, name, tab_class, schema, title, doc = conn.execute(
        """
        SELECT t.id, t.source_id, t.name, t.class, t.schema, s.title, n.content
        FROM snapshot n JOIN source_tab t ON t.id = n.source_tab_id
        JOIN source s ON s.id = t.source_id
        WHERE n.id = %s
        """,
        (snapshot_id,),
    ).fetchone()
    interpret = INTERPRETERS.get(name)
    if interpret is None or tab_class != "CARGA" or not schema:
        return None
    facts, issues = interpret(doc, schema, title)
    source = f"{title} / {name}"
    alias_source = clients.alias_source(source)
    for table in ("accrual", "invoice", "client_churn", "funding_milestone"):
        for fact in facts.get(table, []):
            fact["alias_source"] = alias_source
    with conn.transaction():
        if "invoice" in facts:
            pagos.link(conn, tab_id, snapshot_id, facts)
        counts = {}
        for table, columns in COLUMNS.items():
            conn.execute(f"DELETE FROM {table} WHERE source_tab_id = %s", (tab_id,))
            rows = facts.get(table, [])
            with conn.cursor() as cur:
                cur.executemany(
                    f"""
                    INSERT INTO {table} (source_tab_id, snapshot_id, rules_version,
                        {", ".join(columns)})
                    VALUES (%s, %s, %s, {", ".join(["%s"] * len(columns))})
                    """,
                    [(tab_id, snapshot_id, RULES_VERSION, *(r[c] for c in columns)) for r in rows],
                )
            counts[table] = len(rows)
        known = {
            text
            for (text,) in conn.execute(
                "SELECT DISTINCT text FROM client_alias WHERE source = %s", (alias_source,)
            )
        }
        texts = {a["alias_text"] for a in facts.get("accrual", []) if a["amount_usd"]}
        texts |= {i["alias_text"] for i in facts.get("invoice", [])}
        texts |= {f["alias_text"] for f in facts.get("funding_milestone", [])}
        unknown = texts - known
        issues += [
            ("alias_sin_cliente", text, {"source": source, "text": text})
            for text in sorted(unknown)
        ]
        for issue_type, key, details in issues:
            detect.upsert(conn, issue_type, f"{tab_id}:{key}", source_id, tab_id, details)
        duplicates = conn.execute(DUPLICATES, (tab_id,)).fetchall()
        for k_source, k_tab, k_key, k_title, k_name, k_ref, *pagos_side in duplicates:
            p_tab, block, p_key, month, p_title, p_name, p_ref = pagos_side
            # Keyed by the tracker tab, whichever side was read: one problem per pair.
            key = f"{k_tab}:{k_key}|{p_tab}:{block}:{p_key}:{month:%Y-%m}"
            details = {
                "tracker": {"planilla": k_title, "pestaña": k_name, "cell_ref": k_ref},
                "pagos": {"planilla": p_title, "pestaña": p_name, "cell_ref": p_ref},
            }
            detect.upsert(conn, "funding_duplicado", key, k_source, k_tab, details)
        counts["issues"] = len(issues) + len(duplicates)
        duration_ms = round((time.monotonic() - started) * 1000)
        events.record(
            conn,
            "tab_interpreted",
            source_id=source_id,
            source_tab_id=tab_id,
            duration_ms=duration_ms,
            snapshot_id=snapshot_id,
            accruals=counts["accrual"],
            fx_rates=counts["fx_rate"],
            invoices=counts["invoice"],
            payments=counts["payment"],
            churn=counts["client_churn"],
            fundings=counts["funding_milestone"],
            issues=counts["issues"],
        )
    return {**counts, "duration_ms": duration_ms}
