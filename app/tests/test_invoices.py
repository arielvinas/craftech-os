"""Invoices, payments and churn of Pagos and Pagos ARG, interpreted on each import.

Against the test database. Invented names and amounts only.
"""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from test_diff_store import ORANGE, SALMON, _rgb, _value
from test_import import FakeGoogle
from test_interpret import FEB, JAN, MAR, MONTHS, _import, _issues, _set, _sheet

from craftech_os import cli
from craftech_os.migrate import migrate

SOURCES = """
sources:
  - title: "Facturación Ficticia"
    drive_id: "file-a"
    tabs:
      CARGA: ["Pagos", "Pagos ARG"]
    schemas:
      "Pagos":
        header: "Cliente"
        key: A
        blocks: ["General", "Funding de AWS confirmados", "Total Ingresos"]
        grid: "D:F"
      "Pagos ARG":
        header: "Mes"
        key: A
        blocks: ["Total Ingresos", "Mes"]
        grid: "B:D"
  - title: "Facturación SleakOps Ficticia"
    drive_id: "file-s"
    tabs:
      CARGA: ["Pagos"]
    schemas:
      "Pagos":
        header: "Cliente"
        key: A
        blocks: ["Fundings de AWS", "General", "Total Ingresos"]
        grid: "D:F"
"""
CYAN, BLUE, GREEN, MAGENTA, WHITE = "#00ffff", "#4a86e8", "#d9ead3", "#ff00ff", "#ffffff"


def _formula(number, formula, bg=None):
    """A cell computed by a formula, as Google returns it."""
    cell = {
        "effectiveValue": {"numberValue": number},
        "formattedValue": str(number),
        "userEnteredValue": {"formulaValue": formula},
    }
    if bg:
        cell["effectiveFormat"] = {"backgroundColor": _rgb(bg)}
    return cell


PAGOS = [
    ["Total pagos USA", None, None, "6300", "2700", "2900"],
    ["Cliente", "Generado por", "Servicio", *MONTHS],
    [
        "Cliente Uno",
        "Alguien",
        "Servicio",
        _value("1100", CYAN),
        _value("1200", BLUE),
        _value("1300", ORANGE),
    ],
    [
        "Cliente Dos",
        "Alguien",
        "Marketplace",
        _value("1400", GREEN),
        _value("1500", MAGENTA),
        _value("1600", WHITE),
    ],
    ["Cliente Tres", "Alguien", "Servicio", "1700", "sin dato", _value("1800", SALMON)],
    # A zero with color, magenta without amount and a copy of Pagos ARG: no invoice here.
    [
        "Cliente Cuatro",
        "Alguien",
        "Servicio",
        _value("0", GREEN),
        _value(None, MAGENTA),
        _formula(1900, "='Pagos ARG'!B3", GREEN),
    ],
    ["Cliente Uno", "Alguien", "Soporte", _value("2100", BLUE)],
    ["General"],
    ["Cliente Seis", "Alguien", "Servicio", _value("2200", GREEN)],
    ["Total Ingresos", None, None, "6300", "2700", "2900"],
]
PAGOS_ARG = [
    ["Dolar oficial", "1100", "1100", "1120"],
    ["Mes", *MONTHS],
    [
        "Cliente Pago",
        _formula(121000, "=100*1.21*B$8", GREEN),
        _formula(266200, "=(200*1.21)*C1", BLUE),
        _formula(453750, "=300*1.21*1250", ORANGE),
    ],
    ["Cliente Divisa", _formula(54450, "=50*1.21*B7"), None, _value("130000", CYAN)],
    ["Total Ingresos", "175450", "266200", "583750"],
    ["MEP", "1000", "1010", "1020"],
    ["Dolar Divisa VTA", "900", "910", "920"],
    ["MEP", "1000", "1010", "1020"],
    ["Mes", *MONTHS],
]
SLEAKOPS = [
    ["Total pagos USA", None, None, "300", "0", "0"],
    ["Cliente", "Generado por", "Servicio", *MONTHS],
    [
        "Cliente Baja",
        "Alguien",
        "Servicio",
        _value("300", GREEN),
        _value(None, MAGENTA),
        _value("0", CYAN),
    ],
    ["Total Ingresos", None, None, "300", "0", "0"],
]
AMOUNTS = ["1100", "1200", "1300", "1400", "1500", "1600", "1700", "2100", "121000", "266200"]
AMOUNTS += ["453750", "54450", "130000", "6300", "175450", "583750"]
WINDOW_END = datetime(2026, 10, 18, 12, tzinfo=UTC)


