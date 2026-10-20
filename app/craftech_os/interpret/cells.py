"""Reading a month grid: the month of a header cell, the date and the number of a cell."""

from datetime import date, timedelta
from decimal import Decimal

from craftech_os.diff.compare import blocks, column_index, value

# Day zero of the Google Sheets date serials.
EPOCH = date(1899, 12, 30)
# Serial of 9999-12-31, the last day a date can hold.
MAX_SERIAL = (date.max - EPOCH).days


def day(cell: dict | None) -> date | None:
    """The date of a cell holding one, else None.

    A date is a number shown with a year; a plain number such as 2025 is not one.
    """
    serial = ((cell or {}).get("value") or {}).get("numberValue")
    if serial is None or "yy" not in (cell.get("format") or "").lower():
        return None
    if not 0 <= serial <= MAX_SERIAL:
        return None
    return EPOCH + timedelta(days=int(serial))


def month(cell: dict | None) -> date | None:
    """The first day of the month of a header cell holding a date, else None."""
    found = day(cell)
    return found and found.replace(day=1)


def number(cell: dict) -> Decimal | None:
    """The number of the cell as Google stored it, without float noise; None if not a number."""
    raw = (cell.get("value") or {}).get("numberValue")
    return None if raw is None else Decimal(repr(raw))


def unreadable(cell: dict) -> bool:
    """True if the cell holds something that is not a number: a text, an error, a boolean."""
    return number(cell) is None and bool(cell.get("value")) and bool((value(cell) or "").strip())


def grid(doc: dict, schema: dict):
    """(blocks, header row cells, grid columns, {column: month}), or None without header.

    A month repeated in the header belongs to its first column only.
    """
    split = blocks(doc, schema)
    if split is None:
        return None
    header_r, tab_blocks = split
    first, last = (column_index(x) for x in schema["grid"].split(":"))
    header = next(row for _, rows in tab_blocks for row in rows if row["r"] == header_r)
    columns = range(first, last + 1)
    months = {}
    for c in columns:
        if (m := month(header["cells"].get(c))) and m not in months.values():
            months[c] = m
    return tab_blocks, header, columns, months
