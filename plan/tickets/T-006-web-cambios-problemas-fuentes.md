---
id: T-006
title: Web local de solo visualización: pantallas Cambios, Problemas y Fuentes, con botón "leer ahora"
status: done
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

- [x] `docker compose up -d` levanta `web`; `http://127.0.0.1:8000/` redirige a `/cambios`; el puerto no responde desde otra interfaz de la laptop (`docker compose port web 8000` muestra `127.0.0.1`).
- [ ] En `/cambios`, con los cambios reales ya registrados por el worker, filtrar por planilla "Facturación - Craftech Total" y tipo `color` muestra solo esas filas, con el cuadrado del color y los hexadecimales anterior y nuevo; el detalle de una fila muestra fórmula anterior y nueva cuando existen (captura de pantalla sin valores sensibles o sobre la planilla de prueba propia de Ariel).
- [ ] Un `cell_change` sembrado con `new_value = '<script>alert(1)</script>'` se ve como texto en `/cambios` y en su detalle; el HTML servido contiene `&lt;script&gt;` y no `<script>` (test automatizado y verificación en el navegador real).
- [ ] `/problemas` lista los `color_desconocido` detectados por T-004 con estado `abierto`; tras insertar una resolución `ignorado` por SQL, la misma fila pasa a `ignorado` y muestra autor y motivo; el filtro por estado funciona.
- [x] `/fuentes` muestra las 20 planillas con pestañas y clase, el último snapshot por pestaña, la hora de la última vuelta del worker y el intervalo máximo de las últimas 24 horas; con el último dump borrado o viejo, aparece el aviso de más de 48 horas; con un dump reciente, no.
- [x] Hacer clic en "leer ahora" para una planilla crea un `read_request` pendiente y muestra el mensaje; hacer clic de nuevo antes de que el worker lo atienda no crea otro; en la siguiente vuelta la planilla aparece releída en `/fuentes`.
- [x] Un `GET /cambios?tipo=xxx` responde 400; `GET /cambios/999999` responde 404 con la página de error, sin traza.
- [ ] Con `cell_change` sin atribución, la columna dice "sin atribuir"; tras mergear T-005 y correr el worker, la misma pantalla muestra el identificador o el nombre asociado sin cambios de código en este ticket (verificación posterior al merge de ambos, anotada en `## Post-merge`).
- [x] `grep -r "autoescape" app/craftech_os/web/` muestra el entorno con autoescape forzado y un test falla si se desactiva.
- [x] `uv run pytest` y `ruff check` en limpio; ninguna plantilla ni test contiene datos reales.

## Out of scope

- Migraciones nuevas (ninguna; ver Context).
- Resolver problemas, anotar o asociar editores desde la web: todo eso es por Claude Desktop (T-007).
- Pantallas de etapa B (Facturas y cobros, Fundings, Clientes y aliases).
- Login, HTTPS, acceso desde otra máquina (etapa D).
- Gráficos, exportaciones, refresco automático.

## Implementation

- `app/craftech_os/web/app.py`: FastAPI con `docs_url`, `redoc_url` y `openapi_url` apagados. El entorno Jinja2 se crea a mano con `autoescape=True` y `StrictUndefined`, y se le pasa a `Jinja2Templates(env=...)`. Un middleware pone `Content-Security-Policy: default-src 'self'` en todas las respuestas. Los filtros se validan antes de abrir la conexión (`_id`, `_choice`, `_text`, `_date`, `_page`); un valor fuera de la lista da 400 "Filtro inválido: <nombre>". Las páginas de error (400, 404 y 500) usan `error.html`, y la de 500 muestra un mensaje genérico: la traza queda solo en el log del contenedor.
- `app/craftech_os/web/queries.py`: el SQL de cada pantalla, explícito y siempre con parámetros enlazados. El texto de "clave" usa `ILIKE` con `%`, `_` y `\` escapados. El editor "sin atribuir" corresponde a un arreglo de editores vacío o nulo. "Hasta" es inclusivo: se compara con el día siguiente. Los días se cuentan en la zona horaria de Buenos Aires, porque la conexión usa `TimeZone`. `editor_names` lee `editor_profile` solo si la tabla existe (`to_regclass`); por cada `actor_id` gana la fila más nueva. `request_read` aplica la misma regla que `read-now`: inserta con `ON CONFLICT DO NOTHING` sobre el índice de pedido pendiente.
- Plantillas en `web/templates/` y un único `web/static/style.css`, sin JavaScript ni estilos inline (la CSP los bloquearía). El cuadrado de color es un `<input type="color" disabled>` y se muestra solo si el valor es `#rrggbb`.
- `/cambios` acepta además `?snapshot=<id>`, que filtra los cambios hacia o desde ese snapshot. Lo usan los enlaces "Snapshot anterior" y "Snapshot nuevo" del detalle.
- Salud en `/fuentes`:
  - "Última vuelta del worker que la chequeó" es el último `worker_tick` si la planilla tiene `drive_id`, porque cada vuelta chequea todas.
  - La versión de Drive conocida sale del último `source_read` con `drive_version`.
  - Los reintentos cuentan solo `api_retry` de hoy.
  - El aviso de dump aparece si no hay ningún evento `dump` o si el último tiene más de 48 horas.
