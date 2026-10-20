"""Facts of the last read of a tab (ADR-002): accruals from VENTAS; invoices, payments, churn
and totals from Pagos; the same plus exchange rates from Pagos ARG.

Each tab with an interpreter has its facts replaced as a whole on every new read. Facts carry
no client: the views resolve it through client_alias, so loading an alias needs no rerun.
Events and problem details carry identifiers and counts, never amounts.
"""

import time

import psycopg

from craftech_os import clients, events
from craftech_os.interpret import pagos, ventas
from craftech_os.issues import detect

RULES_VERSION = "v0.9"
INTERPRETERS = {
    "VENTAS": lambda doc, schema, title: ventas.interpret(doc, schema),
    "Pagos": pagos.interpret,
    "Pagos ARG": pagos.interpret_arg,
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
    "payment": ("block", "row_key", "month", "legal_entity", "cell_change_id"),
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
}


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
    for table in ("accrual", "invoice", "client_churn"):
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
        unknown = texts - known
        issues += [
            ("alias_sin_cliente", text, {"source": source, "text": text})
            for text in sorted(unknown)
        ]
        for issue_type, key, details in issues:
            detect.upsert(conn, issue_type, f"{tab_id}:{key}", source_id, tab_id, details)
        counts["issues"] = len(issues)
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
            issues=counts["issues"],
        )
    return {**counts, "duration_ms": duration_ms}
