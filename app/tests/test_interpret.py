"""Accruals of VENTAS and exchange rates of Pagos ARG, interpreted on each import.

Against the test database. Invented names and amounts only.
"""

import csv
import json
from datetime import date
from decimal import Decimal

import pytest
from test_diff_store import _value
from test_import import FakeGoogle, _tab

from craftech_os import cli, interpret
from craftech_os.migrate import migrate

SOURCES = """
sources:
  - title: "Cobranzas Ficticias"
    drive_id: "file-a"
    tabs:
      CARGA: ["VENTAS", "Pagos ARG", "Cobros"]
    schemas:
      "VENTAS":
        header: "Cliente"
        key: A
        blocks: ["Total Ingresos"]
        grid: "E:G"
      "Pagos ARG":
        header: "Mes"
        key: A
        blocks: ["Total Ingresos", "Mes"]
        grid: "B:D"
      "Cobros":
        header: "Cliente"
        key: A
        grid: "B:D"
  - title: "Ventas Mes Ficticias"
    drive_id: "file-s"
    tabs:
      CARGA: ["VENTAS"]
    schemas:
      "VENTAS":
        header: "Mes"
        key: A
        blocks: ["General", "Total Ingresos"]
        grid: "D:F"
"""
JAN, FEB, MAR = date(2025, 1, 1), date(2025, 2, 1), date(2025, 3, 1)


def _month(serial, label):
    """A header cell holding a date, as Google returns it: a serial number shown as a month."""
    return {"effectiveValue": {"numberValue": serial}, "formattedValue": label}


MONTHS = [_month(45658, "ene 2025"), _month(45689, "feb 2025"), _month(45717, "mar 2025")]
VENTAS = [
    ["Ventas ficticias"],
    ["Cliente", "Fuente de ingreso", "U. Negocio", "POD", *MONTHS, "Ventas 2025"],
    ["Cliente Uno", "Servicio", "Cloud", "Pod Norte", "51234", "52234", "53234"],
    ["Cliente Dos", "Servicio", "Data", "Pod Sur", "61234", "sin dato", "0"],
    ["Cliente Uno", "Soporte", "Cloud", "Pod Norte", "71234", "72234", "73234"],
    [None, None, None, None, "81234"],
    ["Total Ingresos", None, None, None, "91234", "92234", "93234"],
]
VENTAS_MES = [
    ["Mes", "Generado por", "Servicios", *MONTHS],
    ["Cliente Tres", "Alguien", "Suscripción", "41234", "42234", "0"],
    ["General", None, None, "31234"],
    ["Cliente Cuatro", "Alguien", "Onboarding", "21234", None, "23234"],
    ["Total Ingresos", None, None, "11234", "12234", "13234"],
]
PAGOS_ARG = [
    ["Dolar oficial", "1011.25", "1022.25", "1033.25"],
    ["Mes", *MONTHS],
    ["Cliente Pago", "64321", "65321", "66321"],
    ["MEP", "1187.25", "1198.25", "1209.25"],
    ["Dolar Divisa VTA", "1111.75", "1122.75", "1133.75"],
    ["MEP", "1187.25", "1198.25", "1209.25"],
    ["Mes", *MONTHS],
    ["Total Ingresos", "64321", "65321", "66321"],
]
AMOUNTS = [x for rows in (VENTAS, VENTAS_MES, PAGOS_ARG) for row in rows for x in row if x]
AMOUNTS = [x for x in AMOUNTS if isinstance(x, str) and x.replace(".", "").isdigit() and x != "0"]


def _sheet(sheet_id, title, rows):
    """rows: texts, header cells (dicts) or None for an empty cell."""
    tab = _tab(sheet_id, title, "")
    tab["merges"] = []
    values = [
        [{} if x is None else x if isinstance(x, dict) else _value(x) for x in row] for row in rows
    ]
    tab["data"] = [{"rowData": [{"values": row} for row in values]}]
    return tab


