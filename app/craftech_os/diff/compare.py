"""Cell-by-cell changes between two snapshot documents of one tab. Pure: no database.

With a schema, rows are grouped in blocks and aligned by their normalized key inside each
block; without one, cells are compared by position. When the alignment of a key is
ambiguous it is not guessed: its rows are compared by position and the key is reported.
"""

import json
import re
import unicodedata
from bisect import bisect_left
from collections import Counter
from collections.abc import Callable
from difflib import SequenceMatcher

BEFORE_HEADER = "(antes del encabezado)"
COLUMN = re.compile(r"^[A-Z]{1,3}$")
CELL = r"\$?[A-Z]{1,3}\$?[0-9]+"
# A quoted string, or a cell or range reference with its optional sheet prefix.
REFERENCE = re.compile(
    rf"""("[^"]*")|(?<![\w.$])((?:'[^']*'|[\w.]+)!)?({CELL}(?::{CELL})?)(?![\w(])"""
)
CELL_PARTS = re.compile(r"(\$?)([A-Z]{1,3})(\$?)([0-9]+)")


def normalize(text: str) -> str:
    """Lowercase, without accents, with single spaces and no surrounding blanks."""
    decomposed = unicodedata.normalize("NFKD", text)
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(plain.lower().split())


def column_index(letters: str) -> int:
    """A -> 0, Z -> 25, AA -> 26."""
    if not COLUMN.match(letters):
        raise ValueError(f"not a column: {letters!r}")
    index = 0
    for ch in letters:
        index = index * 26 + ord(ch) - ord("A") + 1
    return index - 1


