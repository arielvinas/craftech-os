import copy
import math

import pytest

from craftech_os.ingest import document

# Synthetic grid in the shape the Sheets API returns; every name is fictional.
GRID = {
    "properties": {
        "sheetId": 7,
        "title": "Cobros",
        "hidden": True,
        "gridProperties": {"rowCount": 1000, "columnCount": 26},
    },
    "merges": [{"startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 3}],
    "data": [
        {
            "rowData": [
                {
                    "values": [
                        {
                            "effectiveValue": {"stringValue": "Cliente Ficticio"},
                            "formattedValue": "Cliente Ficticio",
                            "userEnteredValue": {"stringValue": "Cliente Ficticio"},
                            "effectiveFormat": {"backgroundColor": {"red": 1, "green": 0.6}},
                        }
                    ]
                },
                {},
                {
                    "values": [
                        {"effectiveFormat": {"backgroundColor": {"blue": 1}}},
                        {
                            "effectiveValue": {"numberValue": 1500.5},
                            "formattedValue": "$1.500,50",
                            "userEnteredValue": {"formulaValue": "=SUMA(B1:B2)"},
                            "effectiveFormat": {
                                "backgroundColor": {"red": 1, "green": 1, "blue": 1},
                                "numberFormat": {"type": "CURRENCY", "pattern": "$#,##0.00"},
                            },
                        },
                    ]
                },
            ]
        }
    ],
}


def test_build_keeps_non_empty_cells_with_color_format_and_formula():
    doc = document.build(GRID)
    assert doc["sheet_id"] == 7 and doc["title"] == "Cobros" and doc["hidden"] is True
    assert doc["grid"] == {"rows": 1000, "cols": 26}
    assert doc["used"] == {"rows": 3, "cols": 2}
    assert doc["rows"] == [
        {
            "r": 0,
            "cells": [
                {
                    "c": 0,
                    "value": {"stringValue": "Cliente Ficticio"},
                    "text": "Cliente Ficticio",
                    "bg": "#ff9900",
                    "format": None,
                }
            ],
        },
        {
            "r": 2,
            "cells": [
                {
                    "c": 1,
                    "value": {"numberValue": 1500.5},
                    "text": "$1.500,50",
                    "bg": "#ffffff",
                    "format": "$#,##0.00",
                    "formula": "=SUMA(B1:B2)",
                }
            ],
        },
    ]
    assert doc["merges"] == [{"start_row": 0, "end_row": 1, "start_col": 0, "end_col": 3}]
    assert document.cell_count(doc) == 2


def test_cell_without_background_has_null_bg():
    grid = {"data": [{"rowData": [{"values": [{"formattedValue": "x"}]}]}]}
    assert document.build(grid)["rows"][0]["cells"][0]["bg"] is None


def test_data_offsets_are_honored():
    grid = {
        "data": [
            {"startRow": 4, "startColumn": 2, "rowData": [{"values": [{"formattedValue": "x"}]}]}
        ]
    }
    doc = document.build(grid)
    assert doc["rows"] == [
        {"r": 4, "cells": [{"c": 2, "value": None, "text": "x", "bg": None, "format": None}]}
    ]
    assert doc["used"] == {"rows": 5, "cols": 3}


def test_empty_tab():
    doc = document.build({"properties": {"sheetId": 0, "title": "Vacía"}})
    assert doc["rows"] == [] and doc["merges"] == [] and doc["used"] == {"rows": 0, "cols": 0}
    assert document.cell_count(doc) == 0


def test_hash_does_not_depend_on_key_order_and_changes_with_content():
    a = document.canonical({"b": 1, "a": {"y": 2, "x": "ñ"}})
    b = document.canonical({"a": {"x": "ñ", "y": 2}, "b": 1})
    assert a == b == '{"a":{"x":"ñ","y":2},"b":1}'
    assert document.content_hash(a) == document.content_hash(b)
    assert len(document.content_hash(a)) == 64
    assert document.content_hash(a) != document.content_hash(document.canonical({"b": 2}))


def test_one_changed_color_changes_the_hash():
    changed = copy.deepcopy(GRID)
    base = document.content_hash(document.canonical(document.build(changed)))
    changed["data"][0]["rowData"][0]["values"][0]["effectiveFormat"]["backgroundColor"] = {"red": 1}
    assert document.content_hash(document.canonical(document.build(changed))) != base


@pytest.mark.parametrize("bad", [math.nan, math.inf, {1, 2}, b"x"])
def test_non_serializable_content_is_an_error(bad):
    with pytest.raises((ValueError, TypeError)):
        document.canonical({"value": bad})


PAINTED = {
    "data": [
        {
            "rowData": [
                {
                    "values": [
                        {"effectiveFormat": {"backgroundColor": {"red": 1, "green": 0.6}}},
                        {"effectiveFormat": {"backgroundColor": {"red": 1, "green": 1, "blue": 1}}},
                        {"effectiveFormat": {}},
                        {},
                    ]
                }
            ]
        }
    ]
}


def test_a_painted_empty_cell_is_kept_as_its_color_only_when_asked():
    doc = document.build(PAINTED, keep_color_only=True)
    assert doc["rows"] == [{"r": 0, "cells": [{"c": 0, "bg": "#ff9900"}]}]
    assert doc["used"] == {"rows": 1, "cols": 1}
    assert document.build(PAINTED)["rows"] == []
