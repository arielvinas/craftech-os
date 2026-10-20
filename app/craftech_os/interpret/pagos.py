"""Invoices of a Pagos or Pagos ARG tab: one per amount cell of the header block, in the state
its color says (rule R29); churn of SleakOps; and the total row of the tab to check them against.

Only the block of the header holds invoices: the funding blocks belong to T-012. Payments are
linked afterwards to the cell change that painted the invoice green (link), never copied.
Problems carry blocks, row keys and cell references, never amounts.
"""

import re
from collections import Counter
from decimal import Decimal, InvalidOperation

import psycopg

from craftech_os.diff.compare import a1, column_index, column_letters, normalize
from craftech_os.interpret import pagos_arg
from craftech_os.interpret.cells import grid, number, unreadable
from craftech_os.issues import detect

# Rule R29: the state of each known color.
STATES = {
    None: "a facturar",
    "#ffffff": "a facturar",
    "#00ffff": "a confirmar",
    "#4a86e8": "confirmada",
    "#ff9900": "enviada",
    "#d9ead3": "pagada",
    "#ff00ff": "retraso",
}
assert set(STATES) == detect.KNOWN_COLORS
PAID, SENT = "#d9ead3", "#ff9900"
IVA = Decimal("1.21")
REFERENCE = re.compile(r"([A-Z]+)(\d+)")


def interpret(doc: dict, schema: dict, title: str) -> tuple[dict, list[tuple[str, str, dict]]]:
    """Pagos: ({"invoice", "client_churn", "payment_total": [fact]}, [(issue_type, key, details)]).

    In SleakOps a painted cell without amount is a churn (rule R31).
    """
    sleakops = "sleakops" in normalize(title)
    return _interpret(doc, schema, "Craftech-io Inc.", "total pagos usa", sleakops)


def interpret_arg(doc: dict, schema: dict, title: str) -> tuple[dict, list[tuple[str, str, dict]]]:
    """Pagos ARG: the invoices in ARS with their rate (rules R10, R14), plus its exchange rates."""
    facts, issues = _interpret(doc, schema, "Craftech S.A.", "total ingresos", False)
    rates, rate_issues = pagos_arg.interpret(doc, schema)
    return {**facts, **rates}, issues + rate_issues


def _interpret(doc: dict, schema: dict, legal_entity: str, total_key: str, churn: bool):
    found = grid(doc, schema)
    if found is None:
        return {"invoice": [], "client_churn": [], "payment_total": []}, [
            ("fila_sin_interpretar", "sin encabezado", {})
        ]
    tab_blocks, header, columns, months = found
    by_r = {row["r"]: row for _, rows in tab_blocks for row in rows}
    ars = legal_entity == "Craftech S.A."
    invoices, churned, issues = [], [], []
    block, rows = next((b, rows) for b, rows in tab_blocks if rows[0] is header)
    with_amounts = Counter()
    for row in rows[1:]:
        row_key = row["key"] if row["ordinal"] == 1 else f"{row['key']} ({row['ordinal']})"
        seen = False
        for c in columns:
            cell = row["cells"].get(c)
            if cell is None:
                continue
            amount = number(cell)
            if amount is None and unreadable(cell):
                issues.append(detect.unreadable(block, row, header["cells"], c))
                continue
            if "!" in (cell.get("formula") or ""):
                # A copy of another tab, such as Pagos ARG in Pagos: invoiced there.
                continue
            bg = cell.get("bg")
            if not amount:
                if churn and bg not in (None, "#ffffff") and row["key"] and c in months:
                    churned.append(
                        {
                            "block": block,
                            "row_key": row_key,
                            "series_order": row["ordinal"],
                            "month": months[c],
                            "color": bg,
                            # Which color marks a churn stays open until Emi answers F-05.
                            "color_to_confirm": True,
                            "alias_text": row["key"],
                            "cell_ref": a1(row["r"], c),
                        }
                    )
                continue
            if bg not in STATES:
                # color_desconocido is opened by detect.find for every grid cell.
                continue
            if row["key"] is None or c not in months:
                name = row["key"] or f"fila {row['r'] + 1}"
                where = f"{block}:{name}:{column_letters(c)}"
                issues.append(
                    ("fila_sin_interpretar", where, {"block": block, "cell_ref": a1(row["r"], c)})
                )
                continue
            invoice = {
                "block": block,
                "row_key": row_key,
                "series_order": row["ordinal"],
                "month": months[c],
                "legal_entity": legal_entity,
                "state": STATES[bg],
                "amount": amount,
                "currency": "ARS" if ars else "USD",
                "net_ars": (amount / IVA).quantize(Decimal("0.01")) if ars else None,
                "fx_rate": None,
                "fx_rate_type": None,
                "fx_rate_to_confirm": False,
                "inferred_usd": None,
                "alias_text": row["key"],
                "cell_ref": a1(row["r"], c),
            }
            if ars:
                invoice.update(_rate(cell, by_r, block, row, header, c, issues))
            invoices.append(invoice)
            seen = True
        if seen:
            with_amounts[row["key"]] += 1
    # Rule R26: the same text in two rows of a block is two series, to be reviewed.
    issues += [
        ("identidad_en_revision", f"{block}:{key}", {"block": block, "rows": n})
        for key, n in sorted(with_amounts.items())
        if n > 1
    ]
    totals = []
    total = next((by_r[r] for r in sorted(by_r) if by_r[r]["key"] == total_key), None)
    if total is None:
        issues.append(("fila_sin_interpretar", f"falta:{total_key}", {"row": total_key}))
    else:
        for c, month in months.items():
            if (amount := number(total["cells"].get(c) or {})) is not None:
                totals.append(
                    {
                        "row_key": total_key,
                        "month": month,
                        "amount": amount,
                        "cell_ref": a1(total["r"], c),
                    }
                )
    return {"invoice": invoices, "client_churn": churned, "payment_total": totals}, issues


