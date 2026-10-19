"""The diff algorithm on synthetic documents: invented clients and amounts only."""

import pytest

from craftech_os.diff.compare import a1, column_index, column_letters, compare, normalize

SCHEMA = {"header": "Cliente", "key": "A", "blocks": ["General", "Total Ingresos"], "grid": "B:D"}


def _cell(c, text, bg=None, formula=None):
    cell = {"c": c, "value": {"stringValue": text}, "text": text, "bg": bg, "format": None}
    if formula is not None:
        cell["formula"] = formula
    return cell


def _doc(*rows):
    """Each row is a list of texts from column A; None leaves the cell empty."""
    built = [
        {"r": r, "cells": [_cell(c, t) for c, t in enumerate(texts) if t is not None]}
        for r, texts in enumerate(rows)
    ]
    built = [row for row in built if row["cells"]]
    return {
        "rows": built,
        "used": {"rows": len(rows), "cols": max((len(t) for t in rows), default=0)},
    }


BASE = [
    ["Título ficticio"],
    ["Cliente", "ene", "feb", "mar"],
    ["General"],
    ["Cliente A", "100", "200", "300"],
    ["Cliente B", "10", "20", "30"],
    ["Total Ingresos", "110", "220", "330"],
]


def _types(result):
    return sorted(c["change_type"] for c in result["changes"])


def _cell_at(doc, r, c):
    return next(x for row in doc["rows"] if row["r"] == r for x in row["cells"] if x["c"] == c)


def test_a1_helpers():
    assert [column_index(x) for x in ("A", "Z", "AA", "AM")] == [0, 25, 26, 38]
    assert [column_letters(i) for i in (0, 25, 26, 38)] == ["A", "Z", "AA", "AM"]
    assert a1(16, 3) == "D17"
    with pytest.raises(ValueError):
        column_index("a1")


def test_normalize_drops_case_accents_and_double_spaces():
    assert normalize("  Cliente   ÁÉ ñu ") == "cliente ae nu"


def test_identical_documents_have_no_changes():
    assert compare(_doc(*BASE), _doc(*BASE), SCHEMA) == {
        "changes": [],
        "ambiguous": [],
        "positional": False,
    }


def test_a_row_inserted_above_a_block_is_one_row_inserted_and_no_value():
    new = BASE[:3] + [["Cliente C", "1", "2", "3"]] + BASE[3:]
    result = compare(_doc(*BASE), _doc(*new), SCHEMA)
    assert _types(result) == ["row_inserted"]
    (change,) = result["changes"]
    assert (change["block"], change["row_key"], change["row_ordinal"]) == (
        "General",
        "cliente c",
        1,
    )
    assert change["cell_ref"] is None


def test_a_deleted_row_is_one_row_deleted():
    new = [row for row in BASE if row[0] != "Cliente A"]
    result = compare(_doc(*BASE), _doc(*new), SCHEMA)
    assert _types(result) == ["row_deleted"]
    assert result["changes"][0]["row_key"] == "cliente a"


def test_a_moved_row_is_one_row_moved_and_nothing_else():
    old = BASE[:3] + [["Cliente Ánfora", "1", "2", "3"]] + BASE[3:]
    new = BASE[:5] + [["Cliente Ánfora", "1", "2", "3"]] + BASE[5:]
    result = compare(_doc(*old), _doc(*new), SCHEMA)
    assert _types(result) == ["row_moved"]
    (change,) = result["changes"]
    assert (change["row_key"], change["old_value"], change["new_value"]) == (
        "cliente anfora",
        "4",
        "6",
    )


def test_a_moved_row_respelled_still_aligns_by_normalized_key():
    old = BASE[:3] + [["Cliente  Ánfora", "1", "2", "3"]] + BASE[3:]
    new = BASE[:5] + [["cliente anfora", "1", "2", "3"]] + BASE[5:]
    result = compare(_doc(*old), _doc(*new), SCHEMA)
    assert _types(result) == ["row_moved", "value"]
    assert result["ambiguous"] == []
    value = next(c for c in result["changes"] if c["change_type"] == "value")
    assert value["cell_ref"] == "A6"


