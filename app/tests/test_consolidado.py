"""Bank movements of the Consolidado tab of "Base informe Craftech " (T-018, ADR-003).

Against the test database. Invented details and amounts only; banks and rubros are labels.
"""

import json
from datetime import date
from decimal import Decimal

import psycopg
import pytest
import yaml
from test_import import FakeGoogle
from test_interpret import _import, _issues, _month, _set, _sheet

from craftech_os.interpret import consolidado, interpreter
from craftech_os.migrate import migrate
from craftech_os.sources import SOURCES_FILE, SourcesError, parse

TITLE = "Base informe Craftech "
REAL = next(s for s in parse(SOURCES_FILE.read_text(encoding="utf-8")) if s["title"] == TITLE)
SCHEMA = REAL["schemas"]["Consolidado"]
SOURCES = yaml.safe_dump(
    {
        "sources": [
            {
                "title": TITLE,
                "drive_id": "file-b",
                "tabs": {"CARGA": ["Consolidado"]},
                "schemas": {"Consolidado": SCHEMA},
            },
            {
                "title": "Budget Ficticio",
                "drive_id": "file-g",
                "tabs": {"DERIVADA": ["Consolidado"]},
            },
        ]
    },
    allow_unicode=True,
)
HEADERS = list(SCHEMA["columns"].values())
JAN = _month(46023, "ene-2026", '" "mmm"-"yyyy')
FEB = _month(46054, "feb-2026", '" "mmm"-"yyyy')


def _row(
    bank,
    rubro="04. Alquileres",
    amount="-1234.5",
    *,
    month=JAN,
    tipo="Egresos",
    agrupador="Agrupador Ficticio",
    currency="ARS",
    fx="1000",
    usd="-1.2345",
    detalle="Detalle Ficticio",
    subdetalle="Subdetalle Ficticio",
    equipo="Equipo Ficticio",
):
    """A Consolidado row, in the order of the 17 headers."""
    return [
        month, "Origen Ficticio", bank, "Tipo Ficticio", "Mensual", tipo, rubro, agrupador,
        equipo, currency, amount, fx, usd, detalle, subdetalle, "Area Ficticia", "Fijo",
    ]  # fmt: skip


BANKS = ["GALICIA", "Macro", "Credicoop", "Caja", "MERCURY", "Mesh", "VETA ARG", "CRYPTO"]
ROWS = [HEADERS, *(_row(b) for b in BANKS), _row("CLIENTES"), _row("AFIP")]


