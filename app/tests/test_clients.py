"""Canonical clients: the 0008 seed and the Zoho and alias loaders, with invented data only."""

import csv

import pytest

from craftech_os import cli
from craftech_os.migrate import migrate

ZOHO_HEADER = [
    "Display Name",
    "Company Name",
    "Payment Terms",
    "Billing Country",
    "CF.Código Tax ID",
    "CF.TIPO DE TAX ID",
]
ZOHO_ROWS = [
    ["Ficticia Uno LLC", "Ficticia Uno LLC", "Net 10", "U.S.A.", "00-0000001", "EIN"],
    ["Inventada Dos", "Inventada Dos S.A. de C.V.", "Due on Receipt", "Mexico", "", ""],
    ["Ejemplo Tres", "Ejemplo Tres SpA", "Net 30", "Chile", "", ""],
    ["", "", "Net 10", "", "", ""],
]
NAMES = ("Ficticia", "Inventada", "Ejemplo", "Cliente Nuevo", "00-0000001")


@pytest.fixture
def env(db, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", db.info.dsn + " password=" + (db.info.password or ""))
    migrate(db)


def _write(path, header, rows):
    # Zoho exports with a byte order mark.
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows([header, *rows])
    return path


def _events(db, kind):
    return [d for (d,) in db.execute("SELECT details FROM system_event WHERE kind = %s", (kind,))]


def test_the_seed_has_both_craftech_legal_entities(env, db):
    rows = db.execute("SELECT name, country, billing_system FROM legal_entity ORDER BY id")
    assert rows.fetchall() == [
        ("Craftech S.A.", "Argentina", "bejerman"),
        ("Craftech-io Inc.", "Estados Unidos", "zoho"),
    ]


def test_load_zoho_creates_clients_once_and_logs_counts_only(env, db, tmp_path, capsys):
    path = _write(tmp_path / "Contacts.csv", ZOHO_HEADER, ZOHO_ROWS)
    assert cli.main(["clients", "load-zoho", str(path)]) == 0
    first = capsys.readouterr().out
    rows = db.execute(
        "SELECT c.name, e.legal_name, e.country, e.tax_id_type, e.tax_id, e.source_system,"
        " e.payment_terms_days FROM client_legal_entity e JOIN client c ON c.id = e.client_id"
        " ORDER BY e.id"
    ).fetchall()
    assert rows == [
        ("Ficticia Uno LLC", "Ficticia Uno LLC", "U.S.A.", "EIN", "00-0000001", "zoho", 10),
        ("Inventada Dos", "Inventada Dos S.A. de C.V.", "Mexico", None, None, "zoho", 0),
        ("Ejemplo Tres", "Ejemplo Tres SpA", "Chile", None, None, "zoho", 30),
    ]
    assert cli.main(["clients", "load-zoho", str(path)]) == 0
    second = capsys.readouterr().out
    assert "3 created" in first and "1 skipped" in first
    assert "0 created, 0 updated, 4 skipped" in second
    assert db.execute("SELECT count(*) FROM client").fetchone() == (3,)
    events = _events(db, "clients_loaded")
    assert events[1] == {"read": 4, "created": 0, "updated": 0, "skipped": 4}
    for text in (first, second, str(events)):
        assert not any(name in text for name in NAMES)


def test_load_zoho_updates_a_known_tax_id_or_razon_social(env, db, tmp_path, capsys):
    _write(tmp_path / "a.csv", ZOHO_HEADER, ZOHO_ROWS[:2])
    cli.main(["clients", "load-zoho", str(tmp_path / "a.csv")])
    changed = [
        ["Ficticia Uno LLC", "Ficticia Uno Holdings LLC", "Net 10", "U.S.A.", "00-0000001", "EIN"],
        ["Inventada Dos", "INVENTADA DOS S.A. de C.V.", "Net 10", "Mexico", "", ""],
    ]
    _write(tmp_path / "b.csv", ZOHO_HEADER, changed)
    cli.main(["clients", "load-zoho", str(tmp_path / "b.csv")])
    assert "0 created, 2 updated" in capsys.readouterr().out
    rows = db.execute(
        "SELECT legal_name, payment_terms_days FROM client_legal_entity ORDER BY id"
    ).fetchall()
    assert rows == [("Ficticia Uno Holdings LLC", 10), ("INVENTADA DOS S.A. de C.V.", 10)]


ALIAS_HEADER = ["fuente", "texto", "cliente", "decidió", "motivo"]


def test_load_aliases_is_idempotent_and_creates_a_missing_client(env, db, tmp_path, capsys):
    _write(tmp_path / "Contacts.csv", ZOHO_HEADER, ZOHO_ROWS[:1])
    cli.main(["clients", "load-zoho", str(tmp_path / "Contacts.csv")])
    rows = [
        ["Cobros", "  FICTICIA  uno ", "ficticia uno llc", "Ariel", "es el mismo cliente"],
        ["Pagos", "Cliente Nuevo", "Cliente Nuevo", "Ariel", "nombre de fantasía"],
    ]
    path = _write(tmp_path / "aliases.csv", ALIAS_HEADER, rows)
    assert cli.main(["aliases", "load", str(path)]) == 0
    assert cli.main(["aliases", "load", str(path)]) == 0
    out = capsys.readouterr().out
    assert "2 created" in out and "0 created, 0 updated, 2 skipped" in out
    assert "1 clients created" in out
    aliases = db.execute(
        "SELECT a.source, a.text, c.name, a.author, a.reason FROM client_alias a"
        " JOIN client c ON c.id = a.client_id ORDER BY a.id"
    ).fetchall()
    assert aliases == [
        ("cobros", "ficticia uno", "Ficticia Uno LLC", "Ariel", "es el mismo cliente"),
        ("pagos", "cliente nuevo", "Cliente Nuevo", "Ariel", "nombre de fantasía"),
    ]
    assert not any(name in out + str(_events(db, "aliases_loaded")) for name in NAMES)


def test_the_latest_alias_decision_wins_and_keeps_the_earlier_one(env, db, tmp_path):
    first = [["Cobros", "Uno", "Inventada Dos", "Ariel", "primera lectura"]]
    cli.main(["aliases", "load", str(_write(tmp_path / "a.csv", ALIAS_HEADER, first))])
    second = [["Cobros", "uno", "Ejemplo Tres", "Emi", "lo corrigió Emi"]]
    cli.main(["aliases", "load", str(_write(tmp_path / "b.csv", ALIAS_HEADER, second))])
    assert db.execute("SELECT count(*) FROM client_alias").fetchone() == (2,)
    assert db.execute(
        "SELECT fuente, texto, cliente, decidio, motivo, decisiones_anteriores FROM mcp.aliases"
    ).fetchall() == [("cobros", "uno", "Ejemplo Tres", "Emi", "lo corrigió Emi", 1)]


def test_an_alias_row_without_who_or_why_loads_nothing(env, db, tmp_path, capsys):
    rows = [
        ["Cobros", "Uno", "Inventada Dos", "Ariel", "ok"],
        ["Cobros", "Dos", "Inventada Dos", "Ariel", "  "],
    ]
    path = _write(tmp_path / "aliases.csv", ALIAS_HEADER, rows)
    assert cli.main(["aliases", "load", str(path)]) == 1
    err = capsys.readouterr().err
    assert "line 3" in err and "Inventada" not in err
    assert db.execute("SELECT count(*) FROM client_alias").fetchone() == (0,)
    assert db.execute("SELECT count(*) FROM client").fetchone() == (0,)


def test_a_csv_without_the_expected_columns_fails(env, tmp_path, capsys):
    path = _write(tmp_path / "x.csv", ["fuente", "texto"], [["Cobros", "Uno"]])
    assert cli.main(["aliases", "load", str(path)]) == 1
    assert "cliente" in capsys.readouterr().err