@pytest.fixture
def fake(monkeypatch):
    from craftech_os.ingest.google import Google

    fake = FakeGoogle()
    fake.files_by_id["file-a"]["tabs"] = [
        _sheet(11, "VENTAS", VENTAS),
        _sheet(12, "Pagos ARG", PAGOS_ARG),
        _sheet(13, "Cobros", [["Cliente", "ene"], ["Cliente Uno", "51234"]]),
    ]
    fake.files_by_id["file-s"] = {
        "name": "Ventas Mes Ficticias",
        "version": "3",
        "tabs": [_sheet(31, "VENTAS", VENTAS_MES)],
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


def _import(path):
    assert cli.main(["import", "--file", str(path)]) == 0


def _set(fake, sheet_id, rows, file_id="file-a"):
    tabs = fake.files_by_id[file_id]["tabs"]
    i = next(i for i, t in enumerate(tabs) if t["properties"]["sheetId"] == sheet_id)
    tabs[i] = _sheet(sheet_id, tabs[i]["properties"]["title"], rows)
    fake.files_by_id[file_id]["version"] = str(int(fake.files_by_id[file_id]["version"]) + 1)


def _accruals(db, planilla="Cobranzas Ficticias"):
    return db.execute(
        """
        SELECT bloque, clave_fila, serie, mes, monto_usd, unidad_negocio, pod, celda, cliente
        FROM mcp.devengados WHERE planilla = %s ORDER BY celda
        """,
        (planilla,),
    ).fetchall()


def _rates(db):
    return db.execute(
        "SELECT tipo, mes, valor, tipo_a_confirmar FROM mcp.cotizaciones ORDER BY tipo, mes"
    ).fetchall()


def _issues(db, issue_type):
    """(stable key without the tab id, details) of the problems of a type."""
    return db.execute(
        "SELECT regexp_replace(stable_key, '^[0-9]+:', ''), details FROM issue"
        " WHERE issue_type = %s ORDER BY stable_key",
        (issue_type,),
    ).fetchall()


def test_ventas_with_a_cliente_header_gives_one_accrual_per_client_row_and_month(db, env, fake):
    _import(env)
    rows = _accruals(db)
    uno = ("Cliente", "cliente uno", 1)
    assert [r[:5] for r in rows if r[:3] == uno] == [
        (*uno, JAN, Decimal("51234")),
        (*uno, FEB, Decimal("52234")),
        (*uno, MAR, Decimal("53234")),
    ]
    assert {r[5:7] for r in rows if r[1] == "cliente dos"} == {("Data", "Pod Sur")}
    # The unreadable amount gives no accrual; a zero is an accrual.
    assert [(r[3], r[4], r[7]) for r in rows if r[1] == "cliente dos"] == [
        (JAN, Decimal("61234"), "E4"),
        (MAR, Decimal("0"), "G4"),
    ]
    assert not [r for r in rows if r[0] != "Cliente"]  # nothing from Total Ingresos
    assert len(rows) == 3 + 2 + 3
    (lectura,) = db.execute("SELECT DISTINCT lectura_id FROM mcp.devengados").fetchone()
    assert db.execute(
        "SELECT texto FROM mcp.celdas WHERE lectura_id = %s AND celda = 'E3'", (lectura,)
    ).fetchone() == ("51234",)


def test_a_repeated_client_is_a_second_series_to_be_reviewed(db, env, fake):
    _import(env)
    second = [r for r in _accruals(db) if r[2] == 2]
    assert [(r[1], r[4], r[7]) for r in second] == [
        ("cliente uno (2)", Decimal("71234"), "E5"),
        ("cliente uno (2)", Decimal("72234"), "F5"),
        ("cliente uno (2)", Decimal("73234"), "G5"),
    ]
    assert _issues(db, "identidad_en_revision") == [
        ("Cliente:cliente uno", {"block": "Cliente", "rows": 2})
    ]


def test_unreadable_amounts_and_rows_with_amounts_and_no_client_are_problems(db, env, fake):
    _import(env)
    assert ("Cliente:cliente dos:feb 2025", {"cell_ref": "F4"}) in _issues(db, "valor_ilegible")
    assert _issues(db, "fila_sin_interpretar") == [
        ("Cliente:fila 6", {"block": "Cliente", "row": 6}),
        ("General:fila 3", {"block": "General", "row": 3}),
    ]


def test_ventas_with_a_mes_header_and_a_general_block(db, env, fake):
    _import(env)
    rows = _accruals(db, "Ventas Mes Ficticias")
    assert [(r[0], r[1], r[3], r[4], r[5], r[6]) for r in rows] == [
        ("Mes", "cliente tres", JAN, Decimal("41234"), None, None),
        ("General", "cliente cuatro", JAN, Decimal("21234"), None, None),
        ("Mes", "cliente tres", FEB, Decimal("42234"), None, None),
        ("Mes", "cliente tres", MAR, Decimal("0"), None, None),
        ("General", "cliente cuatro", MAR, Decimal("23234"), None, None),
    ]


def test_a_client_without_alias_shows_up_once_the_alias_is_loaded(db, env, fake, tmp_path):
    _import(env)
    unknown = _issues(db, "alias_sin_cliente")
    assert ("cliente uno", {"source": "Cobranzas Ficticias / VENTAS", "text": "cliente uno"}) in (
        unknown
    )
    assert {r[8] for r in _accruals(db)} == {None}
    path = tmp_path / "aliases.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(
            [
                ["fuente", "texto", "cliente", "decidio", "motivo"],
                ["cobranzas ficticias / Ventas", "CLIENTE  Uno", "Ficticia Uno", "Ariel", "test"],
            ]
        )
    assert cli.main(["aliases", "load", str(path)]) == 0
    clients = {(r[1], r[8]) for r in _accruals(db)}
    assert clients == {
        ("cliente uno", "Ficticia Uno"),
        ("cliente uno (2)", "Ficticia Uno"),
        ("cliente dos", None),
    }
    assert cli.main(["interpret", "--all"]) == 0
    texts = [details["text"] for _, details in _issues(db, "alias_sin_cliente")]
    assert "cliente uno" in texts  # already open; it is not opened twice


