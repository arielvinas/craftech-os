"""Funding milestones of the AWS blocks of Pagos and of the FUNDINGS tracker (T-012).

Against the test database. Invented names and amounts only.
"""

import csv
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
        funding_total: "TOTAL PAGOS AWS"
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
        funding_total: "TOTAL PAGOS AWS"
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
    # Found by its text: in the real sheets it is above the header.
    ["TOTAL PAGOS AWS", None, None, "5000", "5500", "0"],
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
    ["TOTAL PAGOS AWS", None, None, "4000", "0", "1500"],
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


def test_an_amount_typed_in_the_row_that_opens_a_block_is_a_problem_not_lost(db, env, fake):
    pagos = _edit(PAGOS, 3, 0, None)
    pagos[3] = ["General", "MAP", "Project", "8000"]
    _set(fake, 11, pagos)
    _import(env)
    cells = [row[-1] for row in _fundings(db, "pagos") if row[0] == "Facturación Ficticia"]
    assert cells == ["D5", "E6", "E8"]
    opened = [(k, d) for k, d in _issues(db, "fila_sin_interpretar") if k.startswith("General")]
    assert opened == [("General:general:D", {"block": "General", "cell_ref": "D4"})]


def test_a_cei_row_outside_general_is_a_problem_not_a_milestone(db, env, fake):
    pagos = [row[:] for row in PAGOS]
    pagos[6] = ["Funding de AWS confirmados", "CEI", "CEI", "8000"]
    _set(fake, 11, pagos)
    _import(env)
    assert "CEI" not in {r[3] for r in _fundings(db, "pagos")}
    opened = [(k, d) for k, d in _issues(db, "fila_sin_interpretar") if k.startswith("Funding")]
    assert opened == [
        (
            "Funding de AWS confirmados:funding de aws confirmados:D",
            {"block": "Funding de AWS confirmados", "cell_ref": "D7"},
        )
    ]


def _months(*days):
    return [_month((d - EPOCH).days, d.strftime("%b %Y")) for d in days]


def test_the_cei_row_of_general_gives_milestones_up_to_september_2026(db, env, fake):
    # Ariel's declaration of 20-oct-2026, pending ratification: CEI ended in September 2026.
    sep = date(2026, 9, 1)
    pagos = [row[:] for row in PAGOS]
    pagos[1] = [*PAGOS[1][:3], *_months(FEB, sep, date(2026, 10, 1))]
    # On the CEI row a copy from another sheet counts; on a client row it gives nothing.
    pagos[3] = ["General", "CEI", "CEI", _formula(8000, IMPORTRANGE), "9000", "7000"]
    pagos = _edit(pagos, 5, 3, _formula(1234, "='Otra planilla'!D5"))
    _set(fake, 11, pagos)
    _import(env)
    craftech = "Facturación Ficticia"
    assert [r for r in _fundings(db, "pagos") if r[0] == craftech] == [
        (craftech, "General", "general", "CEI", 1, "CEI #1", True, FEB, 8000, "D4"),
        (craftech, "General", "cliente uno", "MAP", 1, "MAP #1", True, FEB, 5000, "D5"),
        (craftech, "General", "general", "CEI", 2, "CEI #2", True, sep, 9000, "E4"),
    ]
    opened = [(k, d) for k, d in _issues(db, "fila_sin_interpretar") if k.startswith("General")]
    assert opened == [
        (
            "General:general:F",
            {
                "block": "General",
                "cell_ref": "F4",
                "reason": "el programa CEI terminó en septiembre de 2026",
            },
        )
    ]
    texts = [d["text"] for _, d in _issues(db, "alias_sin_cliente")]
    assert "cliente uno" in texts and "general" not in texts

    def state():
        return [
            db.execute("SELECT * FROM mcp.fundings ORDER BY celda, origen").fetchall(),
            db.execute(
                "SELECT id, tipo, estado, celda, detalle FROM mcp.issues ORDER BY id"
            ).fetchall(),
        ]

    before = state()
    assert cli.main(["interpret", "--all"]) == 0
    assert state() == before


def test_a_duplicate_needs_the_same_amount_and_client_and_aliases_join_texts(
    db, env, fake, tmp_path
):
    def row(name, loaded, amount):
        return [name, "MAP", "Cargado en FP", "Craftech", _date(loaded), None, None, amount]

    _set(
        fake,
        41,
        [
            TRACKER_HEADER,
            # Same text as Cliente Uno of Pagos, another amount: not the same funding.
            row("Cliente Uno", date(2026, 3, 1), "1234"),
            # Another text, the amount of Cliente Uno in Pagos (D5).
            row("Uno Alias", date(2026, 3, 2), "5000"),
            # Loaded before the cut, after 1 February: Pagos has it (rule R28).
            row("Cliente Siete", date(2026, 2, 24), "777"),
        ],
        "file-f",
    )
    _import(env)
    assert [r[-1] for r in _fundings(db, "tracker")] == ["H2", "H3"]
    assert _issues(db, "funding_duplicado") == []
    aliases = tmp_path / "aliases.csv"
    with aliases.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(
            [
                ["fuente", "texto", "cliente", "decidió", "motivo"],
                ["Facturación Ficticia / Pagos", "Cliente Uno", "Uno SA", "Ariel", "prueba"],
                ["Fundings Ficticios / FUNDINGS", "Uno Alias", "Uno SA", "Ariel", "prueba"],
            ]
        )
    assert cli.main(["aliases", "load", str(aliases)]) == 0
    assert cli.main(["interpret", "--all"]) == 0
    ((key, details),) = _issues(db, "funding_duplicado")
    assert key.startswith("uno alias|")
    assert (details["tracker"]["cell_ref"], details["pagos"]["cell_ref"]) == ("H3", "D5")


