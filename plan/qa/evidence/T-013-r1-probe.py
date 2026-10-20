"""QA T-013 round 1 probes: vincular_alias against the real interpreter. Invented data only."""

import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from test_interpret import _accruals, _import, env, fake  # noqa: F401
from test_mcp import _call, server, urls  # noqa: F401

from craftech_os import cli

ARGS = {"autor": "QA", "motivo": "sondeo"}


def _state(db, text, tab="VENTAS"):
    return db.execute(
        "SELECT estado FROM mcp.issues WHERE tipo = 'alias_sin_cliente'"
        " AND detalle->>'text' = %s AND pestaña = %s",
        (text, tab),
    ).fetchall()


def _counts(db):
    return db.execute(
        "SELECT (SELECT count(*) FROM client), (SELECT count(*) FROM client_alias),"
        " (SELECT count(*) FROM issue_resolution)"
    ).fetchone()


def test_e2e_real_interpreter_link_then_reinterpret_stays_resolved(db, env, fake, server):  # noqa: F811
    _import(env)
    assert _state(db, "cliente uno") == [("abierto",)]
    out = _call(
        server,
        "vincular_alias",
        fuente="COBRANZAS ficticias/ventas",
        texto="  Clíente   ÚNO ",
        cliente="Ficticia Uno",
        crear_cliente=True,
        **ARGS,
    )
    print("OUT", out)
    assert out["cliente_creado"] is True and len(out["problemas_resueltos"]) == 1
    clients = {(r[1], r[8]) for r in _accruals(db)}
    assert ("cliente uno", "Ficticia Uno") in clients
    assert ("cliente uno (2)", "Ficticia Uno") in clients
    assert ("cliente dos", None) in clients
    assert _state(db, "cliente uno") == [("resuelto",)]
    assert cli.main(["interpret", "--all"]) == 0
    assert _state(db, "cliente uno") == [("resuelto",)], "reinterpret must not reopen"
    assert _state(db, "cliente dos") == [("abierto",)]
    ev = [e for (e,) in db.execute("SELECT details FROM system_event WHERE kind='mcp_write'")]
    print("EVENTS", ev)
    assert {"herramienta": "vincular_alias", "autor": "QA"} in ev


def test_existing_client_matched_by_case_and_accents_no_new_client(db, env, fake, server):  # noqa: F811
    _import(env)
    db.execute("INSERT INTO client (name) VALUES ('Ficticia Uno')")
    out = _call(
        server,
        "vincular_alias",
        fuente="Cobranzas Ficticias / VENTAS",
        texto="cliente uno",
        cliente="FICTÍCIA   uno",
        crear_cliente=True,
        **ARGS,
    )
    assert out["cliente_creado"] is False and out["cliente"] == "Ficticia Uno"
    assert db.execute("SELECT count(*) FROM client").fetchone()[0] == 1


def test_relink_second_decision_wins_and_resolves_nothing_twice(db, env, fake, server):  # noqa: F811
    _import(env)
    db.execute("INSERT INTO client (name) VALUES ('Ficticia Uno'), ('Ficticia Otra')")
    base = dict(fuente="Cobranzas Ficticias / VENTAS", texto="cliente uno", **ARGS)
    first = _call(server, "vincular_alias", cliente="Ficticia Uno", **base)
    second = _call(server, "vincular_alias", cliente="Ficticia Otra", **base)
    assert len(first["problemas_resueltos"]) == 1 and second["problemas_resueltos"] == []
    assert ("cliente uno", "Ficticia Otra") in {(r[1], r[8]) for r in _accruals(db)}
    assert db.execute("SELECT count(*) FROM issue_resolution").fetchone()[0] == 1


def test_reopened_problem_is_resolved_and_ignored_one_is_not(db, env, fake, server):  # noqa: F811
    _import(env)
    db.execute("INSERT INTO client (name) VALUES ('Ficticia Dos')")
    (issue,) = db.execute(
        "SELECT id FROM mcp.issues WHERE detalle->>'text' = 'cliente dos'"
    ).fetchone()
    _call(server, "resolver_problema", id=issue, accion="ignorado", **ARGS)
    out = _call(
        server,
        "vincular_alias",
        fuente="Cobranzas Ficticias / VENTAS",
        texto="cliente dos",
        cliente="Ficticia Dos",
        **ARGS,
    )
    assert out["problemas_resueltos"] == []
    assert _state(db, "cliente dos") == [("ignorado",)]


