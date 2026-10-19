"""Import against the test database, with Drive and Sheets faked in memory. No network."""

from pathlib import Path

import httplib2
import pytest
from googleapiclient.errors import HttpError

from craftech_os import cli
from craftech_os.ingest.google import MAX_RETRIES, Google
from craftech_os.migrate import migrate

APP = Path(__file__).resolve().parents[1] / "craftech_os"
MARKER = "MARCADOR-SECRETO-7731"

SOURCES = """
sources:
  - title: "Cobranzas Ficticias"
    drive_id: "file-a"
    tabs:
      CARGA: ["Cobros", "Borrada"]
  - title: "P&L Ficticio"
    drive_id: "file-p"
    all_tabs: DERIVADA
"""


def _tab(sheet_id, title, text, hidden=False):
    cell = {
        "effectiveValue": {"stringValue": text},
        "formattedValue": text,
        "userEnteredValue": {"formulaValue": '=CONCAT("' + text + '")'},
        "effectiveFormat": {"backgroundColor": {"red": 1}},
    }
    return {
        "properties": {
            "sheetId": sheet_id,
            "title": title,
            "hidden": hidden,
            "gridProperties": {"rowCount": 10, "columnCount": 5},
        },
        "merges": [{"startRowIndex": 0, "endRowIndex": 2, "startColumnIndex": 0}],
        "data": [{"rowData": [{"values": [cell, cell]}]}],
    }


def _http_error(code):
    return HttpError(httplib2.Response({"status": code}), MARKER.encode())


class _Request:
    def __init__(self, fake, key, answer):
        self.fake, self.key, self.answer = fake, key, answer

    def execute(self):
        self.fake.calls.append(self.key)
        failures = self.fake.failures.get(self.key, [])
        if failures:
            failure = failures.pop(0)
            raise failure if isinstance(failure, Exception) else _http_error(failure)
        return self.answer()


class FakeGoogle:
    """Drive's files() and Sheets' spreadsheets(), only the read calls Google uses."""

    def __init__(self):
        self.files_by_id = {
            "file-a": {
                "name": "Cobranzas Ficticias",
                "version": "41",
                "tabs": [
                    _tab(11, "Cobros", MARKER),
                    _tab(12, "Nueva", "otra cosa", hidden=True),
                ],
            },
            "file-p": {
                "name": "P&L Ficticio",
                "version": "7",
                "tabs": [_tab(21, "Resumen", "resumen ficticio")],
            },
        }
        self.failures = {}  # (call, file id, tab title or None) -> statuses or errors, raised first
        self.calls = []
        self.waits = []

    def google(self):
        return Google(self, self, sleep=self.waits.append)

    def files(self):
        return self

    def spreadsheets(self):
        return self

    def list(self, q, **kwargs):
        assert kwargs["supportsAllDrives"] and kwargs["includeItemsFromAllDrives"]
        found = [
            {"id": i, "name": f["name"]}
            for i, f in self.files_by_id.items()
            if f"name = '{f['name']}'" in q
        ]
        return _Request(self, ("list", None, None), lambda: {"files": found})

    def get(self, *, fileId=None, spreadsheetId=None, ranges=None, **kwargs):
        if fileId is not None:
            assert kwargs["supportsAllDrives"]
            f = self.files_by_id[fileId]
            return _Request(
                self,
                ("version", fileId, None),
                lambda: f.get(
                    "drive", {"version": f["version"], "modifiedTime": "2026-10-18T12:00:00.000Z"}
                ),
            )
        tabs = self.files_by_id[spreadsheetId]["tabs"]
        if not kwargs["includeGridData"]:
            return _Request(
                self,
                ("tabs", spreadsheetId, None),
                lambda: {"sheets": [{"properties": t["properties"]} for t in tabs]},
            )
        (quoted,) = ranges
        title = quoted[1:-1].replace("''", "'")
        return _Request(
            self,
            ("grid", spreadsheetId, title),
            lambda: {"sheets": [t for t in tabs if t["properties"]["title"] == title]},
        )


@pytest.fixture
def fake(monkeypatch):
    fake = FakeGoogle()
    monkeypatch.setattr(Google, "from_environment", classmethod(lambda cls: fake.google()))
    return fake


