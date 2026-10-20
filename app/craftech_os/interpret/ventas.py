"""Accruals of a VENTAS tab: one per client row and month column, the amount as in the cell.

The amount is already prorated by days (rule R1) and net of IVA (rule R14); nothing is
recalculated. Problems carry blocks, row keys and cell references, never amounts.
"""

import re
from collections import Counter

from craftech_os.diff.compare import BEFORE_HEADER, a1, column_letters, normalize, value
from craftech_os.interpret.cells import grid, number, unreadable
from craftech_os.issues import detect

SKIPPED_BLOCKS = {"total ingresos"}
LABELS = {"business_unit": "u. negocio", "pod": "pod"}


def interpret(doc: dict, schema: dict) -> tuple[dict, list[tuple[str, str, dict]]]:
    """({"accrual": [fact]}, [(issue_type, key without the tab, details)])."""
    found = grid(doc, schema)
    if found is None:
        return {"accrual": []}, [("fila_sin_interpretar", "sin encabezado", {})]
    tab_blocks, header, columns, months = found
    labels = {normalize(value(cell) or ""): c for c, cell in header["cells"].items()}
    label_columns = {field: labels.get(label) for field, label in LABELS.items()}
    accruals, issues = [], []
    for block, rows in tab_blocks:
        if block == BEFORE_HEADER or normalize(re.sub(r" \(\d+\)$", "", block)) in SKIPPED_BLOCKS:
            continue
        with_amounts = Counter()
        for i, row in enumerate(rows):
            if row is header:
                continue
            amounts = {}
            for c in columns:
                cell = row["cells"].get(c)
                if cell is None:
                    continue
                if (amount := number(cell)) is not None:
                    amounts[c] = amount
                elif unreadable(cell) and i > 0:
                    issues.append(detect.unreadable(block, row, header["cells"], c))
            if i == 0 or row["key"] is None:
                # The row that opens a block, or one without a client: nowhere to put amounts.
                if any(amounts.values()):
                    where = f"{block}:fila {row['r'] + 1}"
                    issues.append(
                        ("fila_sin_interpretar", where, {"block": block, "row": row["r"] + 1})
                    )
                continue
            row_key = row["key"] if row["ordinal"] == 1 else f"{row['key']} ({row['ordinal']})"
            fields = {
                field: value(row["cells"].get(c)) if c is not None else None
                for field, c in label_columns.items()
            }
            for c, amount in amounts.items():
                if c not in months:
                    if amount:
                        where = f"{block}:{row_key}:{column_letters(c)}"
                        issues.append(
                            (
                                "fila_sin_interpretar",
                                where,
                                {"block": block, "cell_ref": a1(row["r"], c)},
                            )
                        )
                    continue
                accruals.append(
                    {
                        "block": block,
                        "row_key": row_key,
                        "series_order": row["ordinal"],
                        "month": months[c],
                        "amount_usd": amount,
                        **fields,
                        "alias_text": row["key"],
                        "cell_ref": a1(row["r"], c),
                    }
                )
            if any(c in months for c in amounts):
                with_amounts[row["key"]] += 1
        # Rule R26: the same text in two rows of a block is two series, to be reviewed.
        issues += [
            ("identidad_en_revision", f"{block}:{key}", {"block": block, "rows": n})
            for key, n in sorted(with_amounts.items())
            if n > 1
        ]
    return {"accrual": accruals}, issues