@pytest.mark.parametrize(
    "bad",
    [
        {"fuente": "   "},
        {"texto": " "},
        {"cliente": "\t"},
        {"fuente": "Cobranzas Ficticias"},
        {"fuente": "Cobranzas Ficticias / VENTAS / x"},
        {"fuente": "/"},
        {"autor": "\n"},
        {"motivo": "  "},
    ],
)
def test_invalid_inputs_write_nothing(db, env, fake, server, bad):  # noqa: F811
    _import(env)
    before = _counts(db)
    args = dict(
        fuente="Cobranzas Ficticias / VENTAS",
        texto="cliente uno",
        cliente="Nuevo",
        crear_cliente=True,
        **ARGS,
    )
    with pytest.raises(ToolError) as e:
        _call(server, "vincular_alias", **{**args, **bad})
    print("ERR", bad, "->", e.value)
    assert _counts(db) == before


def test_missing_author_argument_is_rejected(db, env, fake, server):  # noqa: F811
    _import(env)
    before = _counts(db)
    with pytest.raises(Exception) as e:
        _call(
            server,
            "vincular_alias",
            fuente="Cobranzas Ficticias / VENTAS",
            texto="cliente uno",
            cliente="Nuevo",
            crear_cliente=True,
            motivo="x",
        )
    print("ERR missing autor ->", type(e.value).__name__, e.value)
    assert _counts(db) == before


@pytest.mark.parametrize(
    "name",
    ["<script>alert(1)</script>", "Ñandú 🚀 Ltda.", "x" * 2000, "'; DROP TABLE client; --"],
)
def test_odd_client_names_are_stored_as_data(db, env, fake, server, name):  # noqa: F811
    _import(env)
    out = _call(
        server,
        "vincular_alias",
        fuente="Cobranzas Ficticias / VENTAS",
        texto="cliente uno",
        cliente=name,
        crear_cliente=True,
        **ARGS,
    )
    assert out["cliente"] == name.strip()
    assert db.execute("SELECT count(*) FROM client").fetchone()[0] == 1


def test_similar_list_with_no_clients_and_no_creation(db, env, fake, server):  # noqa: F811
    _import(env)
    with pytest.raises(ToolError, match="ninguno") as e:
        _call(
            server,
            "vincular_alias",
            fuente="Cobranzas Ficticias / VENTAS",
            texto="cliente uno",
            cliente="Nadie",
            **ARGS,
        )
    print("ERR", e.value)
    assert _counts(db) == (0, 0, 0)


def test_text_with_no_problem_still_links_and_returns_empty(db, env, fake, server):  # noqa: F811
    _import(env)
    db.execute("INSERT INTO client (name) VALUES ('Ficticia Uno')")
    out = _call(
        server,
        "vincular_alias",
        fuente="Cobranzas Ficticias / VENTAS",
        texto="texto que no esta en la planilla",
        cliente="Ficticia Uno",
        **ARGS,
    )
    print("OUT", json.dumps(out, ensure_ascii=False))
    assert out["problemas_resueltos"] == []


def test_reopened_alias_problem_is_resolved_by_link(db, env, fake, server):  # noqa: F811
    _import(env)
    (issue,) = db.execute(
        "SELECT id FROM mcp.issues WHERE detalle->>'text' = 'cliente uno'"
    ).fetchone()
    _call(server, "resolver_problema", id=issue, accion="resuelto", **ARGS)
    assert cli.main(["interpret", "--all"]) == 0
    print("STATE after reinterpret", _state(db, "cliente uno"))
    assert _state(db, "cliente uno") == [("reabierto",)]
    out = _call(
        server,
        "vincular_alias",
        fuente="Cobranzas Ficticias / VENTAS",
        texto="cliente uno",
        cliente="Ficticia Uno",
        crear_cliente=True,
        **ARGS,
    )
    assert out["problemas_resueltos"] == [issue]
    assert _state(db, "cliente uno") == [("resuelto",)]