def test_rates_are_found_by_their_text(db, env, fake):
    _import(env)
    expected = [
        ("mep", JAN, Decimal("1187.25"), False),
        ("mep", FEB, Decimal("1198.25"), False),
        ("mep", MAR, Decimal("1209.25"), False),
        ("oficial", JAN, Decimal("1011.25"), True),
        ("oficial", FEB, Decimal("1022.25"), True),
        ("oficial", MAR, Decimal("1033.25"), True),
    ]
    assert _rates(db) == expected
    assert db.execute(
        "SELECT celda FROM mcp.cotizaciones WHERE tipo = 'mep' ORDER BY mes"
    ).fetchall() == [("B6",), ("C6",), ("D6",)]
    assert _issues(db, "cotizacion_tipo_a_confirmar") == [("oficial", {"rate_type": "oficial"})]
    assert _issues(db, "cotizacion_discrepante") == []
    shifted = [["Nota ficticia"], *PAGOS_ARG[:3], ["Otra fila"], *PAGOS_ARG[3:]]
    _set(fake, 12, shifted)
    _import(env)
    assert _rates(db) == expected
    assert db.execute(
        "SELECT celda FROM mcp.cotizaciones WHERE tipo = 'mep' ORDER BY mes"
    ).fetchall() == [("B8",), ("C8",), ("D8",)]


def test_a_control_mep_that_differs_from_the_operational_one_is_a_problem(db, env, fake):
    discrepant = [row[:] for row in PAGOS_ARG]
    discrepant[3][2] = "1199.75"
    _set(fake, 12, discrepant)
    _import(env)
    assert _issues(db, "cotizacion_discrepante") == [
        ("mep:2025-02", {"month": "2025-02-01", "control": "C4", "operativa": "C6"})
    ]
    assert ("mep", FEB, Decimal("1198.25"), False) in _rates(db)