@pytest.fixture
def fake(monkeypatch):
    from craftech_os.ingest.google import Google

    fake = FakeGoogle()
    fake.files_by_id["file-b"] = {
        "name": TITLE,
        "version": "1",
        "tabs": [_sheet(41, "Consolidado", ROWS)],
    }
    fake.files_by_id["file-g"] = {
        "name": "Budget Ficticio",
        "version": "1",
        "tabs": [_sheet(51, "Consolidado", ROWS)],
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


def _movements(db):
    return db.execute(
        """
        SELECT m.row_key, m.cell_ref, m.month, m.bank, m.legal_entity, m.historical, m.adjustment,
               m.currency, m.amount, m.fx_rate, m.amount_usd, m.movement_type, m.rubro,
               m.agrupador, m.detalle, m.subdetalle, m.equipo, s.title
        FROM cash_movement m JOIN source_tab t ON t.id = m.source_tab_id
        JOIN source s ON s.id = t.source_id
        ORDER BY m.id
        """
    ).fetchall()


def test_each_row_gives_a_movement_with_the_entity_of_its_bank(db, env, fake):
    _import(env)
    rows = _movements(db)
    assert len(rows) == len(ROWS) - 1
    assert rows[0] == (
        "fila 2", "K2", date(2026, 1, 1), "GALICIA", "Craftech S.A.", False, False, "ARS",
        Decimal("-1234.5"), Decimal("1000"), Decimal("-1.2345"), "Egresos", "04. Alquileres",
        "Agrupador Ficticio", "Detalle Ficticio", "Subdetalle Ficticio", "Equipo Ficticio", TITLE,
    )  # fmt: skip
    assert {r[3]: r[4:7] for r in rows} == {
        "GALICIA": ("Craftech S.A.", False, False),
        "Macro": ("Craftech S.A.", False, False),
        "Credicoop": ("Craftech S.A.", False, False),
        "Caja": ("Craftech S.A.", False, False),
        "MERCURY": ("Craftech-io Inc.", False, False),
        "Mesh": ("Craftech-io Inc.", False, False),
        "VETA ARG": (None, True, False),
        "CRYPTO": (None, True, False),
        "CLIENTES": (None, False, True),
        "AFIP": (None, False, True),
    }
    assert _issues(db, "cash_unknown_bank") == []
    assert _issues(db, "cash_unmapped_rubro") == []


def test_only_the_consolidado_of_base_informe_is_interpreted(db, env, fake):
    _import(env)
    assert {r[-1] for r in _movements(db)} == {TITLE}
    assert interpreter(TITLE, "Consolidado") is consolidado.interpret
    assert interpreter("Budget Ficticio", "Consolidado") is None
    assert interpreter("Otra Planilla", "Pagos") is not None


def test_an_unknown_bank_is_a_problem_and_its_row_has_no_entity(db, env, fake):
    _set(
        fake,
        41,
        [HEADERS, _row("Banco Ficticio"), _row("Banco Ficticio"), _row("GALICIA")],
        "file-b",
    )
    _import(env)
    assert [r[3:5] for r in _movements(db)] == [
        ("Banco Ficticio", None),
        ("Banco Ficticio", None),
        ("GALICIA", "Craftech S.A."),
    ]
    assert _issues(db, "cash_unknown_bank") == [
        (
            "Banco Ficticio",
            {"planilla": TITLE, "pestaña": "Consolidado", "banco": "Banco Ficticio", "filas": 2,
             "cell_ref": "C2"},
        )
    ]  # fmt: skip


def test_other_headers_are_a_problem_and_keep_the_last_good_movements(db, env, fake):
    _import(env)
    before = _movements(db)
    _set(fake, 41, [["Mes Corriente", "Otra Columna"], _row("GALICIA")], "file-b")
    _import(env)
    assert _movements(db) == before
    ((key, details),) = _issues(db, "cash_header_mismatch")
    assert key == "encabezados"
    assert details == {"planilla": TITLE, "pestaña": "Consolidado", "esperadas": 17,
                       "encontradas": 2}  # fmt: skip
    # An old read without the header row at all is the same problem.
    _set(fake, 41, [["Otra cosa"], _row("GALICIA")], "file-b")
    _import(env)
    assert _movements(db) == before
    assert len(_issues(db, "cash_header_mismatch")) == 1


def test_a_rubro_without_a_rule_is_a_problem(db, env, fake):
    rows = [HEADERS, _row("GALICIA", "99. Rubro Ficticio"), _row("Mesh", "99. Rubro Ficticio")]
    _set(fake, 41, rows, "file-b")
    _import(env)
    assert len(_movements(db)) == 2
    assert _issues(db, "cash_unmapped_rubro") == [
        (
            "99. Rubro Ficticio",
            {"planilla": TITLE, "pestaña": "Consolidado", "rubro": "99. Rubro Ficticio",
             "agrupador": "Agrupador Ficticio", "filas": 2, "cell_ref": "G2"},
        )
    ]  # fmt: skip


def test_sueldos_keep_no_detail_and_no_name_reaches_problems_or_events(db, env, fake):
    name = "Persona Ficticia Zeta"
    sueldo = _row(
        "Banco Ficticio", "01. Sueldos", tipo="Sueldos", agrupador="CCSS", detalle=name,
        subdetalle=name, equipo=name,
    )  # fmt: skip
    unreadable = _row("GALICIA", "01. Sueldos", "sin dato", tipo="Sueldos", detalle=name)
    # Tipo Mov "Sueldos" under another rubro can name a person too.
    other_rubro = _row("GALICIA", "CCSS", tipo="Sueldos", agrupador=name, detalle=name)
    lowercase = _row("GALICIA", "CCSS", tipo="sueldos", agrupador=name, detalle=name)
    _set(
        fake, 41, [HEADERS, sueldo, unreadable, other_rubro, lowercase, _row("GALICIA")], "file-b"
    )  # fmt: skip
    _import(env)
    rows = _movements(db)
    assert [r[14:17] for r in rows] == [
        (None, None, None),
        (None, None, None),
        (None, None, None),
        (None, None, None),
        ("Detalle Ficticio", "Subdetalle Ficticio", "Equipo Ficticio"),
    ]
    assert rows[1][8] is None
    assert _issues(db, "valor_ilegible") == [("fila 3:Amount", {"cell_ref": "K3"})]
    assert _issues(db, "cash_unknown_bank")
    (in_issues,) = db.execute(
        "SELECT count(*) FROM issue WHERE details::text LIKE '%Zeta%'"
    ).fetchone()
    (in_events,) = db.execute(
        "SELECT count(*) FROM system_event WHERE details::text LIKE '%Zeta%'"
    ).fetchone()
    assert (in_issues, in_events) == (0, 0)


@pytest.mark.parametrize(
    "rubro, movement_type", [("01. Sueldos", "Egresos"), ("04. Alquileres", "Sueldos")]
)
def test_the_database_rejects_a_sueldos_row_with_detail(db, env, fake, rubro, movement_type):
    _import(env)
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(
            "INSERT INTO cash_movement (source_tab_id, snapshot_id, rules_version, row_key,"
            " cell_ref, month, bank, historical, adjustment, rubro, movement_type, equipo)"
            " SELECT source_tab_id, snapshot_id, rules_version, 'fila 99', 'K99', month, bank,"
            " false, false, %s, %s, 'Equipo Ficticio' FROM cash_movement LIMIT 1",
            (rubro, movement_type),
        )


def test_the_transfer_from_mercury_to_mesh_is_internal(db, env, fake):
    transfer = _row("MERCURY", "CAJA. Mesh", tipo="Egresos", agrupador="MESH", currency="USD")
    fee = _row("Mesh", "CAJA. Mesh", tipo="Egresos", agrupador="Comisiones", currency="USD")
    _set(fake, 41, [HEADERS, transfer, fee], "file-b")
    _import(env)
    assert [r[11] for r in _movements(db)] == ["Interno", "Egresos"]


def test_an_unknown_movement_type_or_currency_is_kept_and_reported(db, env, fake):
    rows = [HEADERS, _row("GALICIA", tipo="Tipo Ficticio"), _row("GALICIA", currency="XYZ")]
    _set(fake, 41, rows, "file-b")
    _import(env)
    assert [(r[7], r[11]) for r in _movements(db)] == [("ARS", None), (None, "Egresos")]
    assert [k for k, _ in _issues(db, "fila_sin_interpretar")] == [
        "fila 2:Tipo Mov",
        "fila 3:Moneda",
    ]


def test_a_new_read_replaces_all_movements_and_records_counts(db, env, fake):
    _import(env)
    _set(fake, 41, [HEADERS, _row("GALICIA", month=FEB), _row("Banco Ficticio")], "file-b")
    _import(env)
    rows = _movements(db)
    assert [(r[2], r[3]) for r in rows] == [
        (date(2026, 2, 1), "GALICIA"),
        (date(2026, 1, 1), "Banco Ficticio"),
    ]
    duration_ms, details = db.execute(
        "SELECT duration_ms, details FROM system_event WHERE kind = 'tab_interpreted'"
        " AND details->>'movements' IS NOT NULL ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert details["movements"] == 2 and details["issues"] == 1
    assert isinstance(duration_ms, int)
    assert set(details) <= {
        "snapshot_id", "accruals", "fx_rates", "invoices", "payments", "churn",
        "fundings", "movements", "issues",
    }  # fmt: skip


def test_cashflow_rows_hold_labels_only():
    def scalars(node):
        if isinstance(node, dict):
            for k, v in node.items():
                yield k
                yield from scalars(v)
        elif isinstance(node, list):
            for v in node:
                yield from scalars(v)
        else:
            yield node

    raw = yaml.safe_load(consolidado.ROWS_FILE.read_text(encoding="utf-8"))
    assert all(isinstance(x, str) for x in scalars(raw))
    rules = consolidado.rules()
    gastos = next(
        r for r in rules if r["block"] == "Argentina en miles de pesos" and r["label"] == "Gastos"
    )
    assert "01. Sueldos" in gastos["rubros"] and "04. Alquileres" in gastos["rubros"]
    sin_regla = [r for r in rules if not (r["rubros"] or r["agrupadores"] or r["banks"])]
    assert {"Ventas en $", "Saldo Final en USD"} <= {r["label"] for r in sin_regla}


def test_cashflow_rows_reject_amounts(tmp_path):
    path = tmp_path / "rows.yaml"
    path.write_text("blocks:\n  - name: x\n    rows:\n      - label: y\n        rubros: [1500]\n")
    with pytest.raises(ValueError):
        consolidado.rules(path)


@pytest.mark.parametrize(
    "change",
    [
        lambda s: s["columns"].pop("rubro"),
        lambda s: s["banks"].update({"GALICIA": ""}),
        lambda s: s.pop("banks"),
    ],
)
def test_the_consolidado_schema_is_validated(change):
    schema = json.loads(json.dumps(SCHEMA))
    change(schema)
    text = yaml.safe_dump(
        {
            "sources": [
                {
                    "title": TITLE,
                    "tabs": {"CARGA": ["Consolidado"]},
                    "schemas": {"Consolidado": schema},
                }
            ]
        }
    )
    with pytest.raises(SourcesError):
        parse(text)