@pytest.fixture
def env(db, monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", db.info.dsn + " password=" + (db.info.password or ""))
    migrate(db)
    path = tmp_path / "sources.yaml"
    path.write_text(SOURCES, encoding="utf-8")
    return path


def _import(path, *extra):
    return cli.main(["import", "--file", str(path), *extra])


def _tabs(db):
    return db.execute(
        "SELECT name, sheet_id, class, active FROM source_tab ORDER BY sheet_id NULLS LAST"
    ).fetchall()


def _events(db, kind):
    return db.execute(
        "SELECT source_tab_id, duration_ms, details FROM system_event WHERE kind = %s ORDER BY id",
        (kind,),
    ).fetchall()


def _snapshots(db):
    return db.execute("SELECT count(*) FROM snapshot").fetchone()[0]


def test_import_stores_one_snapshot_per_tab_and_registers_tabs(db, env, fake, capsys):
    assert _import(env) == 0
    assert _tabs(db) == [
        ("Cobros", 11, "CARGA", True),
        ("Nueva", 12, "SIN_CLASIFICAR", True),
        ("Resumen", 21, "DERIVADA", True),
        ("Borrada", None, "CARGA", False),
    ]
    rows = db.execute(
        """
        SELECT t.name, s.drive_version, s.drive_modified_at IS NOT NULL, s.read_at IS NOT NULL,
               s.duration_ms >= 0, s.origin, length(s.content_hash), s.row_count, s.col_count,
               s.cell_count, s.content->'rows'->0->'cells'->0->>'bg',
               s.content->'rows'->0->'cells'->0 ? 'formula', jsonb_array_length(s.content->'merges')
        FROM snapshot s JOIN source_tab t ON t.id = s.source_tab_id ORDER BY t.sheet_id
        """
    ).fetchall()
    assert rows == [
        (name, version, True, True, True, "lectura", 64, 1, 2, 2, "#ff0000", True, 1)
        for name, version in [("Cobros", 41), ("Nueva", 41), ("Resumen", 7)]
    ]
    assert [e[2]["tab"] for e in _events(db, "tab_unclassified")] == ["Nueva"]
    assert [e[2]["tab"] for e in _events(db, "tab_missing")] == ["Borrada"]
    reads = _events(db, "tab_read")
    assert len(reads) == 3
    assert all(d is not None and e["cell_count"] == 2 and e["stored"] for _, d, e in reads)
    assert len(_events(db, "source_read")) == 2
    out = capsys.readouterr().out
    assert "'Cobranzas Ficticias': 2 stored, 0 unchanged, 0 failed" in out
    assert "slowest tabs:" in out and "'P&L Ficticio' / 'Resumen'" in out


def test_second_import_adds_events_but_no_snapshots_unless_a_tab_changed(db, env, fake):
    assert _import(env) == 0
    assert _import(env) == 0
    assert _snapshots(db) == 3
    reads = _events(db, "tab_read")
    assert len(reads) == 6 and [e["stored"] for _, _, e in reads[3:]] == [False] * 3
    fake.files_by_id["file-p"]["tabs"][0]["merges"] = []
    assert _import(env) == 0
    assert _snapshots(db) == 4
    # The registered tabs keep their sheet_id and class; the unclassified one stays active.
    assert _tabs(db)[1] == ("Nueva", 12, "SIN_CLASIFICAR", True)


def test_sources_load_leaves_tabs_found_in_google_alone(db, env, fake):
    assert _import(env) == 0
    assert cli.main(["sources", "load", "--file", str(env)]) == 0
    assert ("Nueva", 12, "SIN_CLASIFICAR", True) in _tabs(db)
    assert ("Resumen", 21, "DERIVADA", True) in _tabs(db)


def test_no_event_or_output_contains_cell_values(db, env, fake, capsys):
    fake.failures[("grid", "file-p", "Resumen")] = [500] * (MAX_RETRIES + 1)
    assert _import(env) == 1
    assert _import(env, "--source", "Cobranzas Ficticias") == 0
    captured = capsys.readouterr()
    assert MARKER not in captured.out + captured.err
    assert db.execute("SELECT count(*) FROM system_event").fetchone()[0] > 0
    leaked = db.execute(
        "SELECT count(*) FROM system_event WHERE details::text LIKE %s", (f"%{MARKER}%",)
    ).fetchone()
    assert leaked == (0,)
    # The marker is in the stored content, so the check above can fail.
    stored = db.execute(
        "SELECT count(*) FROM snapshot WHERE content::text LIKE %s", (f"%{MARKER}%",)
    ).fetchone()
    assert stored == (1,)


def test_quota_errors_are_retried_with_growing_waits(db, env, fake):
    fake.failures[("grid", "file-a", "Cobros")] = [429, 503]
    assert _import(env) == 0
    assert fake.waits == [1, 2]
    retries = [e for _, _, e in _events(db, "google_retry")]
    assert retries == [
        {"call": "sheets.get", "status": 429, "attempt": 1, "wait_s": 1},
        {"call": "sheets.get", "status": 503, "attempt": 2, "wait_s": 2},
    ]
    assert _snapshots(db) == 3


def test_a_tab_that_keeps_failing_is_reported_and_the_import_continues(db, env, fake, capsys):
    fake.failures[("grid", "file-a", "Cobros")] = [429] * (MAX_RETRIES + 1)
    assert _import(env) == 1
    assert fake.waits == [2**i for i in range(MAX_RETRIES)]
    assert len(_events(db, "google_retry")) == MAX_RETRIES
    (failed,) = _events(db, "tab_failed")
    assert failed[2] == {"error": "HttpError", "status": 429}
    assert _snapshots(db) == 2
    out = capsys.readouterr()
    assert "'Cobranzas Ficticias': 1 stored, 0 unchanged, 1 failed" in out.out
    assert "1 reads failed" in out.err


def test_a_transport_error_fails_only_that_tab(db, env, fake):
    fake.failures[("grid", "file-a", "Cobros")] = [httplib2.decode.DecodeLimitError(MARKER)]
    assert _import(env) == 1
    assert fake.waits == []
    assert [e for _, _, e in _events(db, "tab_failed")] == [{"error": "DecodeLimitError"}]
    assert _snapshots(db) == 2


@pytest.mark.parametrize("drive", [{"version": "7"}, {"modifiedTime": "2026-10-18T12:00:00Z"}])
def test_a_drive_answer_without_version_fails_only_that_tab(db, env, fake, drive):
    fake.files_by_id["file-p"]["drive"] = drive
    assert _import(env) == 1
    assert [e for _, _, e in _events(db, "tab_failed")] == [{"error": "KeyError"}]
    assert _snapshots(db) == 2


def test_a_client_error_is_not_retried(db, env, fake):
    fake.failures[("version", "file-p", None)] = [403]
    assert _import(env) == 1
    assert fake.waits == []
    assert [e for _, _, e in _events(db, "tab_failed")] == [{"error": "HttpError", "status": 403}]


def test_a_spreadsheet_google_cannot_open_is_reported_and_the_rest_imported(db, env, fake):
    fake.failures[("tabs", "file-a", None)] = [404]
    assert _import(env) == 1
    assert [e for _, _, e in _events(db, "source_failed")] == [
        {"error": "HttpError", "status": 404}
    ]
    assert _snapshots(db) == 1


def test_content_postgres_cannot_store_fails_only_that_tab(db, env, fake):
    fake.files_by_id["file-a"]["tabs"][1] = _tab(12, "Nueva", "nul\u0000byte")
    assert _import(env) == 1
    assert [e["error"] for _, _, e in _events(db, "tab_failed")] == ["UntranslatableCharacter"]
    assert _snapshots(db) == 2


def test_source_without_drive_id_fails_without_calling_google(db, env, fake):
    env.write_text(SOURCES.replace('    drive_id: "file-p"\n', ""), encoding="utf-8")
    assert _import(env, "--source", "P&L Ficticio") == 1
    assert fake.calls == []
    assert [e for _, _, e in _events(db, "source_failed")] == [{"error": "drive_id missing"}]


def test_unknown_source_is_an_error(env, fake, capsys):
    assert _import(env, "--source", "Nope") == 1
    assert "no source titled 'Nope'" in capsys.readouterr().err


def test_resolve_writes_only_the_missing_ids(db, env, fake, capsys):
    original = SOURCES.replace('    drive_id: "file-a"\n', "").replace(
        '    drive_id: "file-p"\n', ""
    )
    original += '  - title: "No Existe"\n    all_tabs: IGNORAR\n'
    env.write_text(original, encoding="utf-8")
    assert cli.main(["sources", "resolve", "--file", str(env)]) == 1
    captured = capsys.readouterr()
    assert "resolved 2 of 3" in captured.out
    assert "'No Existe': 0 spreadsheets with that exact name" in captured.err
    written = env.read_text(encoding="utf-8")
    assert (
        written.replace('    drive_id: "file-a"\n', "").replace('    drive_id: "file-p"\n', "")
        == original
    )
    assert db.execute("SELECT title, drive_id FROM source ORDER BY title").fetchall() == [
        ("Cobranzas Ficticias", "file-a"),
        ("No Existe", None),
        ("P&L Ficticio", "file-p"),
    ]


def test_resolve_rejects_a_title_with_two_spreadsheets(env, fake, capsys):
    fake.files_by_id["file-b"] = {"name": "P&L Ficticio", "version": "1", "tabs": []}
    env.write_text(SOURCES.replace('    drive_id: "file-p"\n', ""), encoding="utf-8")
    assert cli.main(["sources", "resolve", "--file", str(env)]) == 1
    assert "'P&L Ficticio': 2 spreadsheets" in capsys.readouterr().err
    assert env.read_text(encoding="utf-8") == SOURCES.replace('    drive_id: "file-p"\n', "")


def test_the_app_never_deletes_or_updates_snapshots():
    code = " ".join(p.read_text(encoding="utf-8") for p in APP.rglob("*.py")).lower()
    assert "snapshot" in code
    for statement in ("delete from snapshot", "update snapshot", "truncate"):
        assert statement not in " ".join(code.split())