def test_interpret_twice_leaves_the_same_rows_and_problems(db, env, fake, capsys):
    _import(env)

    def state():
        return (
            db.execute(
                "SELECT source_tab_id, block, row_key, series_order, month, amount_usd,"
                " business_unit, pod, alias_source, alias_text, snapshot_id, cell_ref,"
                " rules_version FROM accrual ORDER BY cell_ref, source_tab_id"
            ).fetchall(),
            db.execute(
                "SELECT rate_type, month, source_tab_id, value, type_to_confirm, snapshot_id,"
                " cell_ref, rules_version FROM fx_rate ORDER BY rate_type, month"
            ).fetchall(),
            db.execute("SELECT issue_type, stable_key, details FROM issue ORDER BY id").fetchall(),
        )

    before = state()
    assert cli.main(["interpret", "--all"]) == 0
    assert cli.main(["interpret", "--all"]) == 0
    assert state() == before
    out = capsys.readouterr().out
    assert "3 tabs interpreted" in out
    assert not any(amount in out for amount in AMOUNTS)


def test_a_tab_without_interpreter_is_not_touched(db, env, fake):
    _import(env)
    (cobros,) = db.execute("SELECT id FROM source_tab WHERE name = 'Cobros'").fetchone()
    (snapshot,) = db.execute(
        "SELECT id FROM snapshot WHERE source_tab_id = %s", (cobros,)
    ).fetchone()
    assert interpret.run(db, snapshot) is None
    assert cli.main(["interpret", "--tab", str(cobros)]) == 0
    for table in ("accrual", "fx_rate"):
        assert db.execute(
            f"SELECT count(*) FROM {table} WHERE source_tab_id = %s", (cobros,)
        ).fetchone() == (0,)
    interpreted = db.execute(
        "SELECT DISTINCT source_tab_id FROM system_event WHERE kind = 'tab_interpreted'"
    ).fetchall()
    assert (cobros,) not in interpreted and len(interpreted) == 3


def test_a_new_read_replaces_the_accruals_of_the_previous_one(db, env, fake):
    _import(env)
    edited = [row[:] for row in VENTAS]
    edited[2][5] = "52299"
    _set(fake, 11, edited)
    _import(env)
    rows = _accruals(db)
    assert (FEB, Decimal("52299")) in [(r[3], r[4]) for r in rows if r[1] == "cliente uno"]
    assert Decimal("52234") not in [r[4] for r in rows]
    assert len(rows) == 8
    (latest,) = db.execute(
        "SELECT max(n.id) FROM snapshot n JOIN source_tab t ON t.id = n.source_tab_id"
        " JOIN source s ON s.id = t.source_id"
        " WHERE t.name = 'VENTAS' AND s.title = 'Cobranzas Ficticias'"
    ).fetchone()
    assert db.execute(
        "SELECT DISTINCT lectura_id FROM mcp.devengados WHERE planilla = 'Cobranzas Ficticias'"
    ).fetchall() == [(latest,)]


def test_events_count_facts_and_time_and_nothing_carries_amounts(db, env, fake):
    discrepant = [row[:] for row in PAGOS_ARG]
    discrepant[3][2] = "1199.75"
    _set(fake, 12, discrepant)
    _import(env)
    events = db.execute(
        "SELECT duration_ms, details FROM system_event WHERE kind = 'tab_interpreted'"
    ).fetchall()
    assert len(events) == 3 and all(ms is not None for ms, _ in events)
    counts = sorted((d["accruals"], d["fx_rates"]) for _, d in events)
    assert counts == [(0, 6), (5, 0), (8, 0)]
    details = [d for (d,) in db.execute("SELECT details FROM issue")]
    logged = json.dumps([d for _, d in events] + details)
    assert not any(amount in logged for amount in AMOUNTS + ["1199.75"])
