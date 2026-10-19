---
id: T-006
title: Web local de solo visualización: pantallas Cambios, Problemas y Fuentes, con botón "leer ahora"
status: in-progress
priority: high
lane: ui
depends_on: [T-004]
effort: M
milestone: A
branch: arielvinas/t-006
---

## Context

Unidad 5 del corte del ADR (`plan/adr/ADR-001-espejo-de-planillas-en-postgres.md`, cambios 1 y 7: sin API JSON, sin HTMX, páginas enteras con formularios GET; el proceso se llama `web`). Origen de producto: `docs/03-proposal.md` sección 4.6 (la web, sin login, solo visualización, pantallas Cambios, Problemas y Fuentes en la etapa A) y decisión 1 de Ariel ("la app sería para visualización solamente"). KICKOFF, objetivo 3 de la v0: que cualquier cambio en las planillas se vea: celda, valor anterior y nuevo, color, planilla, pestaña, cuándo y, si se puede, quién.

Seguridad (ADR, "Navegador → web"): sin login en la v0, por eso el puerto se publica solo en `127.0.0.1`; la única acción es "leer ahora", idempotente y sin efecto sobre datos; Jinja2 con autoescape obligatorio porque la pantalla Cambios muestra texto que alguien escribió en una celda y una celda puede contener HTML o un script.

Verificado en el repo tras T-004: existen `source`, `source_tab`, `snapshot`, `cell_change` (con columnas de atribución que T-005 llena; hasta entonces nulas), `issue`, `issue_resolution`, `v_issue`, `read_request`, `system_event`. Las vistas `v_editor` y `v_attribution_stats` las crea T-005, que corre en paralelo con este ticket: **este ticket no las usa y no agrega migraciones** (los archivos de migración se numeran en `core`; dos tickets activos no pueden compartir numeración). La web se conecta con el usuario de aplicación `craftech_app`: en la laptop, con el puerto en `127.0.0.1` y sin login, la frontera navegador → web está dentro de la misma zona de confianza que el worker; un rol de solo lectura para la web vuelve con el login de la etapa D.

## Scope

**Dónde vive:** `app/craftech_os/web/` (FastAPI, `templates/` Jinja2, un `static/style.css` sin framework), servicio `web` en Compose, CLI `craftech-os web`.

1. **Dependencias nuevas:** `fastapi`, `jinja2`, `uvicorn`, `python-multipart` (para el formulario POST). Sin Node, sin HTMX, sin librería de componentes.
2. **Servicio `web` en Compose:** imagen de T-001, comando `craftech-os web`, puerto `127.0.0.1:8000:8000`, `restart: unless-stopped`. Jinja2 con `autoescape=True` forzado en el entorno (test que lo verifica) y una cabecera `Content-Security-Policy: default-src 'self'`.
3. **Cambios** (`GET /cambios`): tabla cronológica descendente con filtros por formulario GET: planilla, pestaña, tipo de cambio, clave de fila (texto contiene), editor (identificador o "sin atribuir"; cuando T-005 mergee, la misma columna muestra el nombre leyendo `editor_profile` directamente, sin depender de sus vistas), fecha desde/hasta. Paginación de 100 por página. Arriba, resumen del período filtrado: cambios por día y por tipo. Cada fila muestra: detectado el (hora de lectura), ventana (`window_start` a `window_end`), planilla › pestaña › celda, bloque y clave de fila, tipo, valor anterior → nuevo, color anterior → nuevo (muestra el hexadecimal y un cuadrado del color), atribución ("sin atribuir" si es nula; "una de: ..." si es ambigua; la hora de la edición si es cierta). Detalle (`GET /cambios/{id}`) con todas las columnas, fórmulas anterior y nueva, y enlace a los snapshots por id.
4. **Problemas** (`GET /problemas`): tabla con filtros por tipo, estado derivado (abierto, resuelto, ignorado, reabierto) y planilla; columnas: tipo, planilla › pestaña, clave estable, visto por primera vez, visto por última vez, estado, dueño, última resolución (autor, motivo, fecha). Detalle (`GET /problemas/{id}`) con `details` y el historial de resoluciones. Sin botones: resolver se hace desde Claude Desktop (T-007).
5. **Fuentes** (`GET /fuentes`): las 20 planillas con sus pestañas, clase, `sheet_id`, activa, último snapshot (hora y duración de lectura desde `system_event`), cantidad de snapshots y de cambios en las últimas 24 horas; por planilla: versión de Drive conocida, última vuelta del worker que la chequeó, pedidos de lectura pendientes. Arriba, salud del sistema desde `system_event`: hora de la última vuelta del worker, intervalo máximo entre vueltas en las últimas 24 horas, último dump (hora y tamaño) con aviso visible si tiene más de 48 horas o no existe, tamaño de la base (`pg_database_size`), cantidad de `api_retry` del día. Botón **"leer ahora"** por planilla: `POST /fuentes/{source_id}/leer-ahora` inserta un `read_request` si no hay uno pendiente (misma regla que la CLI de T-003) y redirige a `/fuentes` con un mensaje; nunca escribe otra cosa.
6. **Raíz** (`GET /`) redirige a `/cambios`. Página de error simple para 404 y 500, sin volcar excepciones al navegador.
7. **Consultas en SQL explícito** con `psycopg`, parámetros siempre ligados (nunca concatenados), en un módulo `queries.py`; los filtros se validan contra listas cerradas (tipos de cambio, estados, ids numéricos). Las plantillas no reciben objetos de conexión.
8. **Tests:** con `TestClient` de FastAPI contra el PostgreSQL del Compose sembrado con fixtures sintéticos: cada pantalla responde 200; los filtros reducen resultados; un `cell_change` cuyo `new_value` es `<script>alert(1)</script>` se renderiza escapado (el texto aparece, la etiqueta no); `POST /leer-ahora` dos veces deja un solo pedido pendiente; un filtro con valor fuera de la lista responde 400 y no llega a la base; un `cell_change` con atribución nula muestra "sin atribuir".