def test_a_value_change_in_an_aligned_row_points_at_the_new_cell():
    new = BASE[:3] + [["Cliente C"], ["Cliente A", "100", "999", "300"]] + BASE[4:]
    result = compare(_doc(*BASE), _doc(*new), SCHEMA)
    assert _types(result) == ["row_inserted", "value"]
    value = next(c for c in result["changes"] if c["change_type"] == "value")
    assert (value["cell_ref"], value["old_value"], value["new_value"]) == ("C5", "200", "999")
    assert value["row_key"] == "cliente a"


def test_a_color_change_has_both_hexadecimals():
    old, new = _doc(*BASE), _doc(*BASE)
    _cell_at(old, 3, 1)["bg"] = "#ff9900"
    _cell_at(new, 3, 1)["bg"] = "#d9ead3"
    (change,) = compare(old, new, SCHEMA)["changes"]
    assert (change["change_type"], change["cell_ref"]) == ("color", "B4")
    assert (change["old_color"], change["new_color"]) == ("#ff9900", "#d9ead3")


def test_a_value_and_its_color_changing_together_are_two_changes():
    old, new = _doc(*BASE), _doc(*BASE)
    _cell_at(new, 3, 1).update(text="101", bg="#ff00ff")
    assert _types(compare(old, new, SCHEMA)) == ["color", "value"]


def test_painting_or_unpainting_an_empty_cell_is_a_color_change():
    old, new = _doc(*BASE), _doc(*BASE)
    next(row for row in new["rows"] if row["r"] == 2)["cells"].append({"c": 1, "bg": "#ff9900"})
    (change,) = compare(old, new, SCHEMA)["changes"]
    assert (change["change_type"], change["cell_ref"]) == ("color", "B3")
    assert (change["old_color"], change["new_color"]) == (None, "#ff9900")
    (change,) = compare(new, old, SCHEMA)["changes"]
    assert (change["old_color"], change["new_color"]) == ("#ff9900", None)


def test_emptying_a_cell_is_emptied():
    new = [list(row) for row in BASE]
    new[4][2] = None
    (change,) = compare(_doc(*BASE), _doc(*new), SCHEMA)["changes"]
    assert (change["change_type"], change["cell_ref"], change["old_value"]) == (
        "emptied",
        "C5",
        "20",
    )


def test_a_formula_replaced_by_a_number_is_formula_overridden():
    old, new = _doc(*BASE), _doc(*BASE)
    _cell_at(old, 5, 1)["formula"] = "=SUM(B4:B5)"
    _cell_at(new, 5, 1)["text"] = "1234"
    (change,) = compare(old, new, SCHEMA)["changes"]
    assert change["change_type"] == "formula_overridden"
    assert (change["old_formula"], change["old_value"], change["new_value"]) == (
        "=SUM(B4:B5)",
        "110",
        "1234",
    )


def test_a_changed_formula_is_formula():
    old, new = _doc(*BASE), _doc(*BASE)
    _cell_at(old, 5, 1)["formula"] = "=SUM(B4:B5)"
    _cell_at(new, 5, 1)["formula"] = "=SUM(B4:B6)"
    assert _types(compare(old, new, SCHEMA)) == ["formula"]


def test_float_noise_with_the_same_text_is_not_a_change():
    old, new = _doc(*BASE), _doc(*BASE)
    _cell_at(old, 5, 1)["value"] = {"numberValue": 110.00000003}
    _cell_at(new, 5, 1)["value"] = {"numberValue": 110.00000001}
    assert compare(old, new, SCHEMA)["changes"] == []


def test_two_rows_with_the_same_key_are_followed_in_order():
    old = BASE[:5] + [["Cliente A", "1", "2", "3"]] + BASE[5:]
    new = BASE[:5] + [["Cliente A", "1", "7", "3"]] + BASE[5:]
    result = compare(_doc(*old), _doc(*new), SCHEMA)
    (change,) = result["changes"]
    assert (change["change_type"], change["row_key"], change["row_ordinal"]) == (
        "value",
        "cliente a",
        2,
    )
    assert result["ambiguous"] == []


