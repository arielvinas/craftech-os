"""The worker against the test database, with Google and the clock faked in memory. No network."""

import os
import subprocess
from datetime import UTC, datetime, timedelta

import pytest
from test_import import MARKER, FakeGoogle, _events, _snapshots, _tab

from craftech_os import cli, worker
from craftech_os.ingest.google import MAX_RETRIES
from craftech_os.migrate import migrate

SOURCES = """
sources:
  - title: "Cobranzas Ficticias"
    drive_id: "file-a"
    tabs:
      CARGA: ["Cobros"]
      HISTORICA: ["Nueva"]
  - title: "P&L Ficticio"
    drive_id: "file-p"
    all_tabs: DERIVADA
  - title: "Sin Id"
    all_tabs: CARGA
"""
EDITED_AT = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


class Clock:
    """now() and sleep() for the worker; sleeping moves now() forward and calls on_sleep."""

    def __init__(self, at):
        self.at, self.sleeps, self.on_sleep = at, [], lambda: None

    def now(self):
        return self.at

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.at += timedelta(seconds=seconds)
        self.on_sleep()


@pytest.fixture
def fake():
    return FakeGoogle()


@pytest.fixture
def clock():
    return Clock(EDITED_AT + timedelta(minutes=30))


@pytest.fixture
def env(db, monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", db.info.dsn + " password=" + (db.info.password or ""))
    migrate(db)
    path = tmp_path / "sources.yaml"
    path.write_text(SOURCES, encoding="utf-8")
    assert cli.main(["sources", "load", "--file", str(path)]) == 0
    return path


def _edit(fake, file_id, version, at):
    fake.files_by_id[file_id]["drive"] = {
        "version": version,
        "modifiedTime": at.isoformat().replace("+00:00", "Z"),
    }


def _tick(db, fake, clock):
    return worker.tick(db, fake.google(), clock.now, clock.sleep)


def _grids(fake):
    return [key[1:] for key in fake.calls if key[0] == "grid"]


def _details(db, kind):
    return [e for _, _, e in _events(db, kind)]


def test_first_tick_reads_only_carga_and_derivada_tabs(db, env, fake, clock):
    assert _tick(db, fake, clock) == {"checked": 2, "read": 2, "stored": 2}
    assert _grids(fake) == [("file-a", "Cobros"), ("file-p", "Resumen")]
    assert _snapshots(db) == 2
    assert _details(db, "version_changed") == [
        {"old": None, "new": "41"},
        {"old": None, "new": "7"},
    ]
    # The spreadsheets were edited 30 minutes ago: nothing to wait for.
    assert _details(db, "calm_wait") == [{"waited_s": 0, "capped": False}] * 2
    assert clock.sleeps == []
    (tick,) = _events(db, "worker_tick")
    assert tick[1] is not None and tick[2] == {"checked": 2, "read": 2, "stored": 2}


def test_an_unchanged_version_is_not_read_again(db, env, fake, clock):
    _tick(db, fake, clock)
    fake.calls.clear()
    assert _tick(db, fake, clock) == {"checked": 2, "read": 0, "stored": 0}
    assert _grids(fake) == []
    assert len(_events(db, "version_changed")) == 2


def test_a_new_version_waits_for_two_quiet_minutes_and_stores_only_changed_tabs(
    db, env, fake, clock
):
    _tick(db, fake, clock)
    fake.calls.clear()
    _edit(fake, "file-p", "8", clock.now())
    fake.files_by_id["file-p"]["tabs"][0]["merges"] = []
    assert _tick(db, fake, clock) == {"checked": 2, "read": 1, "stored": 1}
    assert clock.sleeps == [30, 30, 30, 30]
    assert _details(db, "calm_wait")[-1] == {"waited_s": 120, "capped": False}
    assert _details(db, "version_changed")[-1] == {"old": "7", "new": "8"}
    assert _grids(fake) == [("file-p", "Resumen")]
    assert _snapshots(db) == 3


def test_an_edit_during_the_wait_restarts_the_quiet_window(db, env, fake, clock):
    _tick(db, fake, clock)
    _edit(fake, "file-a", "42", clock.now())
    edits = [clock.now() + timedelta(seconds=60)]

    def edit_once():
        if edits and clock.now() >= edits[0]:
            _edit(fake, "file-a", "43", edits.pop())

    clock.on_sleep = edit_once
    _tick(db, fake, clock)
    assert _details(db, "calm_wait")[-1] == {"waited_s": 180, "capped": False}


def test_the_wait_is_capped_at_ten_minutes_and_reads_anyway(db, env, fake, clock):
    _tick(db, fake, clock)
    fake.calls.clear()
    _edit(fake, "file-a", "42", clock.now())
    clock.on_sleep = lambda: _edit(fake, "file-a", "42", clock.now())
    assert _tick(db, fake, clock)["read"] == 1
    assert sum(clock.sleeps) == 600
    assert _details(db, "calm_wait")[-1] == {"waited_s": 600, "capped": True}
    assert _grids(fake) == [("file-a", "Cobros")]


def test_a_quota_error_on_the_version_check_is_retried_and_the_tick_ends(db, env, fake, clock):
    fake.failures[("version", "file-a", None)] = [429]
    assert _tick(db, fake, clock)["read"] == 2
    assert _details(db, "api_retry") == [
        {"call": "drive.files.get", "status": 429, "attempt": 1, "wait_s": 1}
    ]


def test_a_source_that_keeps_failing_does_not_stop_the_others(db, env, fake, clock):
    fake.failures[("version", "file-a", None)] = [429] * (MAX_RETRIES + 1)
    assert _tick(db, fake, clock) == {"checked": 2, "read": 1, "stored": 1}
    assert _details(db, "source_failed") == [{"error": "HttpError", "status": 429}]
    assert len(_events(db, "worker_tick")) == 1
    # Next tick: Google answers again and the source is read.
    assert _tick(db, fake, clock) == {"checked": 2, "read": 1, "stored": 1}


def test_a_source_with_a_failed_tab_is_read_again_next_tick(db, env, fake, clock):
    fake.failures[("grid", "file-a", "Cobros")] = [403]
    assert _tick(db, fake, clock)["read"] == 2
    fake.calls.clear()
    assert _tick(db, fake, clock) == {"checked": 2, "read": 1, "stored": 1}
    assert _grids(fake) == [("file-a", "Cobros")]


def test_a_tick_killed_mid_read_leaves_no_partial_or_duplicated_snapshots(db, env, fake, clock):
    fake.failures[("grid", "file-p", "Resumen")] = [RuntimeError("killed")]
    with pytest.raises(RuntimeError):
        _tick(db, fake, clock)
    assert _snapshots(db) == 1
    # Restarted: the interrupted source is read again; the finished one is not.
    fake.calls.clear()
    assert _tick(db, fake, clock) == {"checked": 2, "read": 1, "stored": 1}
    assert _grids(fake) == [("file-p", "Resumen")]
    duplicated = db.execute(
        "SELECT count(*) FROM (SELECT source_tab_id, content_hash FROM snapshot"
        " GROUP BY 1, 2 HAVING count(*) > 1) d"
    ).fetchone()
    assert duplicated == (0,)


def test_read_now_is_idempotent_and_served_without_waiting(db, env, fake, clock, capsys):
    _tick(db, fake, clock)
    assert cli.main(["read-now", "P&L Ficticio"]) == 0
    assert cli.main(["read-now", "P&L Ficticio"]) == 0
    out = capsys.readouterr().out
    assert "read requested" in out and "already pending" in out
    pending = "SELECT count(*) FROM read_request WHERE served_at IS NULL"
    assert db.execute(pending).fetchone() == (1,)
    # Same version, just edited: a request reads it anyway, without the calm wait.
    _edit(fake, "file-p", "7", clock.now())
    fake.files_by_id["file-p"]["tabs"][0]["merges"] = []
    fake.calls.clear()
    assert _tick(db, fake, clock) == {"checked": 2, "read": 1, "stored": 1}
    assert clock.sleeps == []
    assert _grids(fake) == [("file-p", "Resumen")]
    assert db.execute(pending).fetchone() == (0,)
    served = db.execute(
        "SELECT requested_by, served_at > requested_at, snapshot_count FROM read_request"
    ).fetchall()
    assert served == [("cli", True, 1)]
    assert cli.main(["read-now", "P&L Ficticio"]) == 0
    assert db.execute(pending).fetchone() == (1,)


def test_read_now_rejects_unknown_sources_and_sources_without_drive_id(db, env, capsys):
    assert cli.main(["read-now", "Nope"]) == 1
    assert cli.main(["read-now", "Sin Id"]) == 1
    err = capsys.readouterr().err
    assert "no source titled 'Nope'" in err and "'Sin Id' has no drive_id" in err
    assert db.execute("SELECT count(*) FROM read_request").fetchone() == (0,)


def test_a_request_for_a_source_google_cannot_answer_stays_pending(db, env, fake, clock):
    assert cli.main(["read-now", "P&L Ficticio"]) == 0
    fake.failures[("version", "file-p", None)] = [404]
    _tick(db, fake, clock)
    assert db.execute("SELECT served_at FROM read_request").fetchone() == (None,)
    del fake.failures[("version", "file-p", None)]
    fake.failures[("tabs", "file-p", None)] = [404]
    _tick(db, fake, clock)
    assert db.execute("SELECT served_at FROM read_request").fetchone() == (None,)
    # Once read, the request is served.
    _tick(db, fake, clock)
    assert db.execute("SELECT snapshot_count FROM read_request").fetchone() == (1,)


def _pg_dump(calls, fail=False):
    def run(cmd, **kwargs):
        calls.append((cmd, kwargs["env"]))
        if fail:
            raise subprocess.CalledProcessError(1, cmd[0], stderr="pg_dump: error: no space")
        path = cmd[cmd.index("--file") + 1]
        with open(path, "wb") as f:
            f.write(b"PGDMP" + b"0" * 95)
        return subprocess.CompletedProcess(cmd, 0)

    return run


def _dumps(directory):
    return sorted(p.name for p in directory.iterdir())


def test_dump_keeps_the_last_fourteen(db, env, tmp_path, monkeypatch, clock):
    backups = tmp_path / "backups"
    backups.mkdir()
    for day in range(1, 16):
        (backups / f"craftech-os-2026-09-{day:02}.dump").write_bytes(b"old")
    (backups / "notes.txt").write_text("not a dump")
    calls = []
    monkeypatch.setattr(subprocess, "run", _pg_dump(calls))
    path = worker.dump(db, "postgresql://u:secret@h/d", backups, clock.now)
    assert path == backups / "craftech-os-2026-10-18.dump"
    cmd, child_env = calls[0]
    assert cmd[:2] == ["pg_dump", "--format=custom"]
    assert "secret" not in " ".join(cmd) and child_env["PGPASSWORD"] == "secret"
    names = _dumps(backups)
    assert len(names) == 15 and "notes.txt" in names
    assert names[0] == "craftech-os-2026-09-03.dump" and names[-2] == path.name
    (event,) = _events(db, "dump")
    assert event[1] is not None and event[2] == {"file": path.name, "size_bytes": 100}


def test_a_failed_dump_is_recorded_and_leaves_no_file(db, env, tmp_path, monkeypatch, clock):
    backups = tmp_path / "backups"
    backups.mkdir()
    monkeypatch.setattr(subprocess, "run", _pg_dump([], fail=True))
    # DumpFailed, not CalledProcessError: its message would carry the URL with the password.
    with pytest.raises(worker.DumpFailed):
        worker.dump(db, "postgresql://u@h/d", backups, clock.now)
    assert _details(db, "dump_failed") == [{"error": "pg_dump: error: no space"}]
    assert list(backups.iterdir()) == []


@pytest.mark.parametrize(
    ("last", "now", "due"),
    [
        (None, "2026-10-18T01:00", True),
        ("2026-10-17T03:05", "2026-10-18T02:59", False),
        ("2026-10-17T03:05", "2026-10-18T03:00", True),
        ("2026-10-18T03:05", "2026-10-18T23:00", False),
        ("2026-10-16T22:00", "2026-10-17T02:00", False),
        ("2026-10-16T01:00", "2026-10-17T02:00", True),
    ],
)
def test_dump_is_due_after_three_or_after_a_day_without_one(tmp_path, last, now, due):
    if last:
        path = tmp_path / f"craftech-os-{last[:10]}.dump"
        path.write_bytes(b"x")
        stamp = datetime.fromisoformat(last).astimezone().timestamp()
        os.utime(path, (stamp, stamp))
    assert worker.dump_due(tmp_path, datetime.fromisoformat(now).astimezone()) is due


class Stop(Exception):
    pass


def test_the_worker_ticks_every_five_minutes_and_dumps_once_a_day(
    db, env, fake, clock, tmp_path, monkeypatch, capsys
):
    calls = []
    monkeypatch.setattr(subprocess, "run", _pg_dump(calls))
    _edit(fake, "file-a", "41", clock.now() - timedelta(seconds=60))

    def stop_after_three_ticks():
        if len(_events(db, "worker_tick")) == 3:
            raise Stop

    clock.on_sleep = stop_after_three_ticks
    with pytest.raises(Stop):
        worker.run(db, fake.google(), "postgresql://u@h/d", tmp_path, clock.now, clock.sleep)
    # The first tick waited 60 s for file-a to be quiet; every tick starts 300 s after the last.
    assert clock.sleeps == [30, 30, 240, 300, 300]
    assert len(calls) == 1 and len(_events(db, "dump")) == 1
    out = capsys.readouterr().out
    assert out.count("tick:") == 3 and MARKER not in out
    assert "tick: checked 2, read 2, stored 2" in out


def test_a_failed_dump_does_not_stop_the_worker(db, env, fake, clock, tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", _pg_dump([], fail=True))

    def stop():
        raise Stop

    clock.on_sleep = stop
    with pytest.raises(Stop):
        worker.run(db, fake.google(), "postgresql://u@h/d", tmp_path, clock.now, clock.sleep)
    assert len(_events(db, "dump_failed")) == 1 and len(_events(db, "worker_tick")) == 1


def test_no_worker_event_or_output_contains_cell_values(db, env, fake, clock, capsys):
    fake.files_by_id["file-p"]["tabs"][0] = _tab(21, "Resumen", MARKER)
    _tick(db, fake, clock)
    assert cli.main(["read-now", "P&L Ficticio"]) == 0
    _tick(db, fake, clock)
    captured = capsys.readouterr()
    assert MARKER not in captured.out + captured.err
    leaked = db.execute(
        "SELECT count(*) FROM system_event WHERE details::text LIKE %s", (f"%{MARKER}%",)
    ).fetchone()
    assert leaked == (0,)
