"""The local web: read-only screens Cambios, Problemas and Fuentes, and the "leer ahora" button.

No login in the v0, so the port is published on 127.0.0.1 only. Every page is rendered on the
server; filters are GET forms validated against closed lists before reaching the database.
"""

import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import jinja2
import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from craftech_os.web import queries

HERE = Path(__file__).parent
TIMEZONE = os.environ.get("TZ") or "America/Argentina/Buenos_Aires"
CHANGE_TYPES = (
    "value", "formula_overridden", "formula", "color", "emptied", "row_inserted",
    "row_deleted", "row_moved", "column_inserted", "tab_added", "tab_deleted", "tab_renamed",
)  # fmt: skip
ISSUE_TYPES = (
    "color_desconocido",
    "alineacion_ambigua",
    "valor_ilegible",
    "pestana_sin_clasificar",
)
ISSUE_STATES = ("abierto", "resuelto", "ignorado", "reabierto")
READ_RESULTS = {
    "created": "Pedido de lectura creado: el worker la lee en la próxima vuelta.",
    "pending": "Ya había un pedido pendiente para esta planilla: no se creó otro.",
    "no_drive_id": "La planilla no tiene identificador de Drive: no se puede leer.",
}
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_TEXT = 200

# Cells hold text anyone can type, HTML and scripts included: autoescape is never optional.
env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(HERE / "templates"),
    autoescape=True,
    undefined=jinja2.StrictUndefined,
)
env.filters["when"] = lambda dt: dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "—"
env.filters["duration"] = lambda td: (
    str(td - timedelta(microseconds=td.microseconds)) if td else "—"
)
env.filters["pretty_json"] = lambda v: json.dumps(v, ensure_ascii=False, indent=2)
env.tests["hex_color"] = lambda v: bool(v and HEX_COLOR.match(v))
templates = Jinja2Templates(env=env)

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")


