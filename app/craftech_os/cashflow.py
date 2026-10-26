"""Monthly cashflow (ADR-003, T-019): the rows of config/cashflow_rows.yaml and the cells of the
Resumen tab of "CASH FLOW MENSUAL", so the view cashflow_cell computes every value from the bank
movements and says where each cell is in the tab.

The Resumen is read only to place the rows and months: its values are stored for the parity
check (T-020), never shown as the value of a cell. Events carry counts, never amounts.
"""

import time
from pathlib import Path

import psycopg
import yaml

from craftech_os import events
from craftech_os.diff.compare import a1, normalize, value
from craftech_os.interpret.cells import month, number
from craftech_os.interpret.consolidado import ROWS_FILE, _texts

SHEET = "CASH FLOW MENSUAL"
RESUMEN = "Resumen mensual Cash Flow ARG-USA"
UNITS = ("ars", "usd")
BALANCES = ("inicial", "final")
# Column A opens a section of the tab; column B has the labels of its rows.
SECTION, LABEL, FIRST_MONTH = 0, 1, 2


def rows(path: Path = ROWS_FILE) -> list[dict]:
    """The rows of the cashflow, in order, with how each is computed; ValueError if malformed."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    out = []
    for block_order, block in enumerate(data["blocks"]):
        name = block["name"]
        if block.get("unit") not in UNITS:
            raise ValueError(f"{name}: unit {block.get('unit')!r} is not one of {UNITS}")
        labels = [row["label"] for row in block["rows"]]
        for row_order, row in enumerate(block["rows"]):
            what = f"{name} / {row['label']}"
            rule = {k: _texts(row.get(k), what) for k in ("rubros", "agrupadores", "banks", "adds")}
            balance = row.get("balance")
            if balance is not None and (balance not in BALANCES or not rule["banks"]):
                raise ValueError(f"{what}: balance must be one of {BALANCES} and name banks")
            if row.get("sign") not in (None, "-"):
                raise ValueError(f"{what}: sign must be '-' or absent")
            for added in rule["adds"]:
                target = next((r for r in block["rows"] if r["label"] == added), None)
                if added not in labels or target.get("adds"):
                    raise ValueError(f"{what}: adds {added!r}, not a plain row of the block")
            out.append(
                {
                    "block": name,
                    "block_order": block_order,
                    "label": row["label"],
                    "row_order": row_order,
                    "resumen": block["resumen"],
                    "unit": block["unit"],
                    **rule,
                    "balance": balance,
                    "sign": -1 if row.get("sign") == "-" else 1,
                    "parametro": row.get("parametro"),
                }
            )
    return out


def _text(cell: dict | None) -> str:
    return normalize(value(cell) or "")


def locate(doc: dict, cashflow_rows: list[dict]) -> tuple[dict, list[dict]]:
    """({column: month} of the header, [cell]) of the rows of the cashflow found in the tab.

    A text in column A naming the resumen of a block opens its section, with the label in
    column B; until another text in column A closes it. A section title can have its labels in
    column A with column B empty. The first row with a label in a section is the one taken.
    """
    sections = {}
    for row in cashflow_rows:
        sections.setdefault(normalize(row["resumen"]), {}).setdefault(normalize(row["label"]), row)
    months, cells, found = {}, [], set()
    section = None
    for line in doc["rows"]:
        by_c = {cell["c"]: cell for cell in line["cells"]}
        if not months:
            months = {c: m for c, cell in by_c.items() if c >= FIRST_MONTH and (m := month(cell))}
            continue
        head, label = _text(by_c.get(SECTION)), _text(by_c.get(LABEL))
        if head in sections:
            section = sections[head]
        elif head and not label and section is not None and head in section:
            label = head
        elif head:
            section = None
        row = section and section.get(label)
        if not row or (row["block"], row["label"]) in found:
            continue
        found.add((row["block"], row["label"]))
        for c, m in months.items():
            cell = by_c.get(c) or {}
            cells.append(
                {
                    "block": row["block"],
                    "label": row["label"],
                    "month": m,
                    "value": number(cell),
                    "cell_ref": a1(line["r"], c),
                    "has_formula": "formula" in cell,
                }
            )
    return months, cells


ROW_COLUMNS = (
    "block",
    "block_order",
    "label",
    "row_order",
    "unit",
    "rubros",
    "agrupadores",
    "banks",
    "balance",
    "adds",
    "sign",
    "parametro",
)
CELL_COLUMNS = ("block", "label", "month", "value", "cell_ref", "has_formula")


def project(conn: psycopg.Connection, snapshot_id: int) -> dict | None:
    """Replace the cashflow rows and the cells of the Resumen with the ones of this snapshot.

    Returns the counts, or None if the snapshot is not of the Resumen (nothing is touched then).
    """
    started = time.monotonic()
    tab_id, source_id, name, title, doc = conn.execute(
        """
        SELECT t.id, t.source_id, t.name, s.title, n.content
        FROM snapshot n JOIN source_tab t ON t.id = n.source_tab_id
        JOIN source s ON s.id = t.source_id
        WHERE n.id = %s
        """,
        (snapshot_id,),
    ).fetchone()
    if (title, name) != (SHEET, RESUMEN):
        return None
    cashflow_rows = rows()
    _, cells = locate(doc, cashflow_rows)
    with conn.transaction():
        conn.execute("DELETE FROM cashflow_row")
        conn.execute("DELETE FROM cashflow_sheet_cell WHERE source_tab_id = %s", (tab_id,))
        with conn.cursor() as cur:
            cur.executemany(
                f"INSERT INTO cashflow_row ({', '.join(ROW_COLUMNS)})"
                f" VALUES ({', '.join(['%s'] * len(ROW_COLUMNS))})",
                [tuple(r[c] for c in ROW_COLUMNS) for r in cashflow_rows],
            )
            cur.executemany(
                f"INSERT INTO cashflow_sheet_cell (source_tab_id, snapshot_id,"
                f" {', '.join(CELL_COLUMNS)})"
                f" VALUES (%s, %s, {', '.join(['%s'] * len(CELL_COLUMNS))})",
                [(tab_id, snapshot_id, *(c[k] for k in CELL_COLUMNS)) for c in cells],
            )
        placed = len({(c["block"], c["label"]) for c in cells})
        counts = {"rows": placed, "cells": len(cells), "missing": len(cashflow_rows) - placed}
        counts["duration_ms"] = round((time.monotonic() - started) * 1000)
        events.record(
            conn,
            "cashflow_projected",
            source_id=source_id,
            source_tab_id=tab_id,
            duration_ms=counts["duration_ms"],
            snapshot_id=snapshot_id,
            filas=counts["rows"],
            celdas=counts["cells"],
            filas_sin_ubicar=counts["missing"],
        )
    return counts