def column_letters(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(ord("A") + rest) + letters
    return letters


def a1(r: int, c: int) -> str:
    return f"{column_letters(c)}{r + 1}"


def value(cell: dict | None) -> str | None:
    """What the cell shows: its formatted text, else its raw value; None when empty."""
    if cell is None:
        return None
    if cell.get("text") not in (None, ""):
        return cell["text"]
    if cell.get("value"):
        return json.dumps(cell["value"], sort_keys=True, ensure_ascii=False)
    return None


def _change(change_type: str, **fields) -> dict:
    change = dict.fromkeys(
        (
            "block",
            "row_key",
            "row_ordinal",
            "cell_ref",
            "old_value",
            "new_value",
            "old_formula",
            "new_formula",
            "old_color",
            "new_color",
        )
    )
    change.update(fields, change_type=change_type)
    return change


def cell_changes(
    old: dict | None, new: dict | None, ref: str | None, moved=lambda formula: formula, **row
) -> list[dict]:
    """Changes of one aligned cell. Values are compared as shown, so float noise is ignored.

    moved rewrites the old formula as Google would after the rows and columns that were
    inserted or deleted, so a shifted reference is not a change.
    """
    ov, nv = value(old), value(new)
    of = old.get("formula") if old else None
    nf = new.get("formula") if new else None
    out = []
    if ov is not None and nv is None:
        out.append(
            _change(
                "emptied",
                cell_ref=ref,
                old_value=ov,
                old_formula=of,
                old_color=old.get("bg"),
                **row,
            )
        )
        return out
    if of is not None and nf is None and nv is not None:
        out.append(
            _change(
                "formula_overridden",
                cell_ref=ref,
                old_value=ov,
                new_value=nv,
                old_formula=of,
                **row,
            )
        )
    else:
        if (moved(of) if of is not None else None) != nf:
            out.append(_change("formula", cell_ref=ref, old_formula=of, new_formula=nf, **row))
        if ov != nv:
            out.append(_change("value", cell_ref=ref, old_value=ov, new_value=nv, **row))
    if old is not None and new is not None and old.get("bg") != new.get("bg"):
        out.append(
            _change("color", cell_ref=ref, old_color=old.get("bg"), new_color=new.get("bg"), **row)
        )
    return out


def _grid(doc: dict) -> dict[int, dict[int, dict]]:
    return {row["r"]: {cell["c"]: cell for cell in row["cells"]} for row in doc["rows"]}


def _positional(old_doc: dict, new_doc: dict) -> list[dict]:
    old, new = _grid(old_doc), _grid(new_doc)
    changes = []
    for r in sorted(old.keys() | new.keys()):
        o, n = old.get(r, {}), new.get(r, {})
        for c in sorted(o.keys() | n.keys()):
            changes += cell_changes(o.get(c), n.get(c), a1(r, c))
    return changes


def blocks(doc: dict, schema: dict) -> tuple[int, list[tuple[str, list[dict]]]] | None:
    """(header row, [(block name, rows)]), or None when the header row is not there.

    Each row is {r, cells: {c: cell}, key, ordinal}. The header row opens the block named
    after the header; each row whose key is a declared block opens a block with that name.
    """
    key_c = column_index(schema["key"])
    header = normalize(schema["header"])
    openers = {normalize(b): b for b in schema.get("blocks", [])}
    rows = []
    for row in sorted(doc["rows"], key=lambda row: row["r"]):
        cells = {cell["c"]: cell for cell in row["cells"]}
        key = normalize(value(cells.get(key_c)) or "") or None
        rows.append({"r": row["r"], "cells": cells, "key": key})
    header_r = next((row["r"] for row in rows if row["key"] == header), None)
    if header_r is None:
        return None
    split, names = [(BEFORE_HEADER, [])], Counter()
    for row in rows:
        name = None
        if row["r"] == header_r:
            name = schema["header"]
        elif row["r"] > header_r and row["key"] in openers:
            name = openers[row["key"]]
        if name is not None:
            names[name] += 1
            split.append((name if names[name] == 1 else f"{name} ({names[name]})", []))
        split[-1][1].append(row)
    for _, block_rows in split:
        seen = Counter()
        for row in block_rows:
            seen[row["key"]] += 1
            row["ordinal"] = seen[row["key"]] if row["key"] is not None else None
    return header_r, split


def _columns(old_header: dict, new_header: dict, width: int):
    """Map old columns to new ones by their header text. Returns (map, inserted columns).

    An old column left out of the map was deleted.
    """
    old = [normalize(value(old_header.get(c)) or "") for c in range(width)]
    new = [normalize(value(new_header.get(c)) or "") for c in range(width)]
    mapping, inserted = {}, []
    matcher = SequenceMatcher(None, old, new, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        paired = min(i2 - i1, j2 - j1) if tag in ("equal", "replace") else 0
        for k in range(paired):
            mapping[i1 + k] = j1 + k
        inserted += range(j1 + paired, j2)
    return mapping, inserted


def _content(row: dict, key_c: int) -> tuple:
    """What a row shows besides its key, ignoring columns."""
    return tuple(sorted(v for c, cell in row["cells"].items() if c != key_c and (v := value(cell))))


def _align(old_rows: list[dict], new_rows: list[dict], key_c: int):
    """Pair the rows of one block. Returns (pairs, moved, ambiguous keys).

    pairs are (old, new) with None on the missing side; moved holds the ids of new rows whose
    key is in a different order than before.
    """
    old_count = Counter(row["key"] for row in old_rows if row["key"] is not None)
    new_count = Counter(row["key"] for row in new_rows if row["key"] is not None)
    ambiguous = {k for k in old_count.keys() & new_count.keys() if old_count[k] != new_count[k]}

    def anchor(row):
        if row["key"] is None or row["key"] in ambiguous:
            return None
        return row["key"], row["ordinal"]

    old_anchors = {anchor(row) for row in old_rows} - {None}
    new_anchors = {anchor(row) for row in new_rows} - {None}
    common = old_anchors & new_anchors
    old_order = [anchor(row) for row in old_rows if anchor(row) in common]
    new_order = [anchor(row) for row in new_rows if anchor(row) in common]
    matcher = SequenceMatcher(None, old_order, new_order, autojunk=False)
    in_order = {old_order[b.a + k] for b in matcher.get_matching_blocks() for k in range(b.size)}
    by_anchor = {anchor(row): row for row in old_rows if anchor(row) in common}
    pairs, moved = [], set()
    for row in new_rows:
        if anchor(row) in common and anchor(row) not in in_order:
            pairs.append((by_anchor[anchor(row)], row))
            moved.add(id(row))

    # Walk the rows between consecutive in-order anchors (and after the last one).
    def gaps(rows):
        gap = []
        for row in rows:
            a = anchor(row)
            if a in in_order:
                yield gap, a
                gap = []
            elif a not in common:
                gap.append(row)
        yield gap, None

    leftovers_old, leftovers_new = [], []
    for (old_gap, a), (new_gap, _) in zip(gaps(old_rows), gaps(new_rows), strict=True):
        old_pos = [row for row in old_gap if anchor(row) is None]
        new_pos = [row for row in new_gap if anchor(row) is None]
        old_keyed = [row for row in old_gap if anchor(row) is not None]
        new_keyed = [row for row in new_gap if anchor(row) is not None]
        if old_keyed and new_keyed and len(old_keyed) != len(new_keyed):
            ambiguous |= {row["key"] for row in old_keyed + new_keyed}
            old_pos, new_pos = old_gap, new_gap
        elif old_keyed and new_keyed:
            # Keys renamed in place: the same number of rows went out and came in.
            pairs += zip(old_keyed, new_keyed, strict=True)
        else:
            leftovers_old += old_keyed
            leftovers_new += new_keyed
        paired = min(len(old_pos), len(new_pos))
        pairs += zip(old_pos[:paired], new_pos[:paired], strict=True)
        pairs += [(row, None) for row in old_pos[paired:]]
        pairs += [(None, row) for row in new_pos[paired:]]
        if a is not None:
            pairs.append((by_anchor[a], next(row for row in new_rows if anchor(row) == a)))
    gone = {_content(row, key_c) for row in leftovers_old} - {()}
    if any(_content(row, key_c) in gone for row in leftovers_new):
        # A key gone here and a new key with the same content there: maybe one row changed
        # key and place at once.
        ambiguous |= {row["key"] for row in leftovers_old + leftovers_new}
    pairs += [(row, None) for row in leftovers_old]
    pairs += [(None, row) for row in leftovers_new]
    return pairs, moved, ambiguous


def _shift(exact: dict[int, int], anchors: dict[int, int], present) -> Callable[[int], int]:
    """Old index -> new index of a row or column, for references in formulas.

    exact holds every aligned index; anchors the ones that kept their order. An index with no
    pair lands where Google puts it: just before the next anchor, counting the empty indexes
    in between (a deleted one takes the place of the next survivor).
    """
    olds = sorted(anchors)

    def move(x: int) -> int:
        if x in exact:
            return exact[x]
        i = bisect_left(olds, x)
        if i == len(olds):
            return x + (anchors[olds[-1]] - olds[-1] if olds else 0)
        return anchors[olds[i]] - sum(1 for y in range(x, olds[i]) if y not in present)

    return move


def _moved_formula(move_row, move_column):
    def cell(m: re.Match) -> str:
        col_abs, letters, row_abs, number = m.groups()
        c = move_column(column_index(letters))
        return f"{col_abs}{column_letters(c)}{row_abs}{move_row(int(number) - 1) + 1}"

    def reference(m: re.Match) -> str:
        if m.group(1) or m.group(2):
            # A text, or a reference to another tab: Google leaves it as it was.
            return m.group(0)
        return CELL_PARTS.sub(cell, m.group(0))

    return lambda formula: REFERENCE.sub(reference, formula)


def _row_fields(block: str, row: dict) -> dict:
    return {"block": block, "row_key": row["key"], "row_ordinal": row["ordinal"]}


def _schema_changes(old_doc: dict, new_doc: dict, schema: dict):
    old_split, new_split = blocks(old_doc, schema), blocks(new_doc, schema)
    if old_split is None or new_split is None:
        return None
    (old_header_r, old_blocks), (new_header_r, new_blocks) = old_split, new_split
    width = max(old_doc["used"]["cols"], new_doc["used"]["cols"])
    old_header = next(
        row["cells"] for _, rows in old_blocks for row in rows if row["r"] == old_header_r
    )
    new_header = next(
        row["cells"] for _, rows in new_blocks for row in rows if row["r"] == new_header_r
    )
    columns, inserted = _columns(old_header, new_header, width)
    inverse = {n: o for o, n in columns.items()}
    changes = [
        _change(
            "column_inserted",
            block=schema["header"],
            cell_ref=a1(new_header_r, c),
            new_value=value(new_header.get(c)),
        )
        for c in inserted
        if value(new_header.get(c)) is not None
    ]
    ambiguous, aligned = [], []
    old_by_name, new_by_name = dict(old_blocks), dict(new_blocks)
    for name in [n for n, _ in old_blocks] + [n for n, _ in new_blocks if n not in old_by_name]:
        pairs, moved, keys = _align(
            old_by_name.get(name, []), new_by_name.get(name, []), column_index(schema["key"])
        )
        ambiguous += [(name, key) for key in sorted(keys)]
        aligned += [(name, old, new, id(new) in moved) for old, new in pairs]
    rows = {old["r"]: new["r"] for _, old, new, _ in aligned if old and new}
    in_place = {old["r"]: new["r"] for _, old, new, m in aligned if old and new and not m}
    present = {row["r"] for row in old_doc["rows"]}
    moved_formula = _moved_formula(
        _shift(rows, in_place, present), _shift(columns, columns, range(width))
    )
    for name, old, new, is_moved in aligned:
        if new is None:
            changes.append(
                _change("row_deleted", old_value=str(old["r"] + 1), **_row_fields(name, old))
            )
            continue
        fields = _row_fields(name, new)
        if old is None:
            changes.append(_change("row_inserted", new_value=str(new["r"] + 1), **fields))
            continue
        if is_moved:
            changes.append(
                _change(
                    "row_moved",
                    old_value=str(old["r"] + 1),
                    new_value=str(new["r"] + 1),
                    **fields,
                )
            )
        targets = {columns[c] for c in old["cells"] if c in columns}
        targets |= {c for c in new["cells"] if c in inverse}
        for c in sorted(targets):
            old_cell = old["cells"].get(inverse[c])
            changes += cell_changes(
                old_cell, new["cells"].get(c), a1(new["r"], c), moved_formula, **fields
            )
        for c, cell in old["cells"].items():
            if c not in columns:
                # Its column is gone: the cell has no place in the new version.
                changes += cell_changes(cell, None, None, **_row_fields(name, old))
    return changes, ambiguous


def compare(old_doc: dict, new_doc: dict, schema: dict | None) -> dict:
    """{changes, ambiguous: [(block, key)], positional: bool} between two documents.

    positional is True when the tab has a schema but its header row is not in one of the
    documents: the comparison fell back to positions.
    """
    if schema:
        result = _schema_changes(old_doc, new_doc, schema)
        if result is not None:
            changes, ambiguous = result
            return {"changes": changes, "ambiguous": ambiguous, "positional": False}
    return {
        "changes": _positional(old_doc, new_doc),
        "ambiguous": [],
        "positional": bool(schema),
    }
