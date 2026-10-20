"""Problems seen in one snapshot document: unknown colors and unreadable values in the grid.

Only tabs with a schema that declares a month grid are inspected. Problem details carry cell
references, colors and counts, never amounts.
"""

import json

import psycopg

from craftech_os.diff.compare import a1, blocks, column_index, column_letters, value

# Rule R29: the five invoice status colors, plus no color and explicit white.
KNOWN_COLORS = {None, "#ffffff", "#00ffff", "#4a86e8", "#ff9900", "#d9ead3", "#ff00ff"}
SAMPLE_REFS = 5


def find(doc: dict, schema: dict | None) -> list[tuple[str, str, dict]]:
    """[(issue_type, key without the tab, details)] for the grid cells of this document."""
    if not schema or not schema.get("grid"):
        return []
    split = blocks(doc, schema)
    if split is None:
        return []
    header_r, tab_blocks = split
    first, last = (column_index(x) for x in schema["grid"].split(":"))
    header = next(row["cells"] for _, rows in tab_blocks for row in rows if row["r"] == header_r)
    colors: dict[str, list[str]] = {}
    found = []
    for block, rows in tab_blocks[1:]:
        # The first row of each block is the header or the row that opens the block.
        for row in rows[1:]:
            for c, cell in sorted(row["cells"].items()):
                if not first <= c <= last:
                    continue
                ref = a1(row["r"], c)
                if cell.get("bg") not in KNOWN_COLORS:
                    colors.setdefault(cell["bg"], []).append(ref)
                if "stringValue" in (cell.get("value") or {}) and (value(cell) or "").strip():
                    found.append(unreadable(block, row, header, c))
    found += [
        ("color_desconocido", color, {"cells": len(refs), "sample": refs[:SAMPLE_REFS]})
        for color, refs in sorted(colors.items())
    ]
    return found


def unreadable(block: str, row: dict, header: dict, c: int) -> tuple[str, str, dict]:
    """The valor_ilegible problem of the cell of this row in column c."""
    where = row["key"] or f"fila {row['r'] + 1}"
    if row["ordinal"] and row["ordinal"] > 1:
        # Rule R26: a repeated key is another series of the same client.
        where += f" ({row['ordinal']})"
    column = value(header.get(c)) or column_letters(c)
    return "valor_ilegible", f"{block}:{where}:{column}", {"cell_ref": a1(row["r"], c)}


def upsert(
    conn: psycopg.Connection,
    issue_type: str,
    stable_key: str,
    source_id: int,
    source_tab_id: int | None,
    details: dict,
) -> None:
    """Record a problem; seeing it again only moves last_seen_at and refreshes its details."""
    conn.execute(
        """
        INSERT INTO issue (issue_type, stable_key, source_id, source_tab_id, details)
        VALUES (%s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (issue_type, stable_key)
        DO UPDATE SET last_seen_at = now(), details = EXCLUDED.details
        """,
        (issue_type, stable_key, source_id, source_tab_id, json.dumps(details, ensure_ascii=False)),
    )