def _rate(cell: dict, by_r: dict, block: str, row: dict, header: dict, c: int, issues: list):
    """Rule R10: the rate of an ARG invoice, from the row its formula references.

    A formula is read as a product such as =7200*1.21*M$1: the reference is the rate, the
    number left after one 1.21 is the base in USD. A rate typed in the formula or a typed
    amount opens cotizacion_tipeada (rule R38). Anything else leaves the rate unknown.
    """
    unknown = {"fx_rate": None, "fx_rate_type": None, "fx_rate_to_confirm": False}
    formula = re.sub(r"[=$()\s]", "", cell.get("formula") or "")
    factors = formula.split("*") if formula else []
    references = [f for f in factors if REFERENCE.fullmatch(f)]
    numbers = []
    for factor in factors:
        if factor in references:
            continue
        try:
            numbers.append(Decimal(factor))
        except InvalidOperation:
            return {**unknown, "inferred_usd": None}
    if IVA in numbers:
        numbers.remove(IVA)
    if len(references) == 1:
        letters, digits = REFERENCE.fullmatch(references[0]).groups()
        source = by_r.get(int(digits) - 1)
        rate = number((source or {"cells": {}})["cells"].get(column_index(letters)) or {})
        key = (source or {}).get("key")
        rate_type = pagos_arg.ROWS.get(key)
        if rate_type is None:
            where = key or f"fila {digits}"
            issues.append(("cotizacion_tipo_a_confirmar", where, {"row": where}))
        return {
            "fx_rate": rate,
            "fx_rate_type": rate_type,
            "fx_rate_to_confirm": rate_type != "mep",
            "inferred_usd": numbers[0] if len(numbers) == 1 else None,
        }
    if references:
        return {**unknown, "inferred_usd": None}
    _, where, details = detect.unreadable(block, row, header["cells"], c)
    issues.append(("cotizacion_tipeada", where, details))
    if len(numbers) == 2:
        return {
            "fx_rate": numbers[1],
            "fx_rate_type": "tipeada",
            "fx_rate_to_confirm": False,
            "inferred_usd": numbers[0],
        }
    return {**unknown, "inferred_usd": None}


def link(conn: psycopg.Connection, tab_id: int, snapshot_id: int, facts: dict) -> None:
    """Point each invoice at the last change that painted it orange, and add one payment per
    paid invoice pointing at the last change that painted it green (rule R4).

    Changes are matched by block, row key, series and month, never by cell: rows move.
    A change is a repaint, or an amount typed into an empty cell of that color.
    """
    docs = {}
    last = {}
    for change_id, to_snapshot, block, key, ordinal, ref, color in conn.execute(
        """
        SELECT c.id, c.to_snapshot, c.block, c.row_key, c.row_ordinal, c.cell_ref, c.new_color
        FROM cell_change c
        WHERE c.source_tab_id = %s AND c.to_snapshot <= %s AND c.new_color IN (%s, %s)
          AND (c.change_type = 'color' OR (c.change_type = 'value' AND c.old_value IS NULL))
        ORDER BY c.id
        """,
        (tab_id, snapshot_id, PAID, SENT),
    ):
        if to_snapshot not in docs:
            doc, schema = conn.execute(
                "SELECT n.content, t.schema FROM snapshot n"
                " JOIN source_tab t ON t.id = n.source_tab_id WHERE n.id = %s",
                (to_snapshot,),
            ).fetchone()
            docs[to_snapshot] = (grid(doc, schema) or (None, None, None, {}))[3]
        month = docs[to_snapshot].get(column_index(re.sub(r"\d+$", "", ref)))
        if month is not None and key is not None:
            row_key = key if ordinal == 1 else f"{key} ({ordinal})"
            last[(color, block, row_key, month)] = change_id
    facts["payment"] = []
    for invoice in facts["invoice"]:
        where = (invoice["block"], invoice["row_key"], invoice["month"])
        invoice["sent_change_id"] = last.get((SENT, *where))
        if invoice["state"] == "pagada":
            facts["payment"].append(
                {
                    "block": invoice["block"],
                    "row_key": invoice["row_key"],
                    "month": invoice["month"],
                    "legal_entity": invoice["legal_entity"],
                    "cell_change_id": last.get((PAID, *where)),
                }
            )
