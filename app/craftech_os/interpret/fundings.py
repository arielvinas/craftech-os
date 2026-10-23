"""Funding milestones (rule R28): from the AWS blocks of Pagos up to February 2026, and from the
FUNDINGS tracker for what is collected from March 2026. The CEI program comes from Pagos up to
September 2026.

Both origins are kept: a funding on both sides is reported as funding_duplicado, never merged.
Until the tracker has a fund claim ID column, a milestone is known by its program and its
order within the program of the client, a provisional key. Fundings are never invoices
(rule R15): they live in their own table and views.
Problems carry blocks, row keys, header texts and cell references, never amounts.
"""

from collections import Counter
from datetime import date, timedelta

from craftech_os.diff.compare import a1, blocks, column_letters, normalize, value
from craftech_os.interpret.cells import day, number, unreadable
from craftech_os.issues import detect

# Rule R28: Pagos holds what is collected up to February 2026, the tracker what is collected
# since, whenever it was loaded (Ariel's decision of 22-oct-2026, pending ratification by Ro).
# A tracker row without any collection date goes by its load date: from 25/2/2026 it is there.
CUT = date(2026, 2, 25)
LAST_PAGOS_MONTH = date(2026, 2, 1)
# The CEI program, paid at the end of each quarter, had its last payment in September 2026:
# ratified by Emi and Ro. The tracker does not hold it, so Pagos is its source after the cut too.
CEI_LAST_MONTH = date(2026, 9, 1)
# Rule R22: the collection is expected 30 days after the sign-off.
COLLECTION_DAYS = 30
# Roles the tracker schema must map to a header text; fund_claim_id is optional.
REQUIRED = (
    "program",
    "status",
    "business_unit",
    "load_date",
    "estimated_signoff",
    "amount_usd",
    "opportunity",
    "invoice_loaded",
    "paid_on",
)
# Business units of the tracker: the parity views match each milestone to the sheet of its unit.
UNITS = ("craftech", "sleakops")
# Column of Pagos with the program of a funding row ("Generado por" in the header block).
PROGRAM_C = 1


def _text(cell: dict | None) -> str | None:
    return (value(cell) or "").strip() or None


def _row_key(row: dict) -> str:
    return row["key"] if row["ordinal"] == 1 else f"{row['key']} ({row['ordinal']})"


def interpret(doc: dict, schema: dict, title: str) -> tuple[dict, list[tuple[str, str, dict]]]:
    """FUNDINGS: ({"funding_milestone": [fact]}, [(issue_type, key, details)]).

    Columns are found by their header text. A row without amount is not a milestone; a row
    collected up to February 2026 is in Pagos. The collection is the payment date, else the
    estimated sign-off + 30 days; a row with neither is kept unless loaded before the cut, when
    it is a problem: which side holds it is not guessed.
    """
    split = blocks(doc, schema)
    if split is None:
        return {"funding_milestone": []}, [("fila_sin_interpretar", "sin encabezado", {})]
    _, tab_blocks = split
    block, rows = next((b, rows) for b, rows in tab_blocks if b == schema["header"])
    found = {}
    for c, cell in sorted(rows[0]["cells"].items()):
        found.setdefault(normalize(value(cell) or ""), c)
    at = {role: found.get(normalize(text)) for role, text in schema["columns"].items()}
    missing = [schema["columns"][role] for role in REQUIRED if at[role] is None]
    if missing:
        return {"funding_milestone": []}, [
            ("fila_sin_interpretar", f"falta:{text}", {"column": text}) for text in missing
        ]
    milestones, issues = [], []
    order = Counter()
    for row in rows[1:]:

        def cell(role, row=row):
            return row["cells"].get(at[role]) if at.get(role) is not None else None

        amount_cell = cell("amount_usd") or {}
        amount = number(amount_cell)
        if amount is None and unreadable(amount_cell):
            issues.append(detect.unreadable(block, row, rows[0]["cells"], at["amount_usd"]))
            continue
        if not amount:
            continue
        load_date = day(cell("load_date"))
        signoff = day(cell("estimated_signoff"))
        collection = signoff and signoff + timedelta(days=COLLECTION_DAYS)
        paid_on = day(cell("paid_on"))
        collected = paid_on or collection
        if collected is not None and collected.replace(day=1) <= LAST_PAGOS_MONTH:
            continue
        if collected is None and load_date is not None and load_date < CUT:
            name = _row_key(row) if row["key"] else f"fila {row['r'] + 1}"
            details = {
                "cell_ref": a1(row["r"], at["paid_on"]),
                "reason": "sin fecha de pago ni sign-off estimado y cargada antes del 25/2/2026:"
                " no se sabe si la cubre Pagos",
            }
            issues.append(("fila_sin_interpretar", f"{block}:{name}:cobro", details))
            continue
        ref = a1(row["r"], at["amount_usd"])
        if row["key"] in (None, "[vacio]"):
            name = row["key"] or f"fila {row['r'] + 1}"
            issues.append(("fila_sin_interpretar", f"{block}:{name}", {"cell_ref": ref}))
            continue
        business_unit = _text(cell("business_unit"))
        if normalize(business_unit or "") not in UNITS:
            # Kept, but no parity view adds it: a problem, not a silent gap.
            unit_ref = a1(row["r"], at["business_unit"])
            issues.append(
                ("fila_sin_interpretar", f"{block}:{_row_key(row)}:unidad", {"cell_ref": unit_ref})
            )
        program = _text(cell("program"))
        order[(row["key"], normalize(program or ""))] += 1
        fund_claim_id = _text(cell("fund_claim_id"))
        milestones.append(
            {
                "origin": "tracker",
                "block": block,
                "row_key": _row_key(row),
                "program": program,
                "opportunity": _text(cell("opportunity")),
                "fund_claim_id": fund_claim_id,
                "program_order": order[(row["key"], normalize(program or ""))],
                "provisional_key": fund_claim_id is None,
                "month": None,
                "amount_usd": amount,
                "status": _text(cell("status")),
                "business_unit": business_unit,
                "load_date": load_date,
                "estimated_signoff": signoff,
                "estimated_collection": collection,
                "invoice_loaded": normalize(_text(cell("invoice_loaded")) or "") == "si",
                "paid_on": paid_on,
                "alias_text": row["key"],
                "cell_ref": ref,
            }
        )
    return {"funding_milestone": milestones}, issues


