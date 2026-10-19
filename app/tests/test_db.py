import shutil
import threading

import psycopg
import pytest

from craftech_os import cli, sources
from craftech_os.migrate import MIGRATIONS_DIR, MigrationError, migrate

TABLES = [
    "annotation",
    "cell_change",
    "drive_activity",
    "editor_profile",
    "issue",
    "issue_resolution",
    "read_request",
    "schema_migration",
    "snapshot",
    "source",
    "source_tab",
    "system_event",
]
MIGRATIONS = [
    "0001_sources.sql",
    "0002_snapshot.sql",
    "0003_read_request.sql",
    "0004_cell_change_issue.sql",
    "0005_drive_activity.sql",
    "0006_mcp_roles_views.sql",
    "0007_mcp_cells.sql",
]


def test_migrate_creates_tables_and_is_idempotent(db):
    assert migrate(db) == MIGRATIONS
    assert migrate(db) == []
    rows = db.execute(
        "SELECT table_name FROM information_schema.tables"
        " WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
    ).fetchall()
    assert sorted(r[0] for r in rows) == TABLES


def test_changed_applied_migration_is_an_error_naming_the_file(db, tmp_path):
    for f in MIGRATIONS_DIR.glob("*.sql"):
        shutil.copy(f, tmp_path)
    migrate(db, tmp_path)
    with (tmp_path / "0001_sources.sql").open("a") as f:
        f.write("\n-- edited\n")
    with pytest.raises(MigrationError, match="0001_sources.sql"):
        migrate(db, tmp_path)


def test_a_failing_migration_leaves_nothing_behind(db, tmp_path):
    (tmp_path / "0001_ok.sql").write_text("CREATE TABLE ok (id int);")
    (tmp_path / "0002_broken.sql").write_text("CREATE TABLE half (id int); SELECT nope;")
    with pytest.raises(Exception, match="nope"):
        migrate(db, tmp_path)
    applied = db.execute("SELECT name FROM schema_migration").fetchall()
    assert applied == [("0001_ok.sql",)]
    assert db.execute("SELECT to_regclass('half')").fetchone() == (None,)


def test_every_table_and_column_has_a_comment(db):
    migrate(db)
    missing = db.execute(
        """
        SELECT c.relname, a.attname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'public'
        JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
        WHERE c.relkind = 'r' AND coalesce(col_description(c.oid, a.attnum), '') = ''
        UNION ALL
        SELECT c.relname, NULL
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'public'
        WHERE c.relkind = 'r' AND coalesce(obj_description(c.oid, 'pg_class'), '') = ''
        """
    ).fetchall()
    assert missing == []
    assert "planilla" in db.execute("SELECT obj_description('source'::regclass)").fetchone()[0]


def _tabs(db):
    return db.execute(
        "SELECT s.title, t.name, t.class, t.active FROM source_tab t"
        " JOIN source s ON s.id = t.source_id ORDER BY s.title, t.name"
    ).fetchall()


def test_load_real_config_twice_without_duplicates(db):
    migrate(db)
    parsed = sources.parse(sources.SOURCES_FILE.read_text(encoding="utf-8"))
    sources.load(db, parsed)
    sources.load(db, parsed)
    assert db.execute("SELECT count(*) FROM source").fetchone() == (20,)
    tabs = _tabs(db)
    assert len(tabs) == 244
    assert sum(cls == "A_CONFIRMAR" for _, _, cls, _ in tabs) == 12
    assert ("Facturación - Craftech Total", "Gastos", "A_CONFIRMAR", True) in tabs
    pnl = db.execute("SELECT default_class FROM source WHERE title = 'P&L - DATA'").fetchone()
    assert pnl == ("DERIVADA",)
    with_schema = db.execute(
        "SELECT s.title, t.name, t.class FROM source_tab t JOIN source s ON s.id = t.source_id"
        " WHERE t.schema IS NOT NULL ORDER BY s.title, t.name"
    ).fetchall()
    assert [(title[:13], name, cls) for title, name, cls in with_schema] == [
        ("Facturación -", "Pagos", "CARGA"),
        ("Facturación -", "Pagos ARG", "CARGA"),
        ("Facturación -", "VENTAS", "CARGA"),
        ("Facturación -", "Pagos", "CARGA"),
        ("Facturación -", "Pagos ARG", "CARGA"),
        ("Facturación -", "VENTAS", "CARGA"),
        ("FUNDINGS - Lo", "FUNDINGS", "CARGA"),
    ]


def test_removed_tab_becomes_inactive_and_comes_back(db):
    migrate(db)
    sources.load(db, sources.parse("sources: [{title: A, tabs: {CARGA: [x, y]}}]"))
    sources.load(db, sources.parse("sources: [{title: A, tabs: {HISTORICA: [x]}}]"))
    assert _tabs(db) == [("A", "x", "HISTORICA", True), ("A", "y", "CARGA", False)]
    sources.load(db, sources.parse("sources: [{title: A, tabs: {CARGA: [x, y]}}]"))
    assert _tabs(db) == [("A", "x", "CARGA", True), ("A", "y", "CARGA", True)]


