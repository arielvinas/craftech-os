"""The snapshot document of a tab, built from a Sheets API grid answer, and its hash.

Cell content is untrusted input: it is copied as it came, never interpreted.
"""

import hashlib
import json


def _hex(color: dict | None) -> str | None:
    if color is None:
        return None
    # The API omits a channel when it is 0.
    channels = (color.get("red", 0), color.get("green", 0), color.get("blue", 0))
    return "#" + "".join(f"{round(c * 255):02x}" for c in channels)


def _cell(c: int, value: dict) -> dict | None:
    if not any(k in value for k in ("effectiveValue", "formattedValue", "userEnteredValue")):
        return None
    fmt = value.get("effectiveFormat", {})
    cell = {
        "c": c,
        "value": value.get("effectiveValue"),
        "text": value.get("formattedValue"),
        "bg": _hex(fmt.get("backgroundColor")),
        "format": fmt.get("numberFormat", {}).get("pattern"),
    }
    formula = value.get("userEnteredValue", {}).get("formulaValue")
    if formula is not None:
        cell["formula"] = formula
    return cell


def build(grid: dict) -> dict:
    """Rows with their non-empty cells, merged ranges and sizes; 0-based row and column."""
    props = grid.get("properties", {})
    rows = []
    for block in grid.get("data", []):
        row0, col0 = block.get("startRow", 0), block.get("startColumn", 0)
        for i, row in enumerate(block.get("rowData", [])):
            cells = [
                cell
                for j, value in enumerate(row.get("values", []))
                if (cell := _cell(col0 + j, value)) is not None
            ]
            if cells:
                rows.append({"r": row0 + i, "cells": cells})
    merges = [
        {
            "start_row": m.get("startRowIndex", 0),
            "end_row": m.get("endRowIndex", 0),
            "start_col": m.get("startColumnIndex", 0),
            "end_col": m.get("endColumnIndex", 0),
        }
        for m in grid.get("merges", [])
    ]
    grid_size = props.get("gridProperties", {})
    return {
        "sheet_id": props.get("sheetId", 0),
        "title": props.get("title"),
        "hidden": props.get("hidden", False),
        "grid": {"rows": grid_size.get("rowCount"), "cols": grid_size.get("columnCount")},
        "used": {
            "rows": max((r["r"] + 1 for r in rows), default=0),
            "cols": max((c["c"] + 1 for r in rows for c in r["cells"]), default=0),
        },
        "rows": rows,
        "merges": merges,
    }


def cell_count(doc: dict) -> int:
    return sum(len(r["cells"]) for r in doc["rows"])


def canonical(doc: dict) -> str:
    """Sorted-keys JSON. Raises ValueError or TypeError if doc is not plain JSON."""
    return json.dumps(
        doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def content_hash(serialized: str) -> str:
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
