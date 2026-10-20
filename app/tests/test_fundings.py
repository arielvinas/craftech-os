"""Funding milestones of the AWS blocks of Pagos and of the FUNDINGS tracker (T-012).

Against the test database. Invented names and amounts only.
"""

import json
from datetime import date
from decimal import Decimal

import pytest
from test_diff_store import _value
from test_import import FakeGoogle
from test_interpret import _import, _issues, _month, _set, _sheet
from test_invoices import BLUE, _edit, _formula

from craftech_os import cli
from craftech_os.migrate import migrate
from craftech_os.sources import SourcesError, parse

TRACKER_COLUMNS = """
        columns:
          program: "TIPO DE FUNDING"
          status: "STATUS"
          business_unit: "Unidad Comercial"
          load_date: "Fecha De Carga En Fp"
          estimated_signoff: "Fecha Estimada De Firmado De Sign-Off"
          amount_usd: "MONTO A PEDIR"
          opportunity: "OPP ID"
          fund_claim_id: "Fund claim ID"
          invoice_loaded: "Invoice cargada"
          paid_on: "Fecha de pago"
"""
SOURCES = (
    """
sources:
  - title: "Facturación Ficticia"
    drive_id: "file-a"
    tabs:
      CARGA: ["Pagos"]
    schemas:
      "Pagos":
        header: "Cliente"
        key: A
        blocks: ["General", "Funding de AWS confirmados", "Total Ingresos"]
        funding_blocks: ["General", "Funding de AWS confirmados"]
        grid: "D:F"
  - title: "Facturación SleakOps Ficticia"
    drive_id: "file-s"
    tabs:
      CARGA: ["Pagos"]
    schemas:
      "Pagos":
        header: "Cliente"
        key: A
        blocks: ["Fundings de AWS", "General", "Total Ingresos"]
        funding_blocks: ["Fundings de AWS"]
        grid: "D:F"
  - title: "Fundings Ficticios"
    drive_id: "file-f"
    tabs:
      CARGA: ["FUNDINGS"]
      DERIVADA: ["Pagos confirmados"]
    schemas:
      "FUNDINGS":
        header: "EMPRESA"
        key: A
"""
    + TRACKER_COLUMNS
)
EPOCH = date(1899, 12, 30)
JAN, FEB, MAR = date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)
MONTHS = [_month(46023, "ene 2026"), _month(46054, "feb 2026"), _month(46082, "mar 2026")]


def _date(day):
    """A cell holding a date, as Google returns it."""
    return _month((day - EPOCH).days, day.strftime("%-d/%-m/%Y"), "d/M/yyyy")


