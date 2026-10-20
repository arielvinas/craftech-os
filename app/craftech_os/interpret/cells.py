"""Reading a month grid: the month of a header cell and the number of a cell."""

from datetime import date, timedelta
from decimal import Decimal

from craftech_os.diff.compare import blocks, column_index, value

# Day zero of the Google Sheets date serials.
EPOCH = date(1899, 12, 30)


def month(cell: dict | None) -> date | None:
    """The first day of the month of a header cell holding a date, else None."""
    serial = ((cell or {}).get("value") or {}).get("numberValue")
    if serial is None:
        return None
    return (EPOCH + timedelta(days=int(serial))).replace(day=1)


def number(cell: dict) -> Decimal | None:
    """The number of the cell as Google stored it, without float noise; None if not a number."""
    raw = (cell.get("value") or {}).get("numberValue")
    return None if raw is None else Decimal(repr(raw))


def unreadable(cell: dict) -> bool:
    """True if the cell holds something that is not a number: a text, an error, a boolean."""
    return number(cell) is None and bool(cell.get("value")) and bool((value(cell) or "").strip())


def grid(doc: dict, schema: dict):
    """(blocks, header row cells, grid columns, {column: month}), or None without header."""
    split = blocks(doc, schema)
    if split is None:
        return None
    header_r, tab_blocks = split
    first, last = (column_index(x) for x in schema["grid"].split(":"))
    header = next(row for _, rows in tab_blocks for row in rows if row["r"] == header_r)
    columns = range(first, last + 1)
    months = {c: m for c in columns if (m := month(header["cells"].get(c)))}
    return tab_blocks, header, columns, months