def test_a_third_repeated_key_is_ambiguous_and_compared_by_position():
    old = BASE[:5] + [["Cliente A", "1", "2", "3"]] + BASE[5:]
    new = BASE[:5] + [["Cliente A", "1", "2", "3"], ["Cliente A", "4", "5", "6"]] + BASE[5:]
    result = compare(_doc(*old), _doc(*new), SCHEMA)
    assert result["ambiguous"] == [("General", "cliente a")]
    assert "row_inserted" in _types(result)


def test_a_row_that_changes_key_and_place_is_ambiguous():
    old = BASE[:3] + [["Cliente C", "1"]] + BASE[3:]
    new = BASE[:5] + [["Cliente D", "1"]] + BASE[5:]
    result = compare(_doc(*old), _doc(*new), SCHEMA)
    assert sorted(result["ambiguous"]) == [("General", "cliente c"), ("General", "cliente d")]


def test_rows_without_key_align_by_position_inside_their_block():
    old = BASE[:5] + [[None, "nota"]] + BASE[5:]
    new = BASE[:5] + [[None, "nota 2"]] + BASE[5:]
    (change,) = compare(_doc(*old), _doc(*new), SCHEMA)["changes"]
    assert (change["change_type"], change["cell_ref"], change["row_key"]) == ("value", "B6", None)


def test_a_new_header_is_column_inserted_and_the_rest_still_aligns():
    new = [list(row) for row in BASE]
    for row in new[1:]:
        if len(row) > 1:
            row.insert(2, None)
    new[1][2] = "ene bis"
    result = compare(_doc(*BASE), _doc(*new), SCHEMA)
    (change,) = result["changes"]
    assert (change["change_type"], change["cell_ref"], change["new_value"]) == (
        "column_inserted",
        "C2",
        "ene bis",
    )


def test_a_repeated_block_header_gets_a_number():
    doc = BASE + [["General"], ["Cliente A", "5"]]
    new = BASE + [["General"], ["Cliente A", "6"]]
    (change,) = compare(_doc(*doc), _doc(*new), SCHEMA)["changes"]
    assert (change["block"], change["row_key"], change["row_ordinal"]) == (
        "General (2)",
        "cliente a",
        1,
    )


def test_without_schema_cells_compare_by_position():
    new = [list(row) for row in BASE]
    new[3][1] = "101"
    result = compare(_doc(*BASE), _doc(*new), None)
    (change,) = result["changes"]
    assert (change["change_type"], change["cell_ref"], change["row_key"], change["block"]) == (
        "value",
        "B4",
        None,
        None,
    )
    assert result["positional"] is False


def test_a_schema_whose_header_is_gone_falls_back_to_positions():
    new = [list(row) for row in BASE]
    new[1][0] = "Clientes"
    result = compare(_doc(*BASE), _doc(*new), SCHEMA)
    assert result["positional"] is True
    assert _types(result) == ["value"]


def _with_formulas(rows):
    """Column D of each client row is =B+C of its own row."""
    doc = _doc(*rows)
    for row in doc["rows"]:
        if normalize(row["cells"][0]["text"]).startswith("cliente "):
            _cell_at(doc, row["r"], 3)["formula"] = f"=B{row['r'] + 1}+$C${row['r'] + 1}"
    return doc


def _total(doc, r, own, other):
    """The total row sums the clients of this tab and of another one."""
    _cell_at(doc, r, 1)["formula"] = f"=SUM(B{own})"
    _cell_at(doc, r, 2)["formula"] = f"=SUM('Otra pestaña'!C{other})+ROUND(1.5,0)"


def test_a_row_inserted_above_formulas_does_not_change_them():
    new = BASE[:3] + [["Cliente C", "1", "2", "3"]] + BASE[3:]
    old_doc, new_doc = _with_formulas(BASE), _with_formulas(new)
    _total(old_doc, 5, "4:B5", "4:C5")
    # Google shifts the references of this tab, not those to another tab.
    _total(new_doc, 6, "5:B6", "4:C5")
    assert _types(compare(old_doc, new_doc, SCHEMA)) == ["row_inserted"]