@app.middleware("http")
async def content_security_policy(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response


def _connect() -> psycopg.Connection:
    # Times are shown and filtered by day in Craftech's time zone.
    return psycopg.connect(
        os.environ["DATABASE_URL"], autocommit=True, options=f"-c TimeZone={TIMEZONE}"
    )


def _bad(name: str) -> HTTPException:
    return HTTPException(400, f"Filtro inválido: {name}")


def _id(params, name: str) -> int | None:
    value = params.get(name, "")
    if value == "":
        return None
    if not value.isascii() or not value.isdigit() or len(value) > 18:
        raise _bad(name)
    return int(value)


def _choice(params, name: str, allowed) -> str | None:
    value = params.get(name, "")
    if value == "":
        return None
    if value not in allowed:
        raise _bad(name)
    return value


def _text(params, name: str) -> str:
    value = params.get(name, "").strip()
    if len(value) > MAX_TEXT or "\x00" in value:
        raise _bad(name)
    return value


def _date(params, name: str) -> date | None:
    value = params.get(name, "")
    if value == "":
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise _bad(name) from None


def _page(params) -> int:
    page = _id(params, "pagina") or 1
    if page > 100_000:
        raise _bad("pagina")
    return page


def _attribution(change: dict, names: dict[str, str]) -> str:
    ids = change["attributed_editor_ids"] or []
    shown = ", ".join(names.get(i, i) for i in ids)
    if not ids:
        if change["attribution_certainty"] == "sin_datos":
            return "sin atribuir (Google no informó editor)"
        return "sin atribuir"
    if change["attribution_certainty"] == "una_de":
        return f"una de: {shown}"
    at = change["attributed_at"]
    return f"{shown}, {at:%Y-%m-%d %H:%M}" if at else shown


@app.get("/")
def root():
    return RedirectResponse("/cambios", status_code=303)


@app.get("/cambios", response_class=HTMLResponse)
def cambios(request: Request):
    p = request.query_params
    f = {
        "planilla": _id(p, "planilla"),
        "pestana": _id(p, "pestana"),
        "tipo": _choice(p, "tipo", CHANGE_TYPES),
        "clave": _text(p, "clave"),
        "editor": _text(p, "editor"),
        "desde": _date(p, "desde"),
        "hasta": _date(p, "hasta"),
        "snapshot": _id(p, "snapshot"),
    }
    page = _page(p)
    with _connect() as conn:
        rows = queries.changes(conn, f, page)
        summary = queries.change_summary(conn, f)
        names = queries.editor_names(conn)
        context = {
            "f": f,
            "page": page,
            "rows": rows[: queries.PAGE_SIZE],
            "has_next": len(rows) > queries.PAGE_SIZE,
            "summary": summary,
            "sources": queries.sources(conn),
            "tabs": queries.tabs(conn),
            "editors": [(i, names.get(i, i)) for i in queries.editor_ids(conn)],
        }
    for row in context["rows"]:
        row["attribution"] = _attribution(row, names)
    query = {k: v for k, v in p.items() if k != "pagina"}
    return templates.TemplateResponse(
        request,
        "cambios.html",
        {
            **context,
            "query": query,
            "change_types": CHANGE_TYPES,
            "not_attributed": queries.NOT_ATTRIBUTED,
        },
    )


@app.get("/cambios/{change_id}", response_class=HTMLResponse)
def cambio(request: Request, change_id: int):
    with _connect() as conn:
        row = queries.change(conn, change_id)
        names = queries.editor_names(conn) if row else {}
    if row is None:
        raise HTTPException(404, "No existe ese cambio.")
    row["attribution"] = _attribution(row, names)
    return templates.TemplateResponse(request, "cambio.html", {"c": row})


@app.get("/problemas", response_class=HTMLResponse)
def problemas(request: Request):
    p = request.query_params
    f = {
        "tipo": _choice(p, "tipo", ISSUE_TYPES),
        "estado": _choice(p, "estado", ISSUE_STATES),
        "planilla": _id(p, "planilla"),
    }
    with _connect() as conn:
        rows = queries.issues(conn, f)
        all_sources = queries.sources(conn)
    return templates.TemplateResponse(
        request,
        "problemas.html",
        {
            "f": f,
            "rows": rows,
            "sources": all_sources,
            "issue_types": ISSUE_TYPES,
            "issue_states": ISSUE_STATES,
        },
    )


@app.get("/problemas/{issue_id}", response_class=HTMLResponse)
def problema(request: Request, issue_id: int):
    with _connect() as conn:
        row = queries.issue(conn, issue_id)
    if row is None:
        raise HTTPException(404, "No existe ese problema.")
    return templates.TemplateResponse(request, "problema.html", {"i": row})


@app.get("/fuentes", response_class=HTMLResponse)
def fuentes(request: Request):
    p = request.query_params
    result = _choice(p, "resultado", READ_RESULTS)
    with _connect() as conn:
        health = queries.health(conn)
        rows = queries.source_rows(conn)
        tabs = queries.tab_rows(conn)
    by_source = {}
    for tab in tabs:
        by_source.setdefault(tab["source_id"], []).append(tab)
    return templates.TemplateResponse(
        request,
        "fuentes.html",
        {
            "health": health,
            "rows": rows,
            "tabs": by_source,
            "message": READ_RESULTS[result] if result else None,
            "now": datetime.now().astimezone(),
        },
    )


@app.post("/fuentes/{source_id}/leer-ahora")
def leer_ahora(source_id: int):
    with _connect() as conn:
        result = queries.request_read(conn, source_id)
    if result is None:
        raise HTTPException(404, "No existe esa planilla.")
    return RedirectResponse(f"/fuentes?resultado={result}#fuente-{source_id}", status_code=303)


def _error_page(request: Request, status: int, message: str):
    return templates.TemplateResponse(
        request, "error.html", {"status": status, "message": message}, status_code=status
    )


@app.exception_handler(StarletteHTTPException)
def http_error(request: Request, exc: StarletteHTTPException):
    message = exc.detail if exc.status_code in (400, 404) else "No se pudo atender el pedido."
    if exc.status_code == 404 and exc.detail == "Not Found":
        message = "No existe esa página."
    return _error_page(request, exc.status_code, message)


@app.exception_handler(RequestValidationError)
def validation_error(request: Request, exc: RequestValidationError):
    # A path id that is not a number: the same answer as an invalid filter.
    return _error_page(request, 400, "Pedido inválido.")


@app.exception_handler(Exception)
def server_error(request: Request, exc: Exception):
    # Starlette still logs the traceback; the browser only sees a plain page.
    return _error_page(request, 500, "Error interno. El detalle quedó en el log del servicio web.")
