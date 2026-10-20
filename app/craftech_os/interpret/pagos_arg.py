"""Exchange rates of a Pagos ARG tab: one per rate row and month, the value as in the cell.

Rate rows are found by their text in the key column, never by row number. The last MEP row
is the operational one; earlier MEP rows are controls checked against it (rule R10).
Problems carry cell references and months, never values.
"""

from craftech_os.diff.compare import a1, column_letters
from craftech_os.interpret.cells import grid, number, unreadable
from craftech_os.issues import detect

ROWS = {"mep": "mep", "dolar oficial": "oficial"}


def _rates(block: str, row: dict, header: dict, columns, months: dict, issues: list) -> dict:
    """{month: (value, cell_ref)} of a rate row.

    A cell that is not a number, or a rate in a column without a month of its own, is a problem.
    """
    rates = {}
    for c in columns:
        cell = row["cells"].get(c)
        if cell is None:
            continue
        if (rate := number(cell)) is not None:
            if c in months:
                rates[months[c]] = (rate, a1(row["r"], c))
            else:
                where = row["key"] if row["ordinal"] == 1 else f"{row['key']} ({row['ordinal']})"
                issues.append(
                    (
                        "fila_sin_interpretar",
                        f"{block}:{where}:{column_letters(c)}",
                        {"block": block, "cell_ref": a1(row["r"], c)},
                    )
                )
        elif unreadable(cell):
            issues.append(detect.unreadable(block, row, header["cells"], c))
    return rates


def interpret(doc: dict, schema: dict) -> tuple[dict, list[tuple[str, str, dict]]]:
    """({"fx_rate": [fact]}, [(issue_type, key without the tab, details)])."""
    found = grid(doc, schema)
    if found is None:
        return {"fx_rate": []}, [("fila_sin_interpretar", "sin encabezado", {})]
    tab_blocks, header, columns, months = found
    issues = []
    rows = {rate_type: [] for rate_type in ROWS.values()}
    for block, block_rows in tab_blocks:
        for row in block_rows:
            if row["key"] in ROWS:
                rows[ROWS[row["key"]]].append(_rates(block, row, header, columns, months, issues))
    facts = []
    for rate_type, found_rows in rows.items():
        if not found_rows:
            issues.append(("fila_sin_interpretar", f"falta:{rate_type}", {"rate_type": rate_type}))
            continue
        if rate_type == "mep":
            stored, *controls = found_rows[::-1]
            discrepant = {}
            for control in controls:
                for month, (rate, ref) in control.items():
                    if month in stored and round(rate, 4) != round(stored[month][0], 4):
                        discrepant.setdefault(
                            month,
                            {
                                "month": month.isoformat(),
                                "control": ref,
                                "operativa": stored[month][1],
                            },
                        )
            issues += [
                ("cotizacion_discrepante", f"mep:{month:%Y-%m}", details)
                for month, details in sorted(discrepant.items())
            ]
        else:
            # Which rate "Dólar oficial" is stays open until Emi answers question F-01.
            stored, *extra = found_rows
            issues.append(("cotizacion_tipo_a_confirmar", rate_type, {"rate_type": rate_type}))
            if extra:
                issues.append(
                    ("fila_sin_interpretar", f"{rate_type}:repetida", {"rows": len(found_rows)})
                )
        facts += [
            {
                "rate_type": rate_type,
                "month": month,
                "value": rate,
                "type_to_confirm": rate_type == "oficial",
                "cell_ref": ref,
            }
            for month, (rate, ref) in sorted(stored.items())
        ]
    return {"fx_rate": facts}, issues