def test_a_missing_tracker_column_and_an_unreadable_amount_are_problems(db, env, fake):
    header = [h if h != "MONTO A PEDIR" else "Monto" for h in TRACKER_HEADER]
    _set(fake, 41, [header, *TRACKER[1:]], "file-f")
    _import(env)
    assert _fundings(db, "tracker") == []
    assert _issues(db, "fila_sin_interpretar")[-1] == (
        "falta:MONTO A PEDIR",
        {"column": "MONTO A PEDIR"},
    )
    _set(fake, 41, _edit(TRACKER, 1, 7, "a definir"), "file-f")
    _import(env)
    assert [r[-1] for r in _fundings(db, "tracker")] == ["H3", "H5", "H6"]
    assert _issues(db, "valor_ilegible") == [
        ("EMPRESA:cliente cinco:MONTO A PEDIR", {"cell_ref": "H2"})
    ]


def test_a_tracker_row_of_an_unknown_business_unit_is_kept_and_is_a_problem(db, env, fake):
    _set(fake, 41, _edit(TRACKER, 1, 3, "Otra"), "file-f")
    _import(env)
    assert [r[-1] for r in _fundings(db, "tracker")] == ["H2", "H3", "H5", "H6"]
    assert ("EMPRESA:cliente cinco:unidad", {"cell_ref": "D2"}) in _issues(
        db, "fila_sin_interpretar"
    )


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


def _aws_parity(db):
    return db.execute(
        "SELECT planilla, mes, total_planilla, suma_fundings, diferencia"
        " FROM mcp.paridad_fundings_aws ORDER BY planilla, mes"
    ).fetchall()


def test_aws_parity_adds_pagos_then_cei_and_the_tracker_by_collection_month(db, env, fake):
    _import(env)
    craftech, sleakops = "Facturación Ficticia", "Facturación SleakOps Ficticia"
    may, jul = date(2026, 5, 1), date(2026, 7, 1)
    assert _aws_parity(db) == [
        (craftech, JAN, Decimal("5000"), Decimal("5000"), 0),
        (craftech, FEB, Decimal("5500"), Decimal("5500"), 0),
        (craftech, MAR, Decimal("0"), 0, 0),
        # After the grid: the tracker milestones are paid on 20/5 and expected on 1/7.
        (craftech, may, None, Decimal("6000"), -6000),
        (craftech, jul, None, Decimal("4000"), -4000),
        (sleakops, JAN, Decimal("4000"), Decimal("4000"), 0),
        (sleakops, FEB, Decimal("0"), 0, 0),
        (sleakops, MAR, Decimal("1500"), Decimal("1500"), 0),
    ]
    # March, after the cut: a CEI milestone the total does not add.
    pagos = [row[:] for row in PAGOS]
    pagos[3] = ["General", "CEI", "CEI", None, None, "300"]
    _set(fake, 11, pagos)
    _import(env)
    assert (craftech, MAR, Decimal("0"), Decimal("300"), -300) in _aws_parity(db)


def test_a_sheet_without_its_aws_total_row_is_a_problem(db, env, fake):
    _set(fake, 31, SLEAKOPS[:-1], "file-s")
    _import(env)
    assert ("falta:total pagos aws", {"row": "total pagos aws"}) in _issues(
        db, "fila_sin_interpretar"
    )
    assert "Facturación SleakOps Ficticia" not in {r[0] for r in _aws_parity(db) if r[2]}


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
    assert pagos["funding_blocks"] == ["Fundings de AWS", "General"]
    assert pagos["funding_total"] == "TOTAL PAGOS AWS"
    assert parsed["Facturación - Craftech Total"]["schemas"]["Pagos"]["funding_total"] == (
        "TOTAL PAGOS AWS"
    )


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
        ("{header: C, key: A, grid: 'D:F', funding_total: ''}", "funding_total must be"),
    ],
)
def test_an_invalid_fundings_schema_is_rejected(schema, message):
    text = f"sources: [{{title: A, tabs: {{CARGA: [FUNDINGS]}}, schemas: {{FUNDINGS: {schema}}}}}]"
    with pytest.raises(SourcesError, match=message):
        parse(text)