def test_a_deleted_row_does_not_change_the_formulas_below():
    old = BASE[:3] + [["Cliente C", "1", "2", "3"]] + BASE[3:]
    old_doc, new_doc = _with_formulas(old), _with_formulas(BASE)
    _total(old_doc, 6, "4:B6", "4:C5")
    _total(new_doc, 5, "4:B5", "4:C5")
    assert _types(compare(old_doc, new_doc, SCHEMA)) == ["row_deleted"]


def test_deleting_the_last_row_of_a_range_shrinks_it():
    old = BASE[:5] + [["Cliente C", "1", "2", "3"]] + BASE[5:]
    old_doc, new_doc = _with_formulas(old), _with_formulas(BASE)
    _total(old_doc, 6, "4:B6", "4:C5")
    _total(new_doc, 5, "4:B5", "4:C5")
    assert _types(compare(old_doc, new_doc, SCHEMA)) == ["row_deleted"]


def test_a_formula_pointing_at_a_painted_empty_row_does_not_change():
    rows = BASE[:5] + [[None]] + BASE[5:]
    docs = []
    for _ in range(2):
        doc = _doc(*rows)
        doc["rows"].append({"r": 5, "cells": [{"c": 1, "bg": "#ff9900"}]})
        _cell_at(doc, 6, 1)["formula"] = "=B6"
        docs.append(doc)
    assert compare(*docs, SCHEMA)["changes"] == []


def test_a_column_inserted_before_formulas_does_not_change_them():
    new = [list(row) for row in BASE]
    for row in new[1:]:
        if len(row) > 1:
            row.insert(1, None)
    new[1][1] = "dic"
    old_doc, new_doc = _with_formulas(BASE), _doc(*new)
    for row in new_doc["rows"]:
        if normalize(row["cells"][0]["text"]).startswith("cliente "):
            _cell_at(new_doc, row["r"], 4)["formula"] = f"=C{row['r'] + 1}+$D${row['r'] + 1}"
    assert _types(compare(old_doc, new_doc, SCHEMA)) == ["column_inserted"]


def test_a_formula_edited_after_a_row_insert_is_still_a_formula_change():
    new = BASE[:3] + [["Cliente C", "1", "2", "3"]] + BASE[3:]
    old_doc, new_doc = _with_formulas(BASE), _with_formulas(new)
    _cell_at(new_doc, 5, 3)["formula"] = "=B6*2"
    result = compare(old_doc, new_doc, SCHEMA)
    assert _types(result) == ["formula", "row_inserted"]
    change = next(c for c in result["changes"] if c["change_type"] == "formula")
    assert (change["cell_ref"], change["old_formula"], change["new_formula"]) == (
        "D6",
        "=B5+$C$5",
        "=B6*2",
    )


def test_a_formula_still_pointing_at_the_old_row_number_is_a_change():
    new = BASE[:3] + [["Cliente C", "1", "2", "3"]] + BASE[3:]
    old_doc, new_doc = _with_formulas(BASE), _with_formulas(new)
    _total(old_doc, 5, "4:B5", "4:C5")
    _total(new_doc, 6, "4:B5", "4:C5")
    assert _types(compare(old_doc, new_doc, SCHEMA)) == ["formula", "row_inserted"]


def test_a_gap_with_a_different_number_of_new_keys_is_ambiguous():
    old = BASE[:4] + [["Cliente C", "1"], ["Cliente D", "2"]] + BASE[4:]
    new = BASE[:4] + [["Cliente E", "3"]] + BASE[4:]
    result = compare(_doc(*old), _doc(*new), SCHEMA)
    assert sorted(key for _, key in result["ambiguous"]) == ["cliente c", "cliente d", "cliente e"]
    assert _types(result) == ["row_deleted", "value", "value"]


def test_an_insert_and_a_delete_in_the_same_block_are_not_ambiguous():
    old = BASE[:5] + [["Cliente D", "4", "5", "6"]] + BASE[5:]
    new = BASE[:3] + [["Cliente C", "1", "2", "3"]] + BASE[3:5] + BASE[5:]
    result = compare(_doc(*old), _doc(*new), SCHEMA)
    assert result["ambiguous"] == []
    assert _types(result) == ["row_deleted", "row_inserted"]
