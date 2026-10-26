"""Monthly cashflow from the bank movements, with the origin of each cell (T-019, ADR-003).

Against the test database. Invented amounts and details only; banks, rubros and the rows of the
Resumen are labels. Months are relative to today: the view tells real, current and projected
months apart with current_date.
"""

from datetime import date
from decimal import Decimal

import psycopg
import pytest
import yaml
from test_consolidado import HEADERS, SCHEMA, TITLE, _row
from test_import import FakeGoogle
from test_interpret import _import, _month, _set, _sheet
from test_mcp import _url

from craftech_os import cashflow, cli
from craftech_os.migrate import migrate

SHEET = "CASH FLOW MENSUAL"
RESUMEN = "Resumen mensual Cash Flow ARG-USA"
SOURCES = yaml.safe_dump(
    {
        "sources": [
            {
                "title": TITLE,
                "drive_id": "file-b",
                "tabs": {"CARGA": ["Consolidado"]},
                "schemas": {"Consolidado": SCHEMA},
            },
            {"title": SHEET, "drive_id": "file-c", "tabs": {"DERIVADA": [RESUMEN]}},
        ]
    },
    allow_unicode=True,
)
ARG = "Argentina en miles de pesos"
INC = "Craftech Inc. en dólares"
PROJ = "Craftech Inc. con pagos proyectados"