def test_removed_source_deactivates_all_its_tabs(db):
    migrate(db)
    sources.load(
        db,
        sources.parse("sources: [{title: A, tabs: {CARGA: [x]}}, {title: B, tabs: {CARGA: [y]}}]"),
    )
    sources.load(db, sources.parse("sources: [{title: A, tabs: {CARGA: [x]}}]"))
    assert _tabs(db) == [("A", "x", "CARGA", True), ("B", "y", "CARGA", False)]
    assert dict((t, c) for t, _, c in sources.summary(db)) == {"A": {"CARGA": 1}, "B": {}}


def test_source_switched_to_all_tabs_takes_that_class(db):
    migrate(db)
    sources.load(db, sources.parse("sources: [{title: A, tabs: {CARGA: [x]}}]"))
    sources.load(db, sources.parse("sources: [{title: A, all_tabs: DERIVADA}]"))
    assert _tabs(db) == [("A", "x", "DERIVADA", True)]


def test_all_tabs_source_keeps_tabs_registered_on_read(db):
    migrate(db)
    sources.load(db, sources.parse("sources: [{title: P, all_tabs: DERIVADA}]"))
    db.execute(
        "INSERT INTO source_tab (source_id, name, class)"
        " SELECT id, 'read later', 'DERIVADA' FROM source WHERE title = 'P'"
    )
    sources.load(db, sources.parse("sources: [{title: P, all_tabs: DERIVADA}]"))
    assert _tabs(db) == [("P", "read later", "DERIVADA", True)]


def test_renamed_source_keeps_its_drive_id(db):
    migrate(db)
    sources.load(db, sources.parse("sources: [{title: A, drive_id: x, all_tabs: CARGA}]"))
    sources.load(db, sources.parse("sources: [{title: B, drive_id: x, all_tabs: CARGA}]"))
    rows = db.execute("SELECT title, drive_id FROM source ORDER BY title").fetchall()
    assert rows == [("A", None), ("B", "x")]


def test_cli_end_to_end(db, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", db.info.dsn + " password=" + (db.info.password or ""))
    assert cli.main(["migrate"]) == 0
    assert "applied 0001_sources.sql" in capsys.readouterr().out
    assert cli.main(["migrate"]) == 0
    assert "nothing to apply" in capsys.readouterr().out
    assert cli.main(["sources", "load"]) == 0
    assert "20 sources and 244 named tabs" in capsys.readouterr().out
    assert cli.main(["sources", "list"]) == 0
    out = capsys.readouterr().out
    facturacion = "CARGA 5, DERIVADA 14, HISTORICA 22, IGNORAR 5, A_CONFIRMAR 1"
    assert f"'Facturación - Craftech Total': {facturacion}\n" in out
    assert "'P&L - DATA': all tabs DERIVADA" in out
    assert out.strip().endswith("20 sources")


def test_cli_reports_invalid_yaml_with_exit_code_1(db, monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("DATABASE_URL", db.info.dsn + " password=" + (db.info.password or ""))
    bad = tmp_path / "sources.yaml"
    bad.write_text("sources: [{title: A, all_tabs: NOPE}]")
    assert cli.main(["sources", "load", "--file", str(bad)]) == 1
    assert "unknown class 'NOPE'" in capsys.readouterr().err


def test_concurrent_migrate_on_empty_database_both_succeed(db):
    dsn = db.info.dsn + " password=" + (db.info.password or "")
    barrier = threading.Barrier(2)
    results, errors = [], []

    def run():
        with psycopg.connect(dsn, autocommit=True) as conn:
            barrier.wait()
            try:
                results.append(migrate(conn))
            except Exception as e:
                errors.append(e)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert sorted(results) == [[], MIGRATIONS]


def test_cli_reports_unreadable_or_malformed_input_with_exit_code_1(monkeypatch, capsys, tmp_path):
    bad = tmp_path / "sources.yaml"
    bad.write_text("sources: [")
    assert cli.main(["sources", "load", "--file", str(bad)]) == 1
    assert "invalid YAML" in capsys.readouterr().err
    assert cli.main(["sources", "load", "--file", str(tmp_path / "missing.yaml")]) == 1
    assert "missing.yaml" in capsys.readouterr().err
    monkeypatch.setenv("DATABASE_URL", "garbage")
    with pytest.raises(SystemExit, match="DATABASE_URL is not a valid connection string"):
        cli.main(["sources", "list"])


def test_cli_without_database_url_fails(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(SystemExit, match="DATABASE_URL is not set"):
        cli.main(["migrate"])