IMPORTRANGE = '=IMPORTRANGE("x", "FUNDINGS!I2:I")'
PAGOS = [
    ["Total pagos USA", None, None, "100", "0", "0"],
    ["Cliente", "Generado por", "Servicio", *MONTHS],
    ["Cliente Uno", "Alguien", "Servicio", _value("100", BLUE)],
    ["General"],
    # Jan 2026 gives a milestone; Mar 2026 is after the cut (rule R28) and gives none.
    ["Cliente Uno", "MAP", "Project", "5000", None, "7000"],
    ["Cliente Dos", "POC CASH", "Project", None, "3000", "0"],
    ["Funding de AWS confirmados", None, None, _formula(9999, IMPORTRANGE)],
    ["Cliente Uno", "MAP", "Project", None, "2500"],
    ["Total Ingresos", None, None, "7600", "5500", "7000"],
]
SLEAKOPS = [
    ["Total pagos USA", None, None, "200", "0", "0"],
    ["Cliente", "Generado por", "Servicio", *MONTHS],
    ["Cliente Tres", "Alguien", "Servicio", "200"],
    ["Fundings de AWS", None, None, _formula(8888, IMPORTRANGE)],
    ["Cliente Tres", "POC CASH", "Onboarding", "4000"],
    ["General"],
    ["Cliente Cuatro", "Alguien", "Servicio", "800"],
    ["Total Ingresos", None, None, "5000", "0", "0"],
]
TRACKER_HEADER = [
    "EMPRESA",
    "TIPO DE FUNDING",
    "STATUS",
    "Unidad Comercial",
    "Fecha De Carga En Fp",
    "Fecha Estimada De Firmado De Sign-Off",
    "Fecha Estimada De Cobro",
    "MONTO A PEDIR",
    "OPP ID",
    "Invoice cargada",
    "Fecha de pago",
]
TRACKER = [
    TRACKER_HEADER,
    [
        "Cliente Cinco",
        "POC ",
        "Cargado en FP",
        "Craftech",
        _date(date(2026, 3, 10)),
        _date(date(2026, 4, 15)),
        "TBD",
        "6000",
        "O-0001",
        "Si",
        _date(date(2026, 5, 20)),
    ],
    # Not loaded yet: no load date, kept.
    [
        "Cliente Cinco",
        "POC",
        "Listo para cargar",
        "Craftech",
        None,
        _date(date(2026, 6, 1)),
        None,
        "4000",
        "O-0002",
    ],
    # Loaded before the cut: Pagos has it (rule R28).
    [
        "Cliente Seis",
        "MAP",
        "Cargado en FP",
        "SleakOps",
        _date(date(2026, 1, 10)),
        None,
        None,
        "999",
        "O-0003",
    ],
    [
        "Cliente Seis",
        "MAP",
        "Cargado en FP",
        "SleakOps",
        _date(date(2026, 2, 25)),
        _date(date(2026, 2, 1)),
        None,
        "1500",
        "O-0004",
        "si",
        _date(date(2026, 3, 3)),
    ],
    # The Feb 2026 funding of Cliente Dos in Pagos, also loaded here.
    [
        "Cliente Dos",
        "POC CASH",
        "Cargado en FP",
        "Craftech",
        _date(date(2026, 2, 26)),
        None,
        None,
        "3000",
        "O-0005",
    ],
    ["[VACIO]", "POC"],
]
MONTH_NAMES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto"]
MONTH_NAMES += ["Septiembre", "Octubre", "Noviembre", "Diciembre"]


def _year(year, amounts):
    """A row of Pagos confirmados: the year and one amount per month."""
    return [str(year), *(f"{amounts.get(m, 0)}" for m in range(1, 13))]


CONFIRMED = [
    ["Craftech", "Q1"],
    [None, *MONTH_NAMES],
    _year(2025, {}),
    _year(2026, {5: 6000}),
    [],
    ["SleakOps", "Q1"],
    [None, *MONTH_NAMES],
    _year(2026, {3: 1500}),
]
AMOUNTS = ["5000", "7000", "3000", "2500", "4000", "6000", "1500", "999"]


