"""The web screens against the test database, with synthetic data only."""

import json
import logging
import re
from datetime import UTC, date, datetime, timedelta

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
    return TestClient(web.app, base_url="http://127.0.0.1", raise_server_exceptions=False)


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
        (NOW - timedelta(minutes=37, milliseconds=250), NOW - timedelta(minutes=2)),
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
    assert root.status_code == 200 and "Ingresos de" in root.text
    assert '<a href="/">Inicio</a>' in root.text


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
    # Once an editor is associated with a person, the latest name per actor is shown.
    db.execute(
        "INSERT INTO editor_profile (actor_id, person_name, author, reason, created_at)"
        " VALUES ('people/111', 'Persona Vieja', 'ariel', 'prueba', now() - interval '1 day'),"
        " ('people/111', 'Persona Ficticia', 'ariel', 'prueba', now())"
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
    response = TestClient(web.app, base_url="http://127.0.0.1", raise_server_exceptions=False).get(
        path
    )
    assert response.status_code == 400
    assert "Filtro inválido" in response.text


def test_foreign_host_is_refused_without_the_database(monkeypatch):
    def no_database():
        raise AssertionError("the database was reached")

    monkeypatch.setattr(web, "_connect", no_database)
    rebound = TestClient(web.app, base_url="http://attacker.example", raise_server_exceptions=False)
    assert rebound.get("/cambios").status_code == 400
    assert rebound.post("/fuentes/1/leer-ahora").status_code == 400
    local = TestClient(web.app, base_url="http://localhost:8000", raise_server_exceptions=False)
    assert local.get("/static/style.css").status_code == 200


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
    response = TestClient(web.app, base_url="http://127.0.0.1", raise_server_exceptions=False).get(
        "/fuentes"
    )
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
    assert "<td>0:35:00</td>" in html  # the 35 minutes between the two seeded ticks
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


def _latest_snapshot(db, tab_id: int) -> int:
    return db.execute(
        "SELECT max(id) FROM snapshot WHERE source_tab_id = %s", (tab_id,)
    ).fetchone()[0]


def _seed_ingresos(db) -> dict:
    """On top of _seed: two clients, invoices of two months, a payment, totals, two fundings
    that are the same one on both sides, and rows without a client."""
    ids = _seed(db)
    pagos = ids["tab_b"]
    ids["tracker"] = db.execute(
        "INSERT INTO source_tab (source_id, sheet_id, name, class)"
        " VALUES (%s, 3, 'FUNDINGS', 'CARGA') RETURNING id",
        (ids["a"],),
    ).fetchone()[0]
    db.execute(
        "INSERT INTO snapshot (source_tab_id, drive_version, drive_modified_at,"
        " duration_ms, origin, content_hash, content, row_count, col_count, cell_count)"
        " VALUES (%s, 3, now(), 120, 'lectura', %s, '{}', 1, 1, 1)",
        (ids["tracker"], f"{3:064x}"),
    )
    snap, tracker_snap = _latest_snapshot(db, pagos), _latest_snapshot(db, ids["tracker"])
    for name, legal, system, days in (
        ("Cliente Ficticio Uno", "Ficticia Uno LLC", "zoho", 30),
        ("Cliente Ficticio Dos", "Ficticia Dos SRL", "bejerman", 15),
    ):
        client_id = db.execute(
            "INSERT INTO client (name) VALUES (%s) RETURNING id", (name,)
        ).fetchone()[0]
        ids[name] = client_id
        db.execute(
            "INSERT INTO client_legal_entity (client_id, legal_name, source_system,"
            " payment_terms_days) VALUES (%s, %s, %s, %s)",
            (client_id, legal, system, days),
        )
        db.execute(
            "INSERT INTO client_alias (source, text, client_id, author, reason)"
            " VALUES ('Pagos', %s, %s, 'ariel', 'prueba')",
            (name.lower(), client_id),
        )
    paid = db.execute(
        "INSERT INTO cell_change (source_tab_id, from_snapshot, to_snapshot, change_type,"
        " row_key, cell_ref, old_color, new_color, attributed_editor_ids,"
        " attribution_certainty, attributed_at)"
        " VALUES (%s, %s, %s, 'color', 'cliente ficticio dos', 'E4', '#ff9900', '#d9ead3',"
        " '{people/222}', 'cierta', '2026-09-20 10:00+00') RETURNING id",
        (pagos, snap - 1, snap),
    ).fetchone()[0]
    inc, sa = "Craftech-io Inc.", "Craftech S.A."
    for text, month, legal, state, amount, currency, net, cell in (
        ("cliente ficticio uno", "2026-09-01", inc, "retraso", 1100, "USD", None, "D3"),
        ("cliente ficticio dos", "2026-09-01", sa, "pagada", 5000, "ARS", 4000, "E4"),
        ("texto huerfano", "2026-09-01", inc, "enviada", 1200, "USD", None, "F5"),
        ("cliente ficticio uno", "2026-08-01", inc, "confirmada", 1300, "USD", None, "C3"),
    ):  # fmt: skip
        db.execute(
            "INSERT INTO invoice (source_tab_id, block, row_key, series_order, month,"
            " legal_entity, state, amount, currency, net_ars, fx_rate_to_confirm,"
            " alias_source, alias_text, snapshot_id, cell_ref, rules_version)"
            " VALUES (%s, 'Cliente', %s, 1, %s, %s, %s, %s, %s, %s, false, 'Pagos', %s, %s, %s,"
            " 'v1')",
            (pagos, text, month, legal, state, amount, currency, net, text, snap, cell),
        )
    db.execute(
        "INSERT INTO payment (source_tab_id, block, row_key, series_order, month, legal_entity,"
        " cell_change_id, snapshot_id, rules_version)"
        " VALUES (%s, 'Cliente', 'cliente ficticio dos', 1, '2026-09-01', 'Craftech S.A.', %s,"
        " %s, 'v1')",
        (pagos, paid, snap),
    )
    # September's total misses 2 against its invoices; August's matches.
    db.execute(
        "INSERT INTO payment_total (source_tab_id, row_key, month, amount, snapshot_id, cell_ref,"
        " rules_version) VALUES (%s, 'total', '2026-09-01', 7302, %s, 'E1', 'v1'),"
        " (%s, 'total', '2026-08-01', 1300, %s, 'C1', 'v1')",
        (pagos, snap, pagos, snap),
    )
    db.execute(
        "INSERT INTO funding_milestone (source_tab_id, origin, block, row_key, program,"
        " program_order, provisional_key, month, amount_usd, alias_source, alias_text,"
        " snapshot_id, cell_ref, rules_version)"
        " VALUES (%s, 'pagos', 'Fundings de AWS', 'cliente ficticio uno', 'Programa Ficticio',"
        " 1, true, '2026-09-01', 700, 'Pagos', 'cliente ficticio uno', %s, 'G6', 'v1')",
        (pagos, snap),
    )
    db.execute(
        "INSERT INTO funding_milestone (source_tab_id, origin, block, row_key, program,"
        " opportunity, fund_claim_id, program_order, provisional_key, amount_usd, status,"
        " business_unit, estimated_signoff, estimated_collection, invoice_loaded, paid_on,"
        " alias_source, alias_text, snapshot_id, cell_ref, rules_version)"
        " VALUES (%s, 'tracker', 'FUNDINGS', 'cliente ficticio uno', 'Programa Ficticio',"
        " 'Oportunidad Ficticia', 'FC-0001', 1, false, 700, 'Aprobado', 'Unidad Ficticia',"
        " '2026-09-05', '2026-10-05', true, '2026-09-15', 'FUNDINGS', 'cliente ficticio uno',"
        " %s, 'C2', 'v1')",
        (ids["tracker"], tracker_snap),
    )
    duplicate = {
        "tracker": {"planilla": "Planilla Ficticia A", "pestaña": "FUNDINGS", "cell_ref": "C2"},
        "pagos": {"planilla": "Planilla Ficticia B", "pestaña": "Pagos", "cell_ref": "G6"},
    }
    db.execute(
        "INSERT INTO issue (issue_type, stable_key, source_id, source_tab_id, details)"
        " VALUES ('funding_duplicado', 'dup-1', %s, %s, %s)",
        (ids["a"], ids["tracker"], json.dumps(duplicate)),
    )
    for key, text in (("sin-1", "texto huerfano"), ("sin-2", "texto ya resuelto")):
        ids[key] = db.execute(
            "INSERT INTO issue (issue_type, stable_key, source_id, source_tab_id, details)"
            " VALUES ('alias_sin_cliente', %s, %s, %s, %s) RETURNING id",
            (key, ids["b"], pagos, json.dumps({"source": "Pagos", "text": text})),
        ).fetchone()[0]
    db.execute(
        "INSERT INTO issue_resolution (issue_id, action, author, reason)"
        " VALUES (%s, 'resuelto', 'Revisora Ficticia', 'vinculado')",
        (ids["sin-2"],),
    )
    return ids


def test_the_income_screens_answer_200_and_are_in_the_menu(db, client):
    _seed_ingresos(db)
    for path in ("/facturas", "/fundings", "/clientes"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.headers["content-security-policy"] == "default-src 'self'"
        assert f'<a href="{path}">' in client.get("/cambios").text


def test_facturas_shows_the_state_with_its_color_and_filters_by_state(db, client):
    ids = _seed_ingresos(db)
    html = client.get("/facturas?mes=2026-09").text
    assert "Cliente Ficticio Uno" in html and "Ficticia Uno LLC" in html
    assert "Craftech-io Inc." in html and "Ficticia Dos SRL" in html
    assert 'class="estado-retraso"' in html and 'class="estado-pagada"' in html
    assert 'value="#ff00ff"' in html and 'value="#d9ead3"' in html
    assert "1,100.00" in html and "4,000.00" in html  # the amount and the ARS net
    assert "2026-09-20" in html and "cierta" in html  # the payment, its date and certainty
    assert "sin cliente" in html  # the row whose text has no alias
    assert "1,300.00" not in html  # August is another month
    only_late = client.get("/facturas?mes=2026-09&estado=retraso").text
    assert "Cliente Ficticio Uno" in only_late and "1,100.00" in only_late
    assert "Ficticia Dos SRL" not in only_late and "1,200.00" not in only_late
    by_entity = client.get("/facturas?mes=2026-09&entidad=Craftech+S.A.").text
    assert "Ficticia Dos SRL" in by_entity and "1,100.00" not in by_entity
    by_client = client.get(f"/facturas?mes=2026-09&cliente={ids['Cliente Ficticio Uno']}").text
    assert "1,100.00" in by_client and "5,000.00" not in by_client


def test_an_invoice_links_to_its_source_cell(db, client):
    _seed_ingresos(db)
    html = client.get("/facturas?mes=2026-09&estado=retraso").text
    assert 'href="https://docs.google.com/spreadsheets/d/file-b/edit#gid=2&amp;range=D3"' in html


def test_a_parity_difference_is_highlighted_and_zero_is_not(db, client):
    _seed_ingresos(db)
    september = client.get("/facturas?mes=2026-09").text
    assert 'class="num parity-off">2.00</td>' in september
    august = client.get("/facturas?mes=2026-08").text
    assert '<td class="num">0.00</td>' in august and "parity-off" not in august


def test_fundings_shows_the_origin_and_marks_duplicates_and_provisional_keys(db, client):
    _seed_ingresos(db)
    html = client.get("/fundings").text
    assert ">pagos</td>" in html and ">tracker</td>" in html
    assert html.count("duplicado</a>") == 2
    assert html.count("clave provisional") == 1
    assert "Oportunidad Ficticia" in html and "2026-10-05" in html
    # The tracker milestone paid in September has no Pagos confirmados total to match.
    assert 'class="num parity-off">-700.00</td>' in html


def test_clientes_lists_rows_without_client_and_has_no_edit_control(db, client):
    ids = _seed_ingresos(db)
    html = client.get("/clientes").text
    assert "Ficticia Uno LLC" in html and "30" in html and "cliente ficticio uno" in html
    assert f'href="/problemas/{ids["sin-1"]}"' in html and "texto huerfano" in html
    assert "texto ya resuelto" not in html
    for control in ("<form", "<input", "<button", "<textarea", "<select"):
        assert control not in html


def test_the_web_has_no_new_post_route():
    posts = {r.path for r in web.app.routes if "POST" in getattr(r, "methods", set())}
    assert posts == {"/fuentes/{source_id}/leer-ahora"}


@pytest.mark.parametrize(
    "path",
    [
        "/facturas?mes=2026-13",
        "/facturas?mes=septiembre",
        "/facturas?estado=perdida",
        "/facturas?entidad=Otra+S.A.",
        "/facturas?cliente=uno",
    ],
)
def test_invalid_income_filter_is_400_without_the_database(monkeypatch, path):
    test_invalid_filter_is_400_without_the_database(monkeypatch, path)


YEAR = date.today().year


def _seed_inicio(db) -> dict:
    """On top of _seed, in March of the current year: an accrual, a USD invoice, an ARS one with
    its amount in USD, another without it, payments of all three, a funding milestone from each
    side, an AWS total that misses, issues of three types (one reopened), a source that failed
    before its last read and one that is failing now with a pending read. A May funding and last
    year's parities sit outside March."""
    ids = _seed(db)
    pagos, march = ids["tab_b"], date(YEAR, 3, 1)
    snap = _latest_snapshot(db, pagos)
    db.execute(
        "INSERT INTO accrual (source_tab_id, block, row_key, series_order, month, amount_usd,"
        " alias_source, alias_text, snapshot_id, cell_ref, rules_version)"
        " VALUES (%s, 'Cliente', 'cliente ficticio', 1, %s, 2000, 'VENTAS', 'cliente ficticio',"
        " %s, 'B2', 'v1')",
        (pagos, march, snap),
    )
    inc, sa = "Craftech-io Inc.", "Craftech S.A."
    for text, legal, state, amount, currency, net_ars, usd, cell in (
        ("cliente usd", inc, "a facturar", 1000, "USD", None, None, "C3"),
        ("cliente ars", sa, "pagada", 121000, "ARS", 121000, 100, "C4"),
        ("cliente ars sin usd", sa, "pagada", 50000, "ARS", 50000, None, "C5"),
    ):  # fmt: skip
        db.execute(
            "INSERT INTO invoice (source_tab_id, block, row_key, series_order, month,"
            " legal_entity, state, amount, currency, net_ars, inferred_usd, fx_rate_to_confirm,"
            " alias_source, alias_text, snapshot_id, cell_ref, rules_version)"
            " VALUES (%s, 'Cliente', %s, 1, %s, %s, %s, %s, %s, %s, %s, false, 'Pagos', %s, %s,"
            " %s, 'v1')",
            (pagos, text, march, legal, state, amount, currency, net_ars, usd, text, snap, cell),
        )
    for text, legal in (("cliente usd", inc), ("cliente ars", sa), ("cliente ars sin usd", sa)):
        db.execute(
            "INSERT INTO payment (source_tab_id, block, row_key, series_order, month,"
            " legal_entity, snapshot_id, rules_version)"
            " VALUES (%s, 'Cliente', %s, 1, %s, %s, %s, 'v1')",
            (pagos, text, march, legal, snap),
        )
    ids["tracker"] = db.execute(
        "INSERT INTO source_tab (source_id, sheet_id, name, class)"
        " VALUES (%s, 3, 'FUNDINGS', 'CARGA') RETURNING id",
        (ids["a"],),
    ).fetchone()[0]
    tracker_snap = db.execute(
        "INSERT INTO snapshot (source_tab_id, drive_version, drive_modified_at,"
        " duration_ms, origin, content_hash, content, row_count, col_count, cell_count)"
        " VALUES (%s, 3, now(), 120, 'lectura', %s, '{}', 1, 1, 1) RETURNING id",
        (ids["tracker"], f"{3:064x}"),
    ).fetchone()[0]
    last_march = date(YEAR - 1, 3, 1)
    for order, month, amount, cell in ((1, march, 700, "G6"), (2, date(YEAR, 5, 1), 400, "I6"),
                                       (3, last_march, 700, "G7")):  # fmt: skip
        db.execute(
            "INSERT INTO funding_milestone (source_tab_id, origin, block, row_key, program,"
            " program_order, provisional_key, month, amount_usd, alias_source, alias_text,"
            " snapshot_id, cell_ref, rules_version)"
            " VALUES (%s, 'pagos', 'Fundings de AWS', 'cliente usd', 'Programa Ficticio',"
            " %s, true, %s, %s, 'Pagos', 'cliente usd', %s, %s, 'v1')",
            (pagos, order, month, amount, snap, cell),
        )
    # Paid in March (and last March) with no "Pagos confirmados" total: that parity misses 300.
    for order, month, cell in ((1, march, "C2"), (2, last_march, "C3")):
        db.execute(
            "INSERT INTO funding_milestone (source_tab_id, origin, block, row_key, program,"
            " fund_claim_id, program_order, provisional_key, amount_usd, business_unit,"
            " invoice_loaded, paid_on, alias_source, alias_text, snapshot_id, cell_ref,"
            " rules_version)"
            " VALUES (%s, 'tracker', 'FUNDINGS', 'cliente usd', 'Programa Ficticio', %s, %s,"
            " false, 300, 'Unidad Ficticia', true, %s, 'FUNDINGS', 'cliente usd', %s, %s, 'v1')",
            (ids["tracker"], f"FC-000{order}", order, month + timedelta(days=14), tracker_snap,
             cell),
        )  # fmt: skip
    # "TOTAL PAGOS AWS" says 650 for the 700 of the Pagos milestone: that parity misses -50.
    for month, cell in ((march, "G1"), (last_march, "G2")):
        db.execute(
            "INSERT INTO funding_total (source_tab_id, row_key, month, amount, snapshot_id,"
            " cell_ref, rules_version) VALUES (%s, 'total pagos aws', %s, 650, %s, %s, 'v1')",
            (pagos, month, snap, cell),
        )
    for key, kind in (("alias-1", "alias_sin_cliente"), ("alias-2", "alias_sin_cliente"),
                      ("dup-1", "funding_duplicado"),
                      ("fila-1", "fila_sin_interpretar")):  # fmt: skip
        ids[key] = db.execute(
            "INSERT INTO issue (issue_type, stable_key, source_id, source_tab_id)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            (kind, key, ids["b"], pagos),
        ).fetchone()[0]
    db.execute(
        "INSERT INTO issue_resolution (issue_id, action, author, reason)"
        " VALUES (%s, 'resuelto', 'Revisora Ficticia', 'prueba'),"
        " (%s, 'ignorado', 'Revisora Ficticia', 'prueba')",
        (ids["alias-2"], ids["dup-1"]),
    )
    # Resolved yesterday and seen again since: reopened, so it counts.
    db.execute(
        "INSERT INTO issue_resolution (issue_id, action, author, reason, created_at)"
        " VALUES (%s, 'resuelto', 'Revisora Ficticia', 'prueba', now() - interval '1 day')",
        (ids["fila-1"],),
    )
    db.execute(
        "INSERT INTO system_event (kind, source_id, occurred_at, details)"
        " VALUES ('source_failed', %s, '2026-10-01 12:00-03', '{\"error\": \"Error Ficticio\"}')",
        (ids["a"],),
    )
    # B fails after its last read, and a read of it is pending.
    db.execute(
        "INSERT INTO system_event (kind, source_id, details)"
        " VALUES ('source_failed', %s, '{\"error\": \"Error Vigente\"}')",
        (ids["b"],),
    )
    db.execute("INSERT INTO read_request (source_id, requested_by) VALUES (%s, 'cli')", (ids["b"],))
    return ids


def _month_row(html: str, month: int) -> str:
    return re.search(rf'<tr id="mes-{YEAR}-{month:02d}">(.*?)</tr>', html, re.S).group(1)


def test_inicio_sums_each_month_in_usd(db, client):
    _seed_inicio(db)
    html = client.get("/").text
    march = _month_row(html, 3)
    # Devengado 2000; facturado 1000 USD + the 100 USD of the ARS invoice, never its pesos;
    # cobrado the same, since both are paid.
    assert re.findall(r'<td class="num">([^<]*)</td>', march)[:3] == [
        "2,000.00", "1,100.00", "1,100.00"
    ]  # fmt: skip
    assert "121,000" not in html and "50,000" not in html
    # The ARS invoice without its USD amount and its payment are counted apart, with a link.
    assert f'<a href="/facturas?mes={YEAR}-03">1 factura, 1 cobro</a>' in march
    assert "por mes de la factura" in html


def test_inicio_shows_twelve_months_and_a_total(db, client):
    _seed_inicio(db)
    html = client.get("/").text
    for month in range(1, 13):
        row = _month_row(html, month)
        assert f'<a href="/facturas?mes={YEAR}-{month:02d}">{YEAR}-{month:02d}</a>' in row
    assert '<td class="num">0.00</td>' in _month_row(html, 1)
    total = re.search(r'<tr class="total">(.*?)</tr>', html, re.S).group(1)
    assert re.findall(r'<td class="num">([^<]*)</td>', total) == [
        "2,000.00", "1,100.00", "1,100.00"
    ]  # fmt: skip
    assert "1 factura, 1 cobro" in total


def test_inicio_keeps_fundings_apart_and_highlights_both_parities(db, client):
    _seed_inicio(db)
    html = client.get("/").text
    assert "700.00" not in _month_row(html, 3) and "1,800.00" not in html
    fundings = html[html.index('id="fundings"') :]
    march = re.search(rf'<tr id="funding-{YEAR}-03">(.*?)</tr>', fundings, re.S).group(1)
    assert "700.00" in march
    may = re.search(rf'<tr id="funding-{YEAR}-05">(.*?)</tr>', fundings, re.S).group(1)
    assert "400.00" in may
    assert f"<td>{YEAR - 1}-" not in fundings  # last year's parities stay out
    assert 'href="/fundings"' in fundings
    assert 'class="num parity-off">-300.00</td>' in fundings  # Pagos confirmados
    assert 'class="num parity-off">-50.00</td>' in fundings  # TOTAL PAGOS AWS
    assert "Pagos confirmados" in fundings and "TOTAL PAGOS AWS" in fundings


def test_inicio_counts_open_issues_by_type(db, client):
    _seed_inicio(db)
    html = client.get("/").text
    assert '<a href="/problemas?tipo=alias_sin_cliente">alias_sin_cliente</a></td>' in html
    assert '<a href="/problemas?tipo=color_desconocido">color_desconocido</a></td>' in html
    assert "funding_duplicado" not in html  # ignored: not open
    issues = html[html.index('id="problemas"') : html.index('id="fuentes"')]
    assert '<a href="/problemas?tipo=fila_sin_interpretar">' in issues  # reopened: open again
    assert re.findall(r'<td class="num">(\d+)</td>', issues) == ["1", "1", "1"]
    # Every type the dashboard links to is accepted by the Problemas filter.
    assert client.get("/problemas?tipo=alias_sin_cliente").status_code == 200


def test_the_problemas_filter_accepts_every_type_the_database_allows(db, client):
    (check,) = db.execute(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint"
        " WHERE conname = 'issue_issue_type_check'"
    ).fetchone()
    assert set(web.ISSUE_TYPES) == set(re.findall(r"'(\w+)'", check))


def test_inicio_shows_each_source_last_read_and_error(db, client):
    _seed_inicio(db)
    html = client.get("/").text
    sources = html[html.index('id="fuentes"') :]
    assert "Planilla Ficticia A" in sources and "Planilla Ficticia B" in sources
    assert "Última lectura con cambios" in sources
    # A's error came before its last read: shown, but not as current. B's is current.
    assert '<span class="muted">2026-10-01 12:00:00: Error Ficticio</span>' in sources
    assert re.search(r'<span class="warning">[^<]*: Error Vigente</span>', sources)
    assert sources.count("pendiente desde") == 1
    assert 'href="/fuentes"' in sources


def test_inicio_is_read_only_and_logs_no_names_or_amounts(db, client, caplog):
    _seed_inicio(db)
    with caplog.at_level(logging.DEBUG):
        html = client.get("/").text
    for control in ("<form", "<input", "<button", "<textarea", "<select"):
        assert control not in html
    for secret in ("Planilla Ficticia", "cliente", "2000", "1100", "Error Ficticio"):
        assert secret not in caplog.text


def _shift(months: int) -> date:
    n = date.today().year * 12 + date.today().month - 1 + months
    return date(n // 12, n % 12 + 1, 1)


# Three closed real months, the current one and a projected one.
R1, R2, R3, CUR, NEXT = (_shift(n) for n in (-3, -2, -1, 0, 1))
INC = "Craftech Inc. en dólares"
SHEET_VALUE = 98765  # what the Resumen says: never shown


def _seed_caja(db):
    """A Resumen of five months with two blocks, and the Mesh and Galicia movements behind it.
    Mesh ends R1 at -200 (100 in, 300 out), then gets 1000 in R2 and spends 100 in R3."""
    source = db.execute(
        "INSERT INTO source (title, drive_id) VALUES ('Planilla Ficticia C', 'file-c') RETURNING id"
    ).fetchone()[0]
    tab = db.execute(
        "INSERT INTO source_tab (source_id, sheet_id, name, class)"
        " VALUES (%s, 3, 'Resumen Ficticio', 'DERIVADA') RETURNING id",
        (source,),
    ).fetchone()[0]
    snap = db.execute(
        "INSERT INTO snapshot (source_tab_id, drive_version, drive_modified_at, duration_ms,"
        " origin, content_hash, content, row_count, col_count, cell_count)"
        " VALUES (%s, 1, now(), 120, 'lectura', %s, '{}', 1, 1, 1) RETURNING id",
        (tab, f"{3:064x}"),
    ).fetchone()[0]
    rows = [
        # block, block_order, label, row_order, unit, rubros, banks, balance, sign, parametro
        (INC, 0, "Saldo Inicial", 0, "usd", [], ["Mesh"], "inicial", 1, None),
        (INC, 0, "Pagos Recibidos INC", 1, "usd", ["COBRANZA"], [], None, 1, None),
        (INC, 0, "Gastos", 2, "usd", ["04. Alquileres"], [], None, -1, None),
        (INC, 0, "USD enviados a la S.A.", 3, "usd", ["CAJA. Intercompany"], [], None, -1,
         "USD a enviar para cerrar el mes con 4.000.000 de pesos"),
        (INC, 0, "Fila Ficticia Sin Regla", 4, "usd", [], [], None, 1, None),
        (INC, 0, "Saldo Final", 5, "usd", [], ["Mesh"], "final", 1, None),
        ("Argentina en miles de pesos", 1, "Saldo Final", 0, "ars", [], ["GALICIA"], "final", 1,
         None),
    ]  # fmt: skip
    for block, b_order, label, r_order, unit, rubros, banks, balance, sign, parametro in rows:
        db.execute(
            "INSERT INTO cashflow_row (block, block_order, label, row_order, unit, rubros, banks,"
            " balance, sign, parametro) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (block, b_order, label, r_order, unit, rubros, banks, balance, sign, parametro),
        )
        for n, month in enumerate((R1, R2, R3, CUR, NEXT)):
            db.execute(
                "INSERT INTO cashflow_sheet_cell (source_tab_id, snapshot_id, block, label, month,"
                " value, cell_ref, has_formula) VALUES (%s, %s, %s, %s, %s, %s, %s, false)",
                (tab, snap, block, label, month, SHEET_VALUE, f"{'CDEFG'[n]}{r_order + 4}"),
            )
    moves = [
        ("Mesh", "USD", "COBRANZA", 100, R1),
        ("Mesh", "USD", "04. Alquileres", -300, R1),
        ("Mesh", "USD", "COBRANZA", 1000, R2),
        ("Mesh", "USD", "04. Alquileres", -100, R3),
        ("Mesh", "USD", "COBRANZA", 7, CUR),
        ("GALICIA", "ARS", "COBRANZA", 5000, R2),
    ]
    for n, (bank, currency, rubro, amount, month) in enumerate(moves):
        db.execute(
            "INSERT INTO cash_movement (source_tab_id, snapshot_id, rules_version, row_key,"
            " cell_ref, month, bank, historical, adjustment, currency, amount, rubro)"
            " VALUES (%s, %s, 'v1', %s, %s, %s, %s, false, false, %s, %s, %s)",
            (tab, snap, f"fila-{n}", f"K{n + 2}", month, bank, currency, amount, rubro),
        )


def _cell(html: str, row: str, month: date) -> str:
    """The <td> of a row and month of the cashflow table."""
    found = re.search(rf'<td id="celda-{re.escape(row)}-{month:%Y-%m}"[^>]*>[^<]*</td>', html)
    assert found, (row, month)
    return found.group(0)


def test_caja_answers_200_and_is_in_the_menu(db, client):
    _seed_caja(db)
    response = client.get("/caja")
    assert response.status_code == 200
    assert response.headers["content-security-policy"] == "default-src 'self'"
    assert '<a href="/caja">Caja</a>' in client.get("/cambios").text


def test_caja_shows_the_five_indicators_with_their_formula_as_proposed(db, client):
    _seed_caja(db)
    html = client.get("/caja").text
    indicators = html[html.index('id="indicadores"') : html.index('id="tabla"')]
    for name in ("Caja hoy", "Salida mensual", "Meses de cobertura", "Cierre de marzo",
                 "Cierre de marzo con pagos proyectados"):  # fmt: skip
        assert f"<dt>{name}</dt>" in indicators, name
    assert indicators.count("propuesto") == 5
    assert "Saldo Final de «Craftech Inc. en dólares» del último mes real cerrado" in indicators
    assert "Caja hoy ÷ salida mensual." in indicators
    assert "700.00" in indicators  # caja hoy: the Saldo Final of R3


def test_caja_table_shows_blocks_rows_and_months_with_a_sticky_concept_column(db, client):
    _seed_caja(db)
    html = client.get("/caja").text
    table = html[html.index('id="tabla"') :]
    assert '<div class="caja-scroll">' in table
    assert table.index(INC) < table.index("Argentina en miles de pesos")
    for row in ("Saldo Inicial", "Pagos Recibidos INC", "Gastos", "Fila Ficticia Sin Regla"):
        assert f'<th class="concepto">{row}</th>' in table, row
    for month in (R1, R2, R3, CUR, NEXT):
        assert f"{month:%Y-%m}" in table
    assert "1,000.00" in _cell(html, f"{INC}-Pagos Recibidos INC", R2)
    assert "5,000.00" in _cell(html, "Argentina en miles de pesos-Saldo Final", R2)
    css = client.get("/static/style.css").text
    assert re.search(r"\.concepto \{[^}]*position: sticky", css)
    assert re.search(r"\.caja-scroll \{[^}]*overflow-x: auto", css)


def test_caja_cells_carry_their_period_sign_and_origin(db, client):
    _seed_caja(db)
    html = client.get("/caja").text
    real = _cell(html, f"{INC}-Saldo Final", R3)
    assert "periodo-real" in real and "negativo" not in real and "700.00" in real
    assert "origen: recalculada" in real and "Planilla Ficticia C / Resumen Ficticio!E9" in real
    assert "negativo" in _cell(html, f"{INC}-Saldo Final", R1)  # -200
    assert "periodo-en_curso" in _cell(html, f"{INC}-Saldo Final", CUR)
    projected = _cell(html, f"{INC}-Saldo Final", NEXT)
    assert "periodo-proyectado" in projected and "sin-valor" in projected
    assert "origen: sin_regla" in projected and "mes proyectado" in projected
    no_rule = _cell(html, f"{INC}-Fila Ficticia Sin Regla", R2)
    assert "sin-valor" in no_rule and "fila sin regla ratificada" in no_rule
    assert "origen: parametro" in _cell(html, f"{INC}-USD enviados a la S.A.", NEXT)
    legend = html[html.index('id="leyenda"') :]
    for mark in ("periodo-en_curso", "periodo-proyectado", "negativo", "sin-valor"):
        assert f'class="{mark}"' in legend, mark
    assert "98765" not in html and "98,765" not in html  # the Resumen's values


def test_caja_chart_is_server_side_svg_without_scripts(db, client):
    _seed_caja(db)
    response = client.get("/caja")
    html = response.text
    chart = html[html.index("<svg") : html.index("</svg>")]
    # Saldo Final of Craftech Inc.: R1, R2, R3 and the current month; NEXT has no value.
    assert chart.count('<rect class="barra') == 4
    assert chart.count('class="barra negativa"') == 1
    assert f"{NEXT:%Y-%m}" not in chart
    assert "<script" not in html.lower() and "style=" not in html
    assert (
        response.headers["content-security-policy"]
        == client.get("/cambios").headers["content-security-policy"]
    )


def test_caja_without_a_resumen_says_so(db, client):
    html = client.get("/caja").text
    assert "Todavía no hay cashflow" in html and "<svg" not in html


def test_caja_is_read_only_and_logs_no_names_or_amounts(db, client, caplog):
    _seed_caja(db)
    with caplog.at_level(logging.DEBUG):
        html = client.get("/caja").text
    for control in ("<form", "<input", "<button", "<textarea", "<select"):
        assert control not in html
    for secret in ("Planilla Ficticia", "Saldo", "1000", "700"):
        assert secret not in caplog.text
