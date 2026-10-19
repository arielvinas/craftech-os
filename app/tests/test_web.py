"""The web screens against the test database, with synthetic data only."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from craftech_os.migrate import migrate
from craftech_os.web import app as web

NOW = datetime.now(UTC)
SCRIPT = "<script>alert(1)</script>"


@pytest.fixture
def client(db, monkeypatch):
    migrate(db)
    monkeypatch.setenv("DATABASE_URL", db.info.dsn + " password=" + (db.info.password or ""))
    return TestClient(web.app, raise_server_exceptions=False)


def _seed(db) -> dict:
    """Two sources, a tab each, two snapshots and a few changes, issues and events."""
    ids = {}
    ids["a"] = db.execute(
        "INSERT INTO source (title, drive_id) VALUES ('Planilla Ficticia A', 'file-a') RETURNING id"
    ).fetchone()[0]
    ids["b"] = db.execute(
        "INSERT INTO source (title, drive_id) VALUES ('Planilla Ficticia B', 'file-b') RETURNING id"
    ).fetchone()[0]
    ids["tab_a"] = db.execute(
        "INSERT INTO source_tab (source_id, sheet_id, name, class)"
        " VALUES (%s, 1, 'Cobros', 'CARGA') RETURNING id",
        (ids["a"],),
    ).fetchone()[0]
    ids["tab_b"] = db.execute(
        "INSERT INTO source_tab (source_id, sheet_id, name, class)"
        " VALUES (%s, 2, 'Pagos', 'CARGA') RETURNING id",
        (ids["b"],),
    ).fetchone()[0]
    snaps = [
        db.execute(
            "INSERT INTO snapshot (source_tab_id, drive_version, drive_modified_at,"
            " duration_ms, origin, content_hash, content, row_count, col_count, cell_count)"
            " VALUES (%s, %s, now(), 120, 'lectura', %s, '{}', 1, 1, 1) RETURNING id",
            (tab, n, f"{n:064x}"),
        ).fetchone()[0]
        for tab in (ids["tab_a"], ids["tab_b"])
        for n in (1, 2)
    ]
    ids["script"] = db.execute(
        "INSERT INTO cell_change (source_tab_id, from_snapshot, to_snapshot, change_type,"
        " row_key, cell_ref, old_value, new_value, old_formula, new_formula)"
        " VALUES (%s, %s, %s, 'value', 'CLAVE-1', 'B2', 'viejo', %s, '=A1+1', '=A1+2')"
        " RETURNING id",
        (ids["tab_a"], snaps[0], snaps[1], SCRIPT),
    ).fetchone()[0]
    ids["color"] = db.execute(
        "INSERT INTO cell_change (source_tab_id, from_snapshot, to_snapshot, change_type,"
        " row_key, cell_ref, old_color, new_color, attributed_editor_ids,"
        " attribution_certainty, attributed_at)"
        " VALUES (%s, %s, %s, 'color', 'CLAVE-2', 'C3', '#ff0000', '#00ff00', '{people/111}',"
        " 'cierta', now()) RETURNING id",
        (ids["tab_b"], snaps[2], snaps[3]),
    ).fetchone()[0]
    ids["issue"] = db.execute(
        "INSERT INTO issue (issue_type, stable_key, source_id, source_tab_id, details)"
        " VALUES ('color_desconocido', 'k-1', %s, %s, '{\"color\": \"#123456\"}') RETURNING id",
        (ids["a"], ids["tab_a"]),
    ).fetchone()[0]
    db.execute(
        "INSERT INTO system_event (kind, occurred_at)"
        " VALUES ('worker_tick', %s), ('worker_tick', %s)",
        (NOW - timedelta(minutes=37), NOW - timedelta(minutes=2)),
    )
    return ids


def test_autoescape_is_forced():
    assert web.env.autoescape is True
    assert (
        web.env.from_string("{{ v }}").render(v=SCRIPT) == "&lt;script&gt;alert(1)&lt;/script&gt;"
    )


def test_every_screen_answers_200(db, client):
    ids = _seed(db)
    for path in (
        "/cambios",
        f"/cambios/{ids['script']}",
        "/problemas",
        f"/problemas/{ids['issue']}",
        "/fuentes",
    ):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.headers["content-security-policy"] == "default-src 'self'"
    root = client.get("/", follow_redirects=False)
    assert root.status_code == 303 and root.headers["location"] == "/cambios"


def test_cell_values_are_escaped(db, client):
    ids = _seed(db)
    for path in ("/cambios", f"/cambios/{ids['script']}"):
        html = client.get(path).text
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
        assert "<script" not in html
    detail = client.get(f"/cambios/{ids['script']}").text
    assert "=A1+1" in detail and "=A1+2" in detail


def test_filters_narrow_the_changes(db, client):
    ids = _seed(db)
    everything = client.get("/cambios").text
    assert "CLAVE-1" in everything and "CLAVE-2" in everything
    only_color = client.get(f"/cambios?planilla={ids['b']}&tipo=color").text
    assert "CLAVE-2" in only_color and "CLAVE-1" not in only_color
    assert 'type="color" value="#ff0000"' in only_color and "#00ff00" in only_color
    assert "CLAVE-1" in client.get("/cambios?clave=clave-1").text
    assert "CLAVE-2" not in client.get("/cambios?clave=clave-1").text
    assert "CLAVE-1" not in client.get("/cambios?editor=people/111").text
    assert "CLAVE-2" not in client.get("/cambios?editor=sin_atribuir").text
    tomorrow = (NOW + timedelta(days=2)).date().isoformat()
    assert "CLAVE-1" not in client.get(f"/cambios?desde={tomorrow}").text


def test_attribution_shows_unattributed_then_the_profile_name(db, client):
    _seed(db)
    html = client.get("/cambios").text
    assert "sin atribuir" in html and "people/111" in html
    # editor_profile arrives with T-005; once it exists, its latest name per actor is shown.
    db.execute(
        "CREATE TABLE editor_profile (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,"
        " actor_id text, person_name text, created_at timestamptz DEFAULT now())"
    )
    db.execute(
        "INSERT INTO editor_profile (actor_id, person_name, created_at)"
        " VALUES ('people/111', 'Persona Vieja', now() - interval '1 day'),"
        " ('people/111', 'Persona Ficticia', now())"
    )
    html = client.get("/cambios").text
    assert "Persona Ficticia" in html and "Persona Vieja" not in html


@pytest.mark.parametrize(
    "path",
    [
        "/cambios?tipo=xxx",
        "/cambios?planilla=1;DROP",
        "/cambios?desde=ayer",
        "/cambios?pagina=-1",
        "/problemas?estado=cerrado",
        "/fuentes?resultado=otro",
    ],
)
def test_invalid_filter_is_400_without_the_database(monkeypatch, path):
    def no_database():
        raise AssertionError("the database was reached")

    monkeypatch.setattr(web, "_connect", no_database)
    response = TestClient(web.app, raise_server_exceptions=False).get(path)
    assert response.status_code == 400
    assert "Filtro inválido" in response.text


def test_missing_rows_are_404_without_traceback(db, client):
    _seed(db)
    for path in ("/cambios/999999", "/problemas/999999", "/no-existe"):
        response = client.get(path)
        assert response.status_code == 404
        assert "Traceback" not in response.text and "Error 404" in response.text
    assert client.post("/fuentes/999999/leer-ahora").status_code == 404


def test_server_error_page_has_no_traceback(monkeypatch):
    def broken():
        raise RuntimeError("secret detail")

    monkeypatch.setattr(web, "_connect", broken)
    response = TestClient(web.app, raise_server_exceptions=False).get("/fuentes")
    assert response.status_code == 500
    assert "secret detail" not in response.text and "Traceback" not in response.text


def test_issue_status_follows_its_resolution(db, client):
    ids = _seed(db)
    html = client.get("/problemas?estado=abierto").text
    assert "<code>k-1</code>" in html and ">abierto</td>" in html
    db.execute(
        "INSERT INTO issue_resolution (issue_id, action, author, reason)"
        " VALUES (%s, 'ignorado', 'Revisora Ficticia', 'motivo de prueba')",
        (ids["issue"],),
    )
    assert "<code>k-1</code>" not in client.get("/problemas?estado=abierto").text
    html = client.get("/problemas?estado=ignorado").text
    assert "<code>k-1</code>" in html and ">ignorado</td>" in html
    assert "Revisora Ficticia" in html and "motivo de prueba" in html
    detail = client.get(f"/problemas/{ids['issue']}").text
    assert "Revisora Ficticia" in detail and "#123456" in detail


def test_read_now_twice_leaves_one_pending_request(db, client):
    ids = _seed(db)
    first = client.post(f"/fuentes/{ids['a']}/leer-ahora", follow_redirects=False)
    assert first.status_code == 303
    assert first.headers["location"] == f"/fuentes?resultado=created#fuente-{ids['a']}"
    assert "Pedido de lectura creado" in client.get(first.headers["location"]).text
    second = client.post(f"/fuentes/{ids['a']}/leer-ahora")
    assert "Ya había un pedido pendiente" in second.text
    (pending,) = db.execute(
        "SELECT count(*) FROM read_request WHERE source_id = %s AND served_at IS NULL", (ids["a"],)
    ).fetchone()
    assert pending == 1


def test_fuentes_warns_when_the_dump_is_missing_or_old(db, client):
    ids = _seed(db)
    html = client.get("/fuentes").text
    assert "Planilla Ficticia A" in html and "Cobros" in html and "CARGA" in html
    assert "0:35:00" in html  # the 35 minutes between the two seeded ticks
    assert "no hay un dump de las últimas 48 horas" in html
    db.execute(
        "INSERT INTO system_event (kind, occurred_at, details)"
        " VALUES ('dump', now() - interval '3 days', '{\"size_bytes\": 10}')"
    )
    assert "no hay un dump de las últimas 48 horas" in client.get("/fuentes").text
    db.execute("INSERT INTO system_event (kind, details) VALUES ('dump', '{\"size_bytes\": 2048}')")
    html = client.get("/fuentes").text
    assert "no hay un dump de las últimas 48 horas" not in html and "2,048 bytes" in html
    assert f'id="fuente-{ids["b"]}"' in html