def from_pagos(tab_blocks, header: dict, columns, months: dict, funding_blocks) -> tuple:
    """([milestone], [issue]) of the funding blocks of a Pagos tab, one per amount and month.

    Amounts copied from another sheet are not milestones. An amount typed in the row that opens
    a block is a problem, except in the CEI row of "General": a program, not a client, whose
    amounts (copies included) are milestones up to its end, also after the cut of rule R28.
    """
    milestones, issues = [], []
    order = Counter()
    for block, rows in tab_blocks:
        if block.split(" (")[0] not in funding_blocks:
            continue
        for row in rows:
            program = _text(row["cells"].get(PROGRAM_C))
            cei = row is rows[0] and block.split(" (")[0] == "General"
            cei = cei and normalize(program or "") == "cei"
            for c in columns:
                cell = row["cells"].get(c)
                if cell is None:
                    continue
                formula = (cell.get("formula") or "").upper()
                if not cei and ("!" in formula or "IMPORTRANGE" in formula):
                    continue
                amount = number(cell)
                if amount is None and unreadable(cell):
                    issues.append(detect.unreadable(block, row, header["cells"], c))
                    continue
                if not amount:
                    continue
                if not cei and c in months and months[c] > LAST_PAGOS_MONTH:
                    continue
                name = row["key"] or f"fila {row['r'] + 1}"
                where = f"{block}:{name}:{column_letters(c)}"
                details = {"block": block, "cell_ref": a1(row["r"], c)}
                if cei and c in months and months[c] > CEI_LAST_MONTH:
                    details["reason"] = "el programa CEI terminó en septiembre de 2026"
                    issues.append(("fila_sin_interpretar", where, details))
                    continue
                if row["key"] is None or c not in months or (row is rows[0] and not cei):
                    issues.append(("fila_sin_interpretar", where, details))
                    continue
                order[(row["key"], normalize(program or ""))] += 1
                milestones.append(
                    {
                        "origin": "pagos",
                        "block": block,
                        "row_key": _row_key(row),
                        "program": program,
                        "opportunity": None,
                        "fund_claim_id": None,
                        "program_order": order[(row["key"], normalize(program or ""))],
                        "provisional_key": True,
                        "month": months[c],
                        "amount_usd": amount,
                        "status": None,
                        "business_unit": None,
                        "load_date": None,
                        "estimated_signoff": None,
                        "estimated_collection": None,
                        "invoice_loaded": None,
                        "paid_on": None,
                        "alias_text": row["key"],
                        "program_row": cei,
                        "cell_ref": a1(row["r"], c),
                    }
                )
    return milestones, issues