**Descartado:** HTMX o refresco automático (ADR, cambio 7: vuelve cuando una pantalla necesite refrescarse sola); API JSON (ADR, cambio 1: nadie la consume); React (decidido en la propuesta 2.2); login (etapa D); pantalla "Clientes y aliases" (etapa B).

## Acceptance criteria

- [ ] `docker compose up -d` levanta `web`; `http://127.0.0.1:8000/` redirige a `/cambios`; el puerto no responde desde otra interfaz de la laptop (`docker compose port web 8000` muestra `127.0.0.1`).
- [ ] En `/cambios`, con los cambios reales ya registrados por el worker, filtrar por planilla "Facturación - Craftech Total" y tipo `color` muestra solo esas filas, con el cuadrado del color y los hexadecimales anterior y nuevo; el detalle de una fila muestra fórmula anterior y nueva cuando existen (captura de pantalla sin valores sensibles o sobre la planilla de prueba propia de Ariel).
- [ ] Un `cell_change` sembrado con `new_value = '<script>alert(1)</script>'` se ve como texto en `/cambios` y en su detalle; el HTML servido contiene `&lt;script&gt;` y no `<script>` (test automatizado y verificación en el navegador real).
- [ ] `/problemas` lista los `color_desconocido` detectados por T-004 con estado `abierto`; tras insertar una resolución `ignorado` por SQL, la misma fila pasa a `ignorado` y muestra autor y motivo; el filtro por estado funciona.
- [ ] `/fuentes` muestra las 20 planillas con pestañas y clase, el último snapshot por pestaña, la hora de la última vuelta del worker y el intervalo máximo de las últimas 24 horas; con el último dump borrado o viejo, aparece el aviso de más de 48 horas; con un dump reciente, no.
- [ ] Hacer clic en "leer ahora" para una planilla crea un `read_request` pendiente y muestra el mensaje; hacer clic de nuevo antes de que el worker lo atienda no crea otro; en la siguiente vuelta la planilla aparece releída en `/fuentes`.
- [ ] Un `GET /cambios?tipo=xxx` responde 400; `GET /cambios/999999` responde 404 con la página de error, sin traza.
- [ ] Con `cell_change` sin atribución, la columna dice "sin atribuir"; tras mergear T-005 y correr el worker, la misma pantalla muestra el identificador o el nombre asociado sin cambios de código en este ticket (verificación posterior al merge de ambos, anotada en `## Post-merge`).
- [ ] `grep -r "autoescape" app/craftech_os/web/` muestra el entorno con autoescape forzado y un test falla si se desactiva.
- [ ] `uv run pytest` y `ruff check` en limpio; ninguna plantilla ni test contiene datos reales.

## Out of scope

- Migraciones nuevas (ninguna; ver Context).
- Resolver problemas, anotar o asociar editores desde la web: todo eso es por Claude Desktop (T-007).
- Pantallas de etapa B (Facturas y cobros, Fundings, Clientes y aliases).
- Login, HTTPS, acceso desde otra máquina (etapa D).
- Gráficos, exportaciones, refresco automático.