@pytest.fixture
def fake(monkeypatch):
    from craftech_os.ingest.google import Google

    fake = FakeGoogle()
    fake.files_by_id["file-a"] = {
        "name": "Facturación Ficticia",
        "version": "1",
        "tabs": [_sheet(11, "Pagos", PAGOS)],
    }
    fake.files_by_id["file-s"] = {
        "name": "Facturación SleakOps Ficticia",
        "version": "1",
        "tabs": [_sheet(31, "Pagos", SLEAKOPS)],
    }
    fake.files_by_id["file-f"] = {
        "name": "Fundings Ficticios",
        "version": "1",
        "tabs": [_sheet(41, "FUNDINGS", TRACKER), _sheet(42, "Pagos confirmados", CONFIRMED)],
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


def _fundings(db, origin):
    return db.execute(
        """
        SELECT planilla, bloque, clave_fila, programa, orden_en_programa, clave_hito,
               clave_provisional, mes, monto_usd, celda
        FROM mcp.fundings WHERE origen = %s ORDER BY planilla, celda
        """,
        (origin,),
    ).fetchall()


def _parity(db):
    return db.execute(
        "SELECT unidad_negocio, mes, total_planilla, suma_fundings, diferencia"
        " FROM mcp.paridad_fundings WHERE diferencia <> 0 OR suma_fundings <> 0"
        " ORDER BY unidad_negocio, mes"
    ).fetchall()


def test_the_aws_block_of_pagos_gives_milestones_up_to_february_2026(db, env, fake):
    _import(env)
    craftech, sleakops = "Facturación Ficticia", "Facturación SleakOps Ficticia"
    assert _fundings(db, "pagos") == [
        (craftech, "General", "cliente uno", "MAP", 1, "MAP #1", True, JAN, 5000, "D5"),
        (craftech, "General", "cliente dos", "POC CASH", 1, "POC CASH #1", True, FEB, 3000, "E6"),
        (
            craftech,
            "Funding de AWS confirmados",
            "cliente uno",
            "MAP",
            2,
            "MAP #2",
            True,
            FEB,
            2500,
            "E8",
        ),
        (
            sleakops,
            "Fundings de AWS",
            "cliente tres",
            "POC CASH",
            1,
            "POC CASH #1",
            True,
            JAN,
            4000,
            "D5",
        ),
    ]


def test_the_tracker_gives_milestones_loaded_from_february_25_2026(db, env, fake):
    _import(env)
    rows = db.execute(
        """
        SELECT clave_fila, programa, orden_en_programa, clave_hito, clave_provisional, oportunidad,
               estado, unidad_negocio, fecha_carga, signoff_estimado, cobro_estimado, monto_usd,
               invoice_cargada, fecha_pago, mes, celda
        FROM mcp.fundings WHERE origen = 'tracker' ORDER BY celda
        """
    ).fetchall()
    assert rows == [
        (
            "cliente cinco",
            "POC",
            1,
            "POC #1",
            True,
            "O-0001",
            "Cargado en FP",
            "Craftech",
            date(2026, 3, 10),
            date(2026, 4, 15),
            # Rule R22: sign-off + 30 days, whatever the sheet says.
            date(2026, 5, 15),
            Decimal("6000"),
            True,
            date(2026, 5, 20),
            None,
            "H2",
        ),
        (
            "cliente cinco (2)",
            "POC",
            2,
            "POC #2",
            True,
            "O-0002",
            "Listo para cargar",
            "Craftech",
            None,
            date(2026, 6, 1),
            date(2026, 7, 1),
            Decimal("4000"),
            False,
            None,
            None,
            "H3",
        ),
        (
            "cliente seis (2)",
            "MAP",
            1,
            "MAP #1",
            True,
            "O-0004",
            "Cargado en FP",
            "SleakOps",
            date(2026, 2, 25),
            date(2026, 2, 1),
            date(2026, 3, 3),
            Decimal("1500"),
            True,
            date(2026, 3, 3),
            None,
            "H5",
        ),
        (
            "cliente dos",
            "POC CASH",
            1,
            "POC CASH #1",
            True,
            "O-0005",
            "Cargado en FP",
            "Craftech",
            date(2026, 2, 26),
            None,
            None,
            Decimal("3000"),
            False,
            None,
            None,
            "H6",
        ),
    ]


def test_a_fund_claim_id_is_the_key_when_the_tracker_has_it(db, env, fake):
    header = [*TRACKER_HEADER, "Fund claim ID"]
    first = [*TRACKER[1], "FC-123"]
    _set(fake, 41, [header, first], "file-f")
    _import(env)
    rows = db.execute(
        "SELECT clave_hito, clave_provisional, fund_claim_id FROM mcp.fundings"
        " WHERE origen = 'tracker'"
    ).fetchall()
    assert rows == [("FC-123", False, "FC-123")]


def test_the_same_funding_on_both_sides_is_a_problem_and_both_rows_stay(db, env, fake):
    _import(env)
    ((key, details),) = _issues(db, "funding_duplicado")
    assert key.startswith("cliente dos|")
    assert details["tracker"]["cell_ref"] == "H6"
    assert details["pagos"]["cell_ref"] == "E6"
    both = db.execute(
        "SELECT origen FROM mcp.fundings WHERE clave_fila = 'cliente dos' ORDER BY origen"
    ).fetchall()
    assert both == [("pagos",), ("tracker",)]


def test_parity_is_zero_with_consistent_data_and_shows_a_difference(db, env, fake):
    _import(env)
    assert _parity(db) == [
        ("Craftech", date(2026, 5, 1), Decimal("6000"), Decimal("6000"), 0),
        ("SleakOps", MAR, Decimal("1500"), Decimal("1500"), 0),
    ]
    _set(fake, 42, _edit(CONFIRMED, 3, 5, "7000"), "file-f")
    _set(fake, 41, _edit(TRACKER, 4, 9, "no"), "file-f")
    _import(env)
    assert _parity(db) == [
        ("Craftech", date(2026, 5, 1), Decimal("7000"), Decimal("6000"), 1000),
        ("SleakOps", MAR, Decimal("1500"), 0, 1500),
    ]


def test_no_invoice_view_has_funding_amounts(db, env, fake):
    _import(env)
    invoiced = db.execute("SELECT DISTINCT monto FROM mcp.facturas ORDER BY 1").fetchall()
    assert invoiced == [(Decimal("100"),), (Decimal("200"),)]
    sums = db.execute("SELECT DISTINCT suma_facturas FROM mcp.paridad_pagos ORDER BY 1").fetchall()
    assert sums == [(0,), (Decimal("100"),), (Decimal("200"),)]


def test_interpret_twice_leaves_the_same_fundings_and_nothing_logs_amounts(db, env, fake, capsys):
    _import(env)

    def state():
        return [
            db.execute(f"SELECT * FROM {view} ORDER BY 1, 2, 3, 4, 5, 6").fetchall()
            for view in ("mcp.fundings", "mcp.paridad_fundings")
        ] + [db.execute("SELECT issue_type, stable_key, details FROM issue ORDER BY id").fetchall()]

    before = state()
    assert cli.main(["interpret", "--all"]) == 0
    assert state() == before
    out = capsys.readouterr().out
    assert "4 fundings" in out
    events = [
        d for (d,) in db.execute("SELECT details FROM system_event WHERE kind = 'tab_interpreted'")
    ]
    assert sorted(d["fundings"] for d in events)[-1] == 4
    logged = json.dumps(events + [d for (d,) in db.execute("SELECT details FROM issue")])
    assert not any(amount in logged or amount in out for amount in AMOUNTS)


def test_the_real_config_has_the_fundings_schema():
    from craftech_os import sources

    parsed = {s["title"]: s for s in parse(sources.SOURCES_FILE.read_text(encoding="utf-8"))}
    schema = parsed["FUNDINGS - Log de status [OFICIAL]"]["schemas"]["FUNDINGS"]
    assert schema["columns"]["amount_usd"] == "MONTO A PEDIR"
    pagos = parsed["Facturación - SleakOps Total"]["schemas"]["Pagos"]
    assert pagos["funding_blocks"] == ["Fundings de AWS"]


@pytest.mark.parametrize(
    "schema, message",
    [
        ("{header: EMPRESA, key: A}", "needs a schema with 'grid' or 'columns'"),
        ("{header: EMPRESA, key: A, columns: {program: X}}", "columns needs"),
        ("{header: EMPRESA, key: A, columns: [X]}", "columns must map"),
        (
            "{header: C, key: A, grid: 'D:F', blocks: [G], funding_blocks: [H]}",
            "funding_blocks must be among the blocks",
        ),
    ],
)
def test_an_invalid_fundings_schema_is_rejected(schema, message):
    text = f"sources: [{{title: A, tabs: {{CARGA: [FUNDINGS]}}, schemas: {{FUNDINGS: {schema}}}}}]"
    with pytest.raises(SourcesError, match=message):
        parse(text)