@pytest.fixture
def fake(monkeypatch):
    from craftech_os.ingest.google import Google

    fake = FakeGoogle()
    fake.files_by_id["file-a"] = {
        "name": "Facturación Ficticia",
        "version": "1",
        "tabs": [_sheet(11, "Pagos", PAGOS), _sheet(12, "Pagos ARG", PAGOS_ARG)],
    }
    fake.files_by_id["file-s"] = {
        "name": "Facturación SleakOps Ficticia",
        "version": "1",
        "tabs": [_sheet(31, "Pagos", SLEAKOPS)],
    }
    monkeypatch.setattr(Google, "from_environment", classmethod(lambda cls: fake.google()))
    return fake


@pytest.fixture
def env(db, monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", db.info.dsn + " password=" + (db.info.password or ""))
    migrate(db)
    path = tmp_path / "sources.yaml"
    path.write_text(SOURCES, encoding="utf-8")
    return path


def _invoices(db, tab="Pagos", planilla="Facturación Ficticia"):
    return db.execute(
        """
        SELECT clave_fila, mes, estado, monto, celda FROM mcp.facturas
        WHERE planilla = %s AND pestaña = %s ORDER BY celda
        """,
        (planilla, tab),
    ).fetchall()


def _payments(db):
    return db.execute(
        "SELECT clave_fila, mes, celda, fecha, origen_fecha, cambio_id FROM mcp.cobros"
        " WHERE planilla = 'Facturación Ficticia' AND pestaña = 'Pagos' ORDER BY clave_fila, mes"
    ).fetchall()


def _edit(rows, r, c, cell):
    edited = [row[:] for row in rows]
    edited[r] = edited[r] + [None] * (c + 1 - len(edited[r]))
    edited[r][c] = cell
    return edited


def test_each_color_is_a_state_and_cells_without_invoice_give_none(db, env, fake):
    _import(env)
    assert _invoices(db) == [
        ("cliente uno", JAN, "a confirmar", Decimal("1100"), "D3"),
        ("cliente dos", JAN, "pagada", Decimal("1400"), "D4"),
        ("cliente tres", JAN, "a facturar", Decimal("1700"), "D5"),
        ("cliente uno (2)", JAN, "confirmada", Decimal("2100"), "D7"),
        ("cliente uno", FEB, "confirmada", Decimal("1200"), "E3"),
        ("cliente dos", FEB, "retraso", Decimal("1500"), "E4"),
        ("cliente uno", MAR, "enviada", Decimal("1300"), "F3"),
        ("cliente dos", MAR, "a facturar", Decimal("1600"), "F4"),
    ]
    (row,) = db.execute(
        "SELECT entidad_legal, moneda, neto_ars, cotizacion FROM mcp.facturas WHERE celda = 'D4'"
        " AND pestaña = 'Pagos' AND planilla = 'Facturación Ficticia'"
    ).fetchall()
    assert row == ("Craftech-io Inc.", "USD", None, None)
    assert [key for key, _ in _issues(db, "color_desconocido")] == [SALMON]
    assert ("Cliente:cliente tres:feb 2025", {"cell_ref": "E5"}) in _issues(db, "valor_ilegible")
    assert ("Cliente:cliente uno", {"block": "Cliente", "rows": 2}) in _issues(
        db, "identidad_en_revision"
    )


def test_an_emptied_invoice_disappears_and_its_history_stays(db, env, fake):
    _import(env)
    _set(fake, 11, _edit(_edit(PAGOS, 2, 5, None), 6, 4, _value("2200", CYAN)))
    _import(env)
    assert "F3" not in [r[4] for r in _invoices(db)]
    assert ("cliente uno (2)", FEB, "a confirmar", Decimal("2200"), "E7") in _invoices(db)
    changes = db.execute(
        "SELECT clave_fila, celda, estado_anterior, estado_nuevo, fecha"
        " FROM mcp.cambios_de_estado_de_factura ORDER BY celda"
    ).fetchall()
    assert changes == [
        ("cliente uno (2)", "E7", "sin factura", "a confirmar", WINDOW_END),
        ("cliente uno", "F3", "enviada", "sin factura", WINDOW_END),
    ]


def test_a_payment_gets_the_editor_date_once_drive_attributes_it(db, env, fake):
    _import(env)
    # Already green on the first read: a payment of unknown date.
    assert _payments(db) == [("cliente dos", JAN, "D4", None, "fecha desconocida", None)]
    _set(fake, 11, _edit(PAGOS, 2, 4, _value("1200", GREEN)))
    _import(env)
    (change,) = db.execute(
        "SELECT id FROM cell_change WHERE change_type = 'color' AND cell_ref = 'E3'"
    ).fetchone()
    paid = ("cliente uno", FEB, "E3", WINDOW_END, "ventana de detección", change)
    assert paid in _payments(db)
    assert ("cliente uno", "confirmada", "pagada") in db.execute(
        "SELECT clave_fila, estado_anterior, estado_nuevo FROM mcp.cambios_de_estado_de_factura"
    ).fetchall()
    edited_at = WINDOW_END - timedelta(minutes=7)
    db.execute(
        "UPDATE cell_change SET attribution_certainty = 'cierta', attributed_at = %s WHERE id = %s",
        (edited_at, change),
    )
    assert ("cliente uno", FEB, "E3", edited_at, "editor", change) in _payments(db)


def test_a_payment_repainted_green_points_at_the_last_change(db, env, fake):
    _import(env)
    for color in (GREEN, BLUE, GREEN):
        _set(fake, 11, _edit(PAGOS, 2, 4, _value("1200", color)))
        _import(env)
    (last,) = db.execute(
        "SELECT max(id) FROM cell_change WHERE change_type = 'color' AND cell_ref = 'E3'"
        " AND new_color = %s",
        (GREEN,),
    ).fetchone()
    assert ("cliente uno", FEB, "E3", WINDOW_END, "ventana de detección", last) in _payments(db)


def test_a_row_inserted_above_keeps_its_payment(db, env, fake):
    _import(env)
    paid = _edit(PAGOS, 2, 4, _value("1200", GREEN))
    _set(fake, 11, paid)
    _import(env)
    before = _payments(db)
    _set(fake, 11, [*paid[:2], ["Cliente Nuevo", "Alguien", "Servicio"], *paid[2:]])
    _import(env)
    after = _payments(db)
    assert len(after) == len(before) == 2
    assert [r[:2] + r[3:] for r in after] == [r[:2] + r[3:] for r in before]
    assert [r[2] for r in after] == ["D5", "E4"]


def test_an_arg_invoice_has_gross_net_rate_and_inferred_usd(db, env, fake):
    _import(env)
    rows = db.execute(
        """
        SELECT celda, entidad_legal, moneda, monto, neto_ars, cotizacion, tipo_cotizacion,
               cotizacion_a_confirmar, usd_inferido, estado
        FROM mcp.facturas WHERE pestaña = 'Pagos ARG' ORDER BY celda
        """
    ).fetchall()
    arg = ("Craftech S.A.", "ARS")
    assert rows == [
        (
            "B3",
            *arg,
            Decimal("121000"),
            Decimal("100000.00"),
            Decimal("1000"),
            "mep",
            False,
            Decimal("100"),
            "pagada",
        ),
        (
            "B4",
            *arg,
            Decimal("54450"),
            Decimal("45000.00"),
            Decimal("900"),
            None,
            True,
            Decimal("50"),
            "a facturar",
        ),
        (
            "C3",
            *arg,
            Decimal("266200"),
            Decimal("220000.00"),
            Decimal("1100"),
            "oficial",
            True,
            Decimal("200"),
            "confirmada",
        ),
        (
            "D3",
            *arg,
            Decimal("453750"),
            Decimal("375000.00"),
            Decimal("1250"),
            "tipeada",
            False,
            Decimal("300"),
            "enviada",
        ),
        (
            "D4",
            *arg,
            Decimal("130000"),
            Decimal("107438.02"),
            None,
            None,
            False,
            None,
            "a confirmar",
        ),
    ]
    assert _issues(db, "cotizacion_tipeada") == [
        ("Mes:cliente divisa:mar 2025", {"cell_ref": "D4"}),
        ("Mes:cliente pago:mar 2025", {"cell_ref": "D3"}),
    ]
    assert ("dolar divisa vta", {"row": "dolar divisa vta"}) in _issues(
        db, "cotizacion_tipo_a_confirmar"
    )


def test_parity_is_zero_with_consistent_data_and_shows_a_missing_invoice(db, env, fake):
    # Sheets adds in binary floating point: a total off by a millionth still closes.
    _set(fake, 11, _edit(PAGOS, 0, 3, "6300.000001"))
    _import(env)

    def parity(planilla, tab):
        return db.execute(
            "SELECT mes, total_planilla, suma_facturas, diferencia FROM mcp.paridad_pagos"
            " WHERE planilla = %s AND pestaña = %s ORDER BY mes",
            (planilla, tab),
        ).fetchall()

    for planilla, tab in [
        ("Facturación Ficticia", "Pagos"),
        ("Facturación Ficticia", "Pagos ARG"),
        ("Facturación SleakOps Ficticia", "Pagos"),
    ]:
        rows = parity(planilla, tab)
        assert [r[0] for r in rows] == [JAN, FEB, MAR]
        assert {r[3] for r in rows} == {0}, (planilla, tab)
    _set(fake, 12, _edit(PAGOS_ARG, 3, 1, None))
    _import(env)
    assert [r[3] for r in parity("Facturación Ficticia", "Pagos ARG")] == [
        Decimal("54450"),
        0,
        0,
    ]


def test_a_painted_cell_without_amount_in_sleakops_is_a_churn_to_be_confirmed(db, env, fake):
    _import(env)
    rows = db.execute(
        "SELECT planilla, clave_fila, mes, color, color_a_confirmar, celda FROM mcp.bajas"
        " ORDER BY celda"
    ).fetchall()
    sleakops = "Facturación SleakOps Ficticia"
    assert rows == [
        (sleakops, "cliente baja", FEB, MAGENTA, True, "E3"),
        (sleakops, "cliente baja", MAR, CYAN, True, "F3"),
    ]
    assert _invoices(db, planilla=sleakops) == [
        ("cliente baja", JAN, "pagada", Decimal("300"), "D3")
    ]


def test_interpret_twice_leaves_the_same_facts_and_nothing_logs_amounts(db, env, fake, capsys):
    _import(env)

    def state():
        return [
            db.execute(f"SELECT * FROM {view} ORDER BY 1, 2, 3, 4, 5").fetchall()
            for view in ("mcp.facturas", "mcp.cobros", "mcp.bajas", "mcp.paridad_pagos")
        ] + [db.execute("SELECT issue_type, stable_key, details FROM issue ORDER BY id").fetchall()]

    before = state()
    assert cli.main(["interpret", "--all"]) == 0
    assert state() == before
    out = capsys.readouterr().out
    assert "3 tabs interpreted" in out and "invoices" in out
    events = [
        d for (d,) in db.execute("SELECT details FROM system_event WHERE kind = 'tab_interpreted'")
    ]
    assert sorted((d["invoices"], d["payments"], d["churn"]) for d in events)[-1] == (8, 1, 0)
    logged = json.dumps(events + [d for (d,) in db.execute("SELECT details FROM issue")])
    assert not any(amount in logged or amount in out for amount in AMOUNTS)


def test_a_row_whose_text_ends_in_a_number_is_not_mixed_with_a_series(db, env, fake):
    literal = ["Cliente Uno (2)", "Alguien", "Servicio", _value("3100", GREEN)]
    _set(fake, 11, [*PAGOS[:7], literal, *PAGOS[7:]])
    _import(env)
    rows = db.execute(
        "SELECT clave_fila, serie, mes, monto, celda FROM mcp.facturas"
        " WHERE pestaña = 'Pagos' AND planilla = 'Facturación Ficticia' AND mes = %s"
        " AND clave_fila LIKE 'cliente uno%%' ORDER BY celda",
        (JAN,),
    ).fetchall()
    assert rows == [
        ("cliente uno", 1, JAN, Decimal("1100"), "D3"),
        ("cliente uno (2)", 2, JAN, Decimal("2100"), "D7"),
        ("cliente uno (2)", 1, JAN, Decimal("3100"), "D8"),
    ]
    _set(fake, 11, [*_edit(PAGOS, 6, 3, _value("2100", GREEN))[:7], literal, *PAGOS[7:]])
    _import(env)
    (change,) = db.execute(
        "SELECT id FROM cell_change WHERE change_type = 'color' AND cell_ref = 'D7'"
    ).fetchone()
    paid = db.execute(
        "SELECT celda, cambio_id FROM mcp.cobros WHERE clave_fila = 'cliente uno (2)' ORDER BY 1"
    ).fetchall()
    assert paid == [("D7", change), ("D8", None)]


def test_a_zero_or_a_text_over_an_amount_shows_in_the_history(db, env, fake):
    _import(env)
    _set(fake, 11, _edit(_edit(PAGOS, 2, 4, _value("pendiente", BLUE)), 2, 5, _value("0", ORANGE)))
    _import(env)
    assert [r[4] for r in _invoices(db) if r[0] == "cliente uno"] == ["D3"]
    changes = db.execute(
        "SELECT celda, estado_anterior, estado_nuevo FROM mcp.cambios_de_estado_de_factura"
        " ORDER BY celda"
    ).fetchall()
    assert changes == [("E3", "confirmada", "sin factura"), ("F3", "enviada", "sin factura")]
    # A zero typed where there was nothing is not an invoice either way.
    _set(fake, 11, _edit(PAGOS, 6, 4, _value("0", BLUE)))
    _import(env)
    assert "E7" not in [
        r[0] for r in db.execute("SELECT celda FROM mcp.cambios_de_estado_de_factura")
    ]


def test_an_amount_typed_into_a_green_cell_is_the_payment_change(db, env, fake):
    _set(fake, 11, _edit(PAGOS, 6, 4, _value(None, GREEN)))
    _import(env)
    _set(fake, 11, _edit(PAGOS, 6, 4, _value("2200", GREEN)))
    _import(env)
    (change,) = db.execute(
        "SELECT id FROM cell_change WHERE change_type = 'value' AND cell_ref = 'E7'"
    ).fetchone()
    assert ("cliente uno (2)", FEB, "E7", WINDOW_END, "ventana de detección", change) in _payments(
        db
    )


@pytest.mark.parametrize("formula", ["=ROUND(50*1.21*B7)", "=50*1.21*B7+0"])
def test_an_arg_formula_that_is_not_a_plain_product_still_reads_its_rate(db, env, fake, formula):
    _set(fake, 12, _edit(PAGOS_ARG, 3, 1, _formula(54450, formula)))
    _import(env)
    (row,) = db.execute(
        "SELECT cotizacion, usd_inferido FROM mcp.facturas WHERE pestaña = 'Pagos ARG'"
        " AND celda = 'B4'"
    ).fetchall()
    assert row == (Decimal("900"), None)


def test_an_arg_formula_with_two_references_opens_a_problem(db, env, fake):
    _set(fake, 12, _edit(PAGOS_ARG, 3, 1, _formula(54450, "=50*1.21*(B7+B6)/2")))
    _import(env)
    (row,) = db.execute(
        "SELECT cotizacion, usd_inferido FROM mcp.facturas WHERE pestaña = 'Pagos ARG'"
        " AND celda = 'B4'"
    ).fetchall()
    assert row == (None, None)
    assert ("Mes:cliente divisa:ene 2025", {"cell_ref": "B4"}) in _issues(
        db, "cotizacion_tipo_a_confirmar"
    )
