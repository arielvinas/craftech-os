"""Funding milestones (rule R28): from the AWS blocks of Pagos up to February 2026, and from the
FUNDINGS tracker for what was loaded from 25 February 2026.

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

# Rule R28: Pagos holds the milestones up to 24/2/2026, the tracker the ones loaded since.
CUT = date(2026, 2, 25)
LAST_PAGOS_MONTH = date(2026, 2, 1)
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
# Column of Pagos with the program of a funding row ("Generado por" in the header block).
PROGRAM_C = 1


def _text(cell: dict | None) -> str | None:
    return (value(cell) or "").strip() or None


def _row_key(row: dict) -> str:
    return row["key"] if row["ordinal"] == 1 else f"{row['key']} ({row['ordinal']})"


def interpret(doc: dict, schema: dict, title: str) -> tuple[dict, list[tuple[str, str, dict]]]:
    """FUNDINGS: ({"funding_milestone": [fact]}, [(issue_type, key, details)]).

    Columns are found by their header text. A row without amount is not a milestone; a row
    loaded before the cut is in Pagos. A row not loaded yet, without load date, is kept.
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
        if load_date is not None and load_date < CUT:
            continue
        ref = a1(row["r"], at["amount_usd"])
        if row["key"] in (None, "[vacio]"):
            name = row["key"] or f"fila {row['r'] + 1}"
            issues.append(("fila_sin_interpretar", f"{block}:{name}", {"cell_ref": ref}))
            continue
        program = _text(cell("program"))
        order[(row["key"], normalize(program or ""))] += 1
        signoff = day(cell("estimated_signoff"))
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
                "business_unit": _text(cell("business_unit")),
                "load_date": load_date,
                "estimated_signoff": signoff,
                "estimated_collection": signoff and signoff + timedelta(days=COLLECTION_DAYS),
                "invoice_loaded": normalize(_text(cell("invoice_loaded")) or "") == "si",
                "paid_on": day(cell("paid_on")),
                "alias_text": row["key"],
                "cell_ref": ref,
            }
        )
    return {"funding_milestone": milestones}, issues


def from_pagos(tab_blocks, header: dict, columns, months: dict, funding_blocks) -> tuple:
    """([milestone], [issue]) of the funding blocks of a Pagos tab, one per amount and month.

    The row that opens a block, and amounts copied from another sheet, are not milestones.
    """
    milestones, issues = [], []
    order = Counter()
    for block, rows in tab_blocks:
        if block.split(" (")[0] not in funding_blocks:
            continue
        for row in rows[1:]:
            program = _text(row["cells"].get(PROGRAM_C))
            for c in columns:
                cell = row["cells"].get(c)
                if cell is None:
                    continue
                formula = (cell.get("formula") or "").upper()
                if "!" in formula or "IMPORTRANGE" in formula:
                    continue
                amount = number(cell)
                if amount is None and unreadable(cell):
                    issues.append(detect.unreadable(block, row, header["cells"], c))
                    continue
                if not amount:
                    continue
                if row["key"] is None or c not in months:
                    name = row["key"] or f"fila {row['r'] + 1}"
                    where = f"{block}:{name}:{column_letters(c)}"
                    issues.append(
                        (
                            "fila_sin_interpretar",
                            where,
                            {"block": block, "cell_ref": a1(row["r"], c)},
                        )
                    )
                    continue
                if months[c] > LAST_PAGOS_MONTH:
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
                        "cell_ref": a1(row["r"], c),
                    }
                )
    return milestones, issues
