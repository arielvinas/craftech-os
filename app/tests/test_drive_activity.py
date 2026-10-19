"""Drive Activity import, editors and attribution against the test database. No network."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import psycopg
import pytest
from test_import import MARKER, FakeGoogle, _events, _tab
from test_worker import EDITED_AT, Clock, _edit

from craftech_os import attribution, cli, worker
from craftech_os.ingest import drive_activity
from craftech_os.ingest.google import Google
from craftech_os.migrate import migrate

SOURCES = """
sources:
  - title: "Cobranzas Ficticias"
    drive_id: "file-a"
    tabs:
      CARGA: ["Cobros"]
  - title: "P&L Ficticio"
    drive_id: "file-p"
    all_tabs: DERIVADA
"""
T0 = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
CELL_CHANGE_COLUMNS = [
    "id", "source_tab_id", "from_snapshot", "to_snapshot", "change_type", "block", "row_key",
    "row_ordinal", "cell_ref", "old_value", "new_value", "old_formula", "new_formula",
    "old_color", "new_color", "detected_at", "window_start", "window_end",
    "attributed_editor_ids", "attribution_certainty", "attributed_at",
]  # fmt: skip


def _activity(at, actor="people/101", action="edit"):
    user = (
        {"deletedUser": {}}
        if actor == "deletedUser"
        else {"knownUser": {"personName": actor, "isCurrentUser": False}}
    )
    return {
        "primaryActionDetail": {action: {}},
        "actors": [{"user": user}],
        "targets": [{"driveItem": {"name": "items/file-a", "title": MARKER}}],
        "actions": [{"detail": {action: {}}}],
        "timestamp": at.isoformat().replace("+00:00", "Z"),
    }


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
    assert cli.main(["sources", "load", "--file", str(path)]) == 0
    return path


def _source_id(db, title="Cobranzas Ficticias"):
    return db.execute("SELECT id FROM source WHERE title = %s", (title,)).fetchone()[0]


def _change(db, start, end, change_type="value", title="Cobranzas Ficticias"):
    """A cell_change in the first tab of the source, with the window (start, end]."""
    source_id = _source_id(db, title)
    (tab_id,) = db.execute(
        "INSERT INTO source_tab (source_id, sheet_id, name, class)"
        " SELECT %s, 900 + count(*), 'Tab Ficticia ' || count(*), 'CARGA' FROM source_tab"
        " RETURNING id",
        (source_id,),
    ).fetchone()
    snaps = [
        db.execute(
            "INSERT INTO snapshot (source_tab_id, drive_version, drive_modified_at,"
            " duration_ms, origin, content_hash, content, row_count, col_count, cell_count)"
            " VALUES (%s, %s, %s, 1, 'lectura', %s, '{}', 1, 1, 1) RETURNING id",
            (tab_id, n, at, f"{tab_id:032x}{n:032x}"),
        ).fetchone()[0]
        for n, at in ((1, start), (2, end))
    ]
    if change_type.startswith("tab_"):
        return db.execute(
            "INSERT INTO cell_change (source_tab_id, change_type, new_value)"
            " VALUES (%s, %s, 'x') RETURNING id",
            (tab_id, change_type),
        ).fetchone()[0]
    return db.execute(
        "INSERT INTO cell_change (source_tab_id, from_snapshot, to_snapshot, change_type,"
        " cell_ref, window_start, window_end) VALUES (%s, %s, %s, %s, 'B2', %s, %s) RETURNING id",
        (tab_id, snaps[0], snaps[1], change_type, start, end),
    ).fetchone()[0]


def _attribution(db, change_id):
    return db.execute(
        "SELECT attributed_editor_ids, attribution_certainty, attributed_at"
        " FROM cell_change WHERE id = %s",
        (change_id,),
    ).fetchone()


def _store(db, fake, activities, file_id="file-a", title="Cobranzas Ficticias"):
    fake.activities[file_id] = activities
    return drive_activity.fetch(db, fake.google(), _source_id(db, title), file_id, lambda: T0)


def _activity_rows(db):
    return db.execute(
        "SELECT actor_id, action_type, activity_at FROM drive_activity ORDER BY activity_at, id"
    ).fetchall()


# --- import ---


def test_drive_import_reads_every_page_and_a_rerun_adds_nothing(db, env, fake, capsys):
    fake.activities["file-a"] = [_activity(T0 - timedelta(minutes=m)) for m in range(5)]
    assert cli.main(["drive", "import"]) == 0
    assert [k for k in fake.calls if k[0] == "activity"] == [
        ("activity", "file-a", None),
        ("activity", "file-a", "2"),
        ("activity", "file-a", "4"),
        ("activity", "file-p", None),
    ]
    assert len(_activity_rows(db)) == 5
    assert cli.main(["drive", "import"]) == 0
    assert len(_activity_rows(db)) == 5
    reads = [e for _, _, e in _events(db, "activity_read")]
    assert [e["inserted"] for e in reads] == [5, 0, 0, 0]
    out = capsys.readouterr().out
    assert "'Cobranzas Ficticias': 5 new activities" in out


def test_drive_import_of_one_source(db, env, fake):
    fake.activities["file-a"] = [_activity(T0)]
    fake.activities["file-p"] = [_activity(T0)]
    assert cli.main(["drive", "import", "--source", "P&L Ficticio"]) == 0
    assert [k[1] for k in fake.calls if k[0] == "activity"] == ["file-p"]
    assert cli.main(["drive", "import", "--source", "Nope"]) == 1


def test_parse_keeps_the_actor_id_and_the_action(db, env, fake):
    _store(
        db,
        fake,
        [
            _activity(T0, "deletedUser"),
            _activity(T0 - timedelta(minutes=1), "people/202", "permissionChange"),
            _activity(T0 - timedelta(minutes=2), "people/101", "edit"),
        ],
    )
    assert _activity_rows(db) == [
        ("people/101", "edit", T0 - timedelta(minutes=2)),
        ("people/202", "permissionChange", T0 - timedelta(minutes=1)),
        ("deletedUser", "edit", T0),
    ]
    assert (
        db.execute("SELECT raw->'targets'->0->'driveItem'->>'name' FROM drive_activity").fetchall()
        == [("items/file-a",)] * 3
    )


def test_a_later_fetch_starts_ten_minutes_before_the_latest_known_activity(db, env, fake):
    _store(db, fake, [_activity(T0)])
    later = [
        _activity(T0 + timedelta(minutes=30), "people/303"),
        _activity(T0 - timedelta(minutes=9), "people/404"),  # published late: still read
        _activity(T0 - timedelta(minutes=11), "people/505"),  # before the overlap: not asked for
        _activity(T0),
    ]
    _store(db, fake, later)
    assert [r[0] for r in _activity_rows(db)] == ["people/404", "people/101", "people/303"]


def test_an_interrupted_import_stores_nothing_and_the_next_one_reads_it_all(db, env, fake):
    fake.failures[("activity", "file-a", "2")] = [404]
    activities = [_activity(T0 - timedelta(minutes=m)) for m in range(5)]
    assert _store(db, fake, activities) is None
    (failed,) = [e for _, _, e in _events(db, "activity_failed")]
    assert failed == {"error": "HttpError", "status": 404}
    assert _activity_rows(db) == []
    assert _store(db, fake, activities)["inserted"] == 5
    assert len(_activity_rows(db)) == 5


def test_activity_retries_on_quota_errors_and_records_them(db, env, fake):
    fake.failures[("activity", "file-a", None)] = [429]
    assert _store(db, fake, [_activity(T0)])["inserted"] == 1
    (retry,) = [e for _, _, e in _events(db, "api_retry")]
    assert retry["call"] == "driveactivity.query" and retry["status"] == 429


def test_no_event_or_output_contains_names_or_titles_from_google(db, env, fake, capsys):
    fake.activities["file-a"] = [_activity(T0, "people/101")]
    _change(db, T0 - timedelta(minutes=5), T0 - timedelta(minutes=1))
    assert cli.main(["drive", "import"]) == 0
    assert cli.main(["editors"]) == 0
    captured = capsys.readouterr()
    assert MARKER not in captured.out + captured.err
    leaked = db.execute(
        "SELECT count(*) FROM system_event WHERE details::text LIKE %s", (f"%{MARKER}%",)
    ).fetchone()
    assert leaked == (0,)


# --- attribution ---


def _attribute(db, through):
    return attribution.attribute(db, _source_id(db), through)


def test_one_editor_in_the_window_is_cierta_at_their_last_edit(db, env, fake):
    change = _change(db, T0, T0 + timedelta(minutes=10))
    _store(
        db,
        fake,
        [
            _activity(T0 + timedelta(minutes=14), "people/101"),  # within the 5 minute margin
            _activity(T0 + timedelta(minutes=4), "people/101"),
            _activity(T0 + timedelta(minutes=3), "people/202", "permissionChange"),
            _activity(T0, "people/303"),  # at window_start: the previous version had it
            _activity(T0 + timedelta(minutes=16), "people/404"),  # after the margin
        ],
    )
    assert _attribute(db, T0 + timedelta(minutes=20)) == {"cierta": 1}
    assert _attribution(db, change) == (["people/101"], "cierta", T0 + timedelta(minutes=14))


def test_two_editors_are_una_de_and_none_is_sin_datos(db, env, fake):
    two = _change(db, T0, T0 + timedelta(minutes=10))
    none = _change(db, T0 + timedelta(hours=2), T0 + timedelta(hours=3))
    _store(
        db,
        fake,
        [_activity(T0 + timedelta(minutes=2), "people/202"), _activity(T0 + timedelta(minutes=1))],
    )
    assert _attribute(db, T0 + timedelta(hours=4)) == {"una_de": 1, "sin_datos": 1}
    assert _attribution(db, two) == (["people/101", "people/202"], "una_de", None)
    assert _attribution(db, none) == ([], "sin_datos", None)


def test_a_deleted_user_alone_is_cierta(db, env, fake):
    change = _change(db, T0, T0 + timedelta(minutes=10))
    _store(db, fake, [_activity(T0 + timedelta(minutes=5), "deletedUser")])
    _attribute(db, T0 + timedelta(hours=1))
    assert _attribution(db, change) == (["deletedUser"], "cierta", T0 + timedelta(minutes=5))


def test_a_change_waits_until_activity_after_its_margin_was_read(db, env, fake):
    change = _change(db, T0, T0 + timedelta(minutes=10))
    tab_change = _change(db, T0, T0, "tab_added")
    _store(db, fake, [_activity(T0 + timedelta(minutes=2))])
    assert _attribute(db, T0 + timedelta(minutes=15)) == {}
    assert _attribution(db, change) == (None, None, None)
    assert _attribute(db, T0 + timedelta(minutes=15, seconds=1)) == {"cierta": 1}
    # Already attributed: not touched again. Tab changes have no window and stay unprocessed.
    _store(db, fake, [_activity(T0 + timedelta(minutes=3), "people/202")])
    assert _attribute(db, T0 + timedelta(hours=1)) == {}
    assert _attribution(db, change)[1] == "cierta"
    assert _attribution(db, tab_change) == (None, None, None)


def test_attribution_only_looks_at_the_changes_source(db, env, fake):
    other = _change(db, T0, T0 + timedelta(minutes=10), title="P&L Ficticio")
    _store(db, fake, [_activity(T0 + timedelta(minutes=2))])
    _attribute(db, T0 + timedelta(hours=1))
    assert _attribution(db, other) == (None, None, None)
    attribution.attribute(db, _source_id(db, "P&L Ficticio"), T0 + timedelta(hours=1))
    assert _attribution(db, other) == ([], "sin_datos", None)


def test_drive_import_attributes_pending_changes_at_the_end(db, env, fake, capsys):
    change = _change(db, T0, T0 + timedelta(minutes=10))
    fake.activities["file-a"] = [_activity(T0 + timedelta(minutes=2))]
    assert cli.main(["drive", "import"]) == 0
    assert _attribution(db, change)[1] == "cierta"
    assert "1 changes attributed: cierta 1" in capsys.readouterr().out


def test_cell_change_columns_are_unchanged(db, env):
    columns = db.execute(
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_name = 'cell_change' ORDER BY ordinal_position"
    ).fetchall()
    assert [c for (c,) in columns] == CELL_CHANGE_COLUMNS


# --- editors ---


def _editors(db):
    return db.execute("SELECT actor_id, number, label FROM v_editor ORDER BY actor_id").fetchall()


def test_every_actor_is_numbered_by_first_appearance_and_stays_numbered(db, env, fake):
    _store(
        db,
        fake,
        [
            _activity(T0, "deletedUser"),
            _activity(T0 - timedelta(minutes=1), "people/202", "permissionChange"),
            _activity(T0 - timedelta(minutes=2), "people/303"),
        ],
    )
    first = _editors(db)
    assert first == [
        ("deletedUser", None, "usuario eliminado"),
        ("people/202", 2, "editor sin identificar #2"),
        ("people/303", 1, "editor sin identificar #1"),
    ]
    assert _editors(db) == first
    # A later backfill brings an older activity of a new actor: the numbers already given stay.
    _store(db, fake, [_activity(T0 - timedelta(days=300), "people/909")], "file-p", "P&L Ficticio")
    assert _editors(db) == [*first, ("people/909", 3, "editor sin identificar #3")]


def test_the_latest_editor_profile_wins(db, env, fake):
    _store(db, fake, [_activity(T0, "people/101")])
    db.execute(
        "INSERT INTO editor_profile (actor_id, person_name, author, reason, created_at) VALUES"
        " ('people/101', 'Persona Vieja', 'ariel', 'prueba', now() - interval '1 day'),"
        " ('people/101', 'Persona Ficticia', 'ariel', 'prueba', now())"
    )
    assert db.execute("SELECT number, person_name, label FROM v_editor").fetchall() == [
        (1, "Persona Ficticia", "Persona Ficticia")
    ]


def test_annotation_accepts_only_the_four_entity_types(db, env):
    for entity_type in ("source", "source_tab", "cell_change", "issue"):
        db.execute(
            "INSERT INTO annotation (entity_type, entity_key, body, author, reason)"
            " VALUES (%s, '1', 'nota', 'ariel', 'prueba')",
            (entity_type,),
        )
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(
            "INSERT INTO annotation (entity_type, entity_key, body, author, reason)"
            " VALUES ('snapshot', '1', 'nota', 'ariel', 'prueba')"
        )


def test_attribution_stats_per_source_and_day(db, env, fake):
    for n in range(3):
        _change(db, T0 + timedelta(hours=n), T0 + timedelta(hours=n, minutes=10))
    _change(db, T0, T0, "tab_added")
    _store(db, fake, [_activity(T0 + timedelta(minutes=2))])
    _attribute(db, T0 + timedelta(hours=1, minutes=30))
    rows = db.execute(
        "SELECT source_id, total, cierta, una_de, sin_datos, pendientes, pct_cierta"
        " FROM v_attribution_stats"
    ).fetchall()
    assert [r[1:] for r in rows] == [(3, 1, 0, 1, 1, Decimal("33.3"))]
    assert rows[0][0] == _source_id(db)


def test_editors_lists_each_actor_with_edits_sheets_and_hours(db, env, fake, capsys):
    _store(
        db,
        fake,
        [
            _activity(T0 + timedelta(hours=3)),
            _activity(T0 + timedelta(minutes=1), "people/202", "rename"),
            _activity(T0),
        ],
    )
    _store(db, fake, [_activity(T0 + timedelta(days=1))], "file-p", "P&L Ficticio")
    assert cli.main(["editors"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "editor sin identificar #1  people/101  3 edits  'Cobranzas Ficticias', 'P&L Ficticio'"
        "  10-13 h UTC  2026-01-05..2026-01-06",
        "editor sin identificar #2  people/202  0 edits  'Cobranzas Ficticias'"
        "  10-10 h UTC  2026-01-05..2026-01-05",
        "2 editors",
    ]


# --- worker ---


def _activity_calls(fake):
    return [k[1] for k in fake.calls if k[0] == "activity"]


def test_the_worker_fetches_activity_and_attributes_once_the_margin_passed(db, env, fake):
    clock = Clock(EDITED_AT + timedelta(minutes=30))

    def tick():
        return worker.tick(db, fake.google(), clock.now, clock.sleep)

    tick()
    assert _activity_calls(fake) == ["file-a", "file-p"]
    fake.calls.clear()
    edited = clock.now() - timedelta(minutes=3)
    _edit(fake, "file-a", "42", edited)
    fake.files_by_id["file-a"]["tabs"][0] = _tab(11, "Cobros", "otro valor ficticio")
    fake.activities["file-a"] = [_activity(edited + timedelta(minutes=2))]
    tick()
    # Read now: its activity is fetched, but the margin after the edit has not passed yet.
    assert _activity_calls(fake) == ["file-a"]
    pending = db.execute(
        "SELECT count(*) FROM cell_change WHERE window_end IS NOT NULL"
        " AND attribution_certainty IS NULL"
    ).fetchone()[0]
    assert pending > 0
    fake.calls.clear()
    clock.at += timedelta(minutes=5)
    tick()
    assert _activity_calls(fake) == ["file-a"]
    assert db.execute(
        "SELECT DISTINCT attributed_editor_ids, attribution_certainty, attributed_at"
        " FROM cell_change WHERE window_end IS NOT NULL"
    ).fetchall() == [(["people/101"], "cierta", edited + timedelta(minutes=2))]
    fake.calls.clear()
    clock.at += timedelta(minutes=5)
    tick()
    assert _activity_calls(fake) == []
    # Every source is fetched at least once an hour.
    clock.at += timedelta(hours=1)
    tick()
    assert _activity_calls(fake) == ["file-a", "file-p"]


def test_a_failed_activity_fetch_does_not_stop_the_tick(db, env, fake):
    clock = Clock(EDITED_AT + timedelta(minutes=30))
    fake.failures[("activity", "file-a", None)] = [403]
    counts = worker.tick(db, fake.google(), clock.now, clock.sleep)
    assert counts["read"] == 2
    assert _activity_calls(fake) == ["file-a", "file-p"]
    assert [e["status"] for _, _, e in _events(db, "activity_failed")] == [403]
    assert len(_events(db, "activity_read")) == 1