- `cli.py`: nuevo comando `craftech-os web [--host 127.0.0.1] [--port 8000]`, que corre uvicorn. En Compose, el servicio `web` pasa `--host 0.0.0.0` dentro del contenedor y publica solo `127.0.0.1:8000:8000`.
- Dependencias: `fastapi`, `jinja2` y `uvicorn`, más `httpx` solo para desarrollo, porque lo usa `TestClient`. No agregué `python-multipart`: el POST de "leer ahora" no tiene campos de formulario.
- README: nueva sección "Web local".

## Test plan

Automatizados (`app/tests/test_web.py`, 16 tests, con datos sintéticos en la base `_test`):

1. Todas las pantallas responden 200 con la CSP, y `/` redirige con 303 a `/cambios`.
2. Un `cell_change` con `new_value = '<script>alert(1)</script>'` sale como `&lt;script&gt;` y sin `<script` en `/cambios` y en su detalle; el detalle muestra las fórmulas anterior y nueva.
3. Los filtros por planilla, tipo, clave, editor, "sin atribuir" y fecha reducen los resultados. El filtro de color muestra el cuadrado y los dos hexadecimales.
4. Atribución:
   - Un cambio sin atribución dice "sin atribuir".
   - Al crear `editor_profile`, se muestra el nombre más nuevo de cada editor.
5. Filtros inválidos (`tipo=xxx`, `planilla=1;DROP`, `desde=ayer`, `pagina=-1`, `estado=cerrado`, `resultado=otro`) dan 400 sin llegar a la base: la conexión está reemplazada por una que falla.
6. 404 con página de error y sin traza en `/cambios/999999`, `/problemas/999999` y en una ruta inexistente. Un POST a una fuente inexistente también da 404. Un error interno da 500 sin el detalle.
7. En `/problemas`, un problema `abierto` pasa a `ignorado` tras insertar la resolución por SQL, y muestra autor y motivo. El filtro por estado funciona.
8. Dos POST de "leer ahora" dejan un solo `read_request` pendiente y muestran los dos mensajes.
9. Dump en `/fuentes`:
   - Sin dump o con uno de hace 3 días, aparece el aviso de más de 48 horas.
   - Con uno reciente, no aparece y se ve el tamaño.
   - El intervalo máximo entre vueltas se muestra sin microsegundos.

Para QA en el navegador real (`docker compose -f infra/docker-compose.yml up -d`, <http://127.0.0.1:8000/>):

- Sembrar en la base real un `cell_change` con `<script>alert(1)</script>` en una pestaña de prueba, verlo como texto, y borrarlo después.
- Filtrar por planilla y tipo `color` cuando el worker haya registrado cambios reales. Hoy la base real tiene 0 `cell_change` y 0 `issue`.
- Ver que `docker compose port web 8000` muestre `127.0.0.1:8000`, y que desde la IP de la red local no responda.

**Blast radius:** el código nuevo está aislado en `app/craftech_os/web/`. Lo compartido es:

- `cli.py`: un subcomando más; el resto no cambia.
- `infra/docker-compose.yml`: un servicio nuevo. `postgres` y `worker` no cambian.
- `pyproject.toml` y `uv.lock`: tres dependencias nuevas. La imagen del worker también las instala, porque usan el mismo Dockerfile.
- `README.md`.

La web solo escribe en `read_request`.

## Post-merge

- En `main`: `docker compose -f infra/docker-compose.yml up -d --build web`. No hay migraciones ni variables de entorno nuevas: usa `APP_DB_PASSWORD` y `POSTGRES_DB` de `infra/.env`.
- Después de mergear T-005 y de que el worker atribuya cambios: abrir `/cambios` y verificar que la columna Atribución muestre el identificador o el nombre de `editor_profile`, sin cambios de código (criterio 8, segunda parte).
- Con cambios `color` reales en "Facturación - Craftech Total": verificar el criterio 2 con una captura sin valores sensibles.

### Verificado en esta rama (smoke con la base real, sin capturas ni valores)

- El contenedor `web` publica solo `127.0.0.1:8000`; desde la IP de la red local no responde. `/` responde 303 hacia `/cambios`.
- `/fuentes` muestra "20 planillas.", la última vuelta, el intervalo máximo (0:05:16) y el último dump, que es reciente, sin aviso.
- "Leer ahora" sobre la fuente 1: el primer POST dio `created` y el segundo `pending`, con un solo `read_request` pendiente. El worker lo atendió en la vuelta siguiente (`served_at` 03:35:56 UTC, log `read 1`). Luego `/fuentes` mostró "Pedido de lectura pendiente: no". Ese `read_request` real queda en la base, atendido.
- No verificado con datos reales: los criterios 2, 3 (navegador), 4 y 8 (segunda parte). La base real tiene 0 `cell_change` y 0 `issue`; esos casos quedan cubiertos por los tests sintéticos y por `## Post-merge`.