def _shift(months: int) -> date:
    today = date.today()
    n = today.year * 12 + today.month - 1 + months
    return date(n // 12, n % 12 + 1, 1)


def _header(d: date) -> dict:
    return _month((d - date(1899, 12, 30)).days, f"{d:%b-%y}", 'mmm"-"yy')


# Three closed real months, the current one and a projected one.
R1, R2, R3, CUR, NEXT = (_shift(n) for n in (-3, -2, -1, 0, 1))
MONTHS = [R1, R2, R3, CUR, NEXT]


def _move(bank, rubro, amount, month, tipo="Egresos", currency=None, **extra):
    currency = currency or ("USD" if bank in ("MERCURY", "Mesh") else "ARS")
    return _row(bank, rubro, amount, month=_header(month), tipo=tipo, currency=currency, **extra)


SUELDO = {"detalle": "Persona Ficticia Zeta", "subdetalle": "Puesto Ficticio", "equipo": "Eq Z"}
MOVES = [
    HEADERS,
    _move("Mesh", "COBRANZA", "1000", R1, "Ingresos"),
    _move("Mesh", "01. Sueldos", "-120", R1, "Sueldos", **SUELDO),
    _move("Mesh", "01. Sueldos", "-180", R1, "Sueldos", **SUELDO),
    _move("Mesh", "04. Alquileres", "-100", R1),
    _move("MERCURY", "CAJA. Intercompany", "-200", R1),
    _move("Mesh", "COBRANZA", "500", R2, "Ingresos"),
    _move("Mesh", "01. Sueldos", "-300", R2, "Sueldos", **SUELDO),
    _move("Mesh", "04. Alquileres", "-50", R2),
    _move("Mesh", "01. Sueldos", "-300", R3, "Sueldos", **SUELDO),
    _move("Mesh", "COBRANZA", "10", CUR, "Ingresos"),
    _move("Mesh", "COBRANZA", "7", NEXT, "Ingresos"),
    _move("GALICIA", "COBRANZA", "2000", R2, "Ingresos"),
    _move("GALICIA", "CAJA. Intercompany", "150", R2, "Ingresos"),
    _move("GALICIA", "01. Sueldos", "-700", R2, "Sueldos", **SUELDO),
    _move("GALICIA", "04. Alquileres", "-300", R2),
]
FORMULA = {
    "effectiveValue": {"numberValue": 999},
    "formattedValue": "999",
    "userEnteredValue": {"formulaValue": "=C4+1"},
}
SHEET_VALUE = "999"
RESUMEN_ROWS = [
    [None, None, *(_header(m) for m in MONTHS)],
    ["ARGENTINA", "Saldo Inicial", *[SHEET_VALUE] * 5],
    [None, "Pagos Recibidos S.A.", *[SHEET_VALUE] * 5],
    [None, "Gastos", FORMULA, *[SHEET_VALUE] * 4],
    ["CASH FLOW USA", "Saldo Inicial", *[SHEET_VALUE] * 5],
    [None, "Pagos Recibidos INC", *[SHEET_VALUE] * 5],
    [None, "Saldo Final", *[SHEET_VALUE] * 5],
    # A label again in the same section: the first one is taken.
    [None, "Saldo Final", *[SHEET_VALUE] * 5],
    ["CASH FLOW USA Con facturacion minima", "Saldo Inicial", *[SHEET_VALUE] * 5],
    ["CONTROL CASH FLOW REAL CON PROYECTADO"],
    ["Pagos Proyectados Craftech", None, *[SHEET_VALUE] * 5],
]


@pytest.fixture
def fake(monkeypatch):
    from craftech_os.ingest.google import Google

    fake = FakeGoogle()
    fake.files_by_id["file-b"] = {
        "name": TITLE,
        "version": "1",
        "tabs": [_sheet(41, "Consolidado", MOVES)],
    }
    fake.files_by_id["file-c"] = {
        "name": SHEET,
        "version": "1",
        "tabs": [_sheet(61, RESUMEN, RESUMEN_ROWS)],
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


def _sheet_cells(db):
    return db.execute(
        "SELECT block, label, month, value, cell_ref, has_formula, snapshot_id"
        " FROM cashflow_sheet_cell ORDER BY block, label, month"
    ).fetchall()


def _cells(db, block):
    """{(label, month): (value, origin, period, motivo)} of a block."""
    rows = db.execute(
        "SELECT label, month, value, origin, period, motivo FROM cashflow_cell WHERE block = %s",
        (block,),
    ).fetchall()
    return {(label, month): tuple(rest) for label, month, *rest in rows}


def test_the_resumen_is_projected_though_derivada_and_a_new_read_replaces_it(db, env, fake):
    _import(env)
    cells = _sheet_cells(db)
    # Arg: 3 rows; Inc: 3 rows; control: 1 row; the scenario block is not one of ours.
    assert len(cells) == 7 * len(MONTHS)
    gastos = [c for c in cells if c[:2] == (ARG, "Gastos")]
    assert gastos[0][2:6] == (R1, Decimal("999"), "C4", True)
    assert gastos[1][5] is False
    assert (PROJ, "Saldo Inicial") not in {c[:2] for c in cells}
    assert ("Diferencia entre proyectado y real", "Pagos Proyectados Craftech") in {
        c[:2] for c in cells
    }
    _set(fake, 61, RESUMEN_ROWS[:3], "file-c")
    _import(env)
    again = _sheet_cells(db)
    assert len(again) == 2 * len(MONTHS)
    assert len({c[-1] for c in again}) == 1 and again[0][-1] != cells[0][-1]


def test_real_months_add_the_movements_and_no_sheet_value_is_shown(db, env, fake):
    _import(env)
    inc = _cells(db, INC)
    assert inc["Pagos Recibidos INC", R1] == (Decimal("1000"), "recalculada", "real", None)
    assert inc["Sueldos", R1][:2] == (Decimal("300"), "recalculada")
    assert inc["Gastos", R1][0] == Decimal("100")
    assert inc["USD enviados a la S.A.", R1][0] == Decimal("200")
    assert inc["Saldo Final", R1][0] == Decimal("400")
    assert inc["Saldo Inicial", R2][0] == Decimal("400")
    assert inc["Subtotal ingresos", R2][0] == Decimal("900")
    assert inc["Saldo Final", R3][0] == Decimal("250")
    assert inc["Pagos Recibidos INC", R3][0] == Decimal("0")
    arg = _cells(db, ARG)
    assert arg["Pagos Recibidos S.A.", R2][0] == Decimal("2000")
    assert arg["$ recibidos de la INC", R2][0] == Decimal("150")
    assert arg["Gastos", R2][0] == Decimal("1000")
    assert arg["Subtotal ingresos", R2][0] == Decimal("2150")
    assert arg["Saldo Final", R2][0] == Decimal("1150")
    every = db.execute("SELECT value FROM cashflow_cell WHERE value IS NOT NULL").fetchall()
    assert (Decimal(SHEET_VALUE),) not in every


def test_a_closed_month_without_movements_is_not_real_yet(db, env, fake):
    # Early in the month, before the Consolidado has the last closed month.
    _set(fake, 41, [m for m in MOVES if R3.strftime("%b-%y") not in str(m)], "file-b")
    _import(env)
    inc = _cells(db, INC)
    assert inc["Saldo Final", R2][2] == "real"
    assert inc["Sueldos", R3][:3] == (None, "sin_regla", "proyectado")
    by = {
        r[0]: r[1:]
        for r in db.execute("SELECT indicator, month, value FROM cashflow_indicator").fetchall()
    }
    assert by["caja_hoy"] == (R2, Decimal("550"))
    # Two real months only: no average with an empty month in it.
    assert by["salida_mensual"][1] is None


def test_the_current_month_is_recalculated_and_marked(db, env, fake):
    _import(env)
    inc = _cells(db, INC)
    assert inc["Pagos Recibidos INC", CUR] == (Decimal("10"), "recalculada", "en_curso", None)
    assert inc["Saldo Final", CUR][0] == Decimal("260")


def test_projected_months_and_rows_without_a_rule_have_no_value_and_say_why(db, env, fake):
    _import(env)
    inc = _cells(db, INC)
    value, origin, period, motivo = inc["Pagos Recibidos INC", NEXT]
    assert (value, origin, period) == (None, "sin_regla", "proyectado")
    assert "proyección" in motivo
    assert inc["Saldo Final", NEXT][:2] == (None, "sin_regla")
    for label in ("Ventas en $", "Gastos en $"):
        assert _cells(db, ARG)[label, R2][:3] == (None, "sin_regla", "real")
    assert "regla" in _cells(db, ARG)["Ventas en $", R2][3]
    assert _cells(db, PROJ)["Pagos Recibidos INC", R2][:2] == (None, "sin_regla")


def test_the_four_million_parameter_rows_are_marked_in_projected_months(db, env, fake):
    _import(env)
    marked = db.execute(
        "SELECT block, label, value FROM cashflow_cell WHERE origin = 'parametro'"
        " ORDER BY block, label"
    ).fetchall()
    assert marked == [
        (ARG, "$ recibidos de la INC", None),
        (PROJ, "USD enviados a la S.A.", None),
        (INC, "USD enviados a la S.A.", None),
    ]
    motivo = _cells(db, ARG)["$ recibidos de la INC", NEXT][3]
    assert "4.000.000" in motivo
    # In real months the same row adds the movements.
    assert _cells(db, INC)["USD enviados a la S.A.", R1][1] == "recalculada"


def test_the_indicators_are_proposed_with_their_formula(db, env, fake):
    _import(env)
    rows = db.execute(
        "SELECT indicator, value, unit, formula, proposed, month FROM cashflow_indicator"
        " ORDER BY position"
    ).fetchall()
    assert [r[0] for r in rows] == [
        "caja_hoy",
        "salida_mensual",
        "cobertura",
        "cierre_marzo",
        "cierre_marzo_con_pagos_proyectados",
    ]
    by = {r[0]: r for r in rows}
    assert by["caja_hoy"][1:3] == (Decimal("250"), "usd") and by["caja_hoy"][5] == R3
    assert by["salida_mensual"][1].quantize(Decimal("0.01")) == Decimal("416.67")
    assert by["cobertura"][1].quantize(Decimal("0.01")) == Decimal("0.60")
    assert by["cobertura"][2] == "meses"
    march = date(CUR.year + (CUR.month > 3), 3, 1)
    assert by["cierre_marzo"][1] is None and by["cierre_marzo"][5] == march
    assert all(r[4] is True and len(r[3]) > 20 for r in rows)


def test_the_cli_interpret_projects_the_resumen_too(db, env, fake, capsys):
    _import(env)
    db.execute("DELETE FROM cashflow_sheet_cell")
    assert cli.main(["interpret", "--all"]) == 0
    assert f"{SHEET} / {RESUMEN}: 7 rows, {7 * len(MONTHS)} cells" in capsys.readouterr().out
    assert len(_sheet_cells(db)) == 7 * len(MONTHS)


def test_projection_events_carry_counts_only(db, env, fake):
    _import(env)
    (details,) = db.execute(
        "SELECT details FROM system_event WHERE kind = 'cashflow_projected'"
    ).fetchone()
    assert details["filas"] == 7 and details["celdas"] == 7 * len(MONTHS)
    assert details["filas_sin_ubicar"] == len(cashflow.rows()) - 7
    assert SHEET_VALUE not in str(details)


def test_other_tabs_are_not_projected(db, env, fake):
    _import(env)
    (snapshot_id,) = db.execute(
        "SELECT n.id FROM snapshot n JOIN source_tab t ON t.id = n.source_tab_id"
        " WHERE t.name = 'Consolidado'"
    ).fetchone()
    assert cashflow.project(db, snapshot_id) is None


def test_cashflow_rows_validate_their_arithmetic(tmp_path):
    path = tmp_path / "rows.yaml"
    bad = {
        "blocks": [
            {"name": "x", "resumen": "X", "unit": "usd", "rows": [{"label": "a", "adds": ["b"]}]}
        ]
    }
    path.write_text(yaml.safe_dump(bad))
    with pytest.raises(ValueError, match="b"):
        cashflow.rows(path)
    # A subtotal of a row without a rule would add only part of what it says.
    bad["blocks"][0]["rows"].append({"label": "b"})
    path.write_text(yaml.safe_dump(bad))
    with pytest.raises(ValueError, match="b"):
        cashflow.rows(path)
    bad["blocks"][0]["rows"] = [{"label": "a", "balance": "final"}]
    path.write_text(yaml.safe_dump(bad))
    with pytest.raises(ValueError, match="banks"):
        cashflow.rows(path)
    bad["blocks"][0]["unit"] = "eur"
    path.write_text(yaml.safe_dump(bad))
    with pytest.raises(ValueError, match="eur"):
        cashflow.rows(path)
    # A duplicate key would silently keep only the last rule.
    path.write_text("blocks: [{name: x, resumen: X, unit: usd, rows: [{label: a, label: b}]}]")
    with pytest.raises(ValueError, match="duplicated key 'label'"):
        cashflow.rows(path)
    # A key that overrides a merged one is not a duplicate.
    path.write_text(
        "base: &base {label: a, rubros: [r]}\n"
        "blocks: [{name: x, resumen: X, unit: usd, rows: [{<<: *base, label: b}]}]"
    )
    assert [r["label"] for r in cashflow.rows(path)] == ["b"]


MCP_VIEWS = ("mcp.caja_mensual", "mcp.movimientos_de_caja", "mcp.indicadores_de_caja")


def test_the_reader_reads_the_cash_views_and_the_writer_does_not(db, env, fake):
    _import(env)
    reader, writer = (
        _url("mcp_reader", "MCP_READER_PASSWORD"),
        _url("mcp_writer", "MCP_WRITER_PASSWORD"),
    )
    with psycopg.connect(reader, autocommit=True) as conn:
        for view in MCP_VIEWS:
            assert conn.execute(f"SELECT count(*) FROM {view}").fetchone()[0] > 0, view
        row = conn.execute(
            "SELECT bloque, fila, mes, periodo, valor, unidad, origen, motivo, planilla,"
            " pestaña, celda, lectura_id FROM mcp.caja_mensual"
            " WHERE bloque = %s AND fila = 'Saldo Final' AND mes = %s",
            (INC, R1),
        ).fetchone()
        assert row[:7] == (INC, "Saldo Final", R1, "real", Decimal("400"), "usd", "recalculada")
        assert row[8:11] == (SHEET, RESUMEN, "C7")
    with psycopg.connect(writer, autocommit=True) as conn:
        for view in MCP_VIEWS:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(f"SELECT * FROM {view}")


def test_no_salary_of_a_person_reaches_the_cash_views(db, env, fake):
    _import(env)
    for view in MCP_VIEWS:
        text = str(db.execute(f"SELECT * FROM {view}").fetchall())
        for private in SUELDO.values():
            assert private not in text, view
    sueldos = db.execute(
        "SELECT detalle, subdetalle, equipo, monto FROM mcp.movimientos_de_caja"
        " WHERE rubro = '01. Sueldos'"
    ).fetchall()
    assert {r[:3] for r in sueldos} == {(None, None, None)}
    # R1 pays two salaries from Mesh: both views carry only their total.
    for view, column in (("mcp.movimientos_de_caja", "monto"), ("mcp.caja_mensual", "valor")):
        values = {r[0] for r in db.execute(f"SELECT abs({column}) FROM {view}")}
        assert Decimal("300") in values and not {Decimal("120"), Decimal("180")} & values, view
    (celda,) = db.execute(
        "SELECT celda FROM mcp.movimientos_de_caja WHERE rubro = '01. Sueldos' AND mes = %s",
        (R1,),
    ).fetchone()
    assert celda is None
