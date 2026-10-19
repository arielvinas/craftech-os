---
id: T-005
title: Actividad de Drive: importación desde marzo de 2026, perfiles de editor, atribución de cada cambio y anotaciones
status: done
priority: high
lane: core
depends_on: [T-004]
effort: M
milestone: A
branch: arielvinas/t-005
---

## Context

Unidad 4 del corte del ADR (`plan/adr/ADR-001-espejo-de-planillas-en-postgres.md`, cambio 4 y riesgo "varias personas editan en el mismo intervalo"). Origen de producto: `docs/03-proposal.md` sección 4.4 (quién y cuándo), decisión 2 de Ariel ("Ya la habilité", Drive Activity API) y decisión 4 (nada instalado en las planillas: lo que no se pueda atribuir por celda se muestra como conjunto y ventana, nunca se inventa). Regla **R4** (ratificada): el cobro es la fecha en que Emi pinta el verde; mientras se lea la planilla, la fecha de detección. Con la actividad de Drive, la fecha pasa a ser la de la edición cuando hay un solo editor posible; resuelve "se pintó el viernes, se leyó el lunes".

Hechos verificados el 18-oct-2026 (anexo B de la propuesta): la Drive Activity API v2 funciona con permiso de Lector; para "FUNDINGS - Log de status [OFICIAL]" devuelve 1.141 eventos, el más viejo del 16 de marzo de 2026, cada uno con marca de tiempo, tipo (edición, cambio de permiso) y actor. Los actores vienen como identificadores de perfil de Google (`people/<id>`, 8 distintos en esa planilla), no como nombres; no coinciden con los identificadores de permisos de Drive; la People API no está habilitada y no se habilita (la propuesta lo descarta: exigiría permisos sobre el directorio). Ariel asocia cada identificador a una persona desde Claude Desktop (T-007); hasta entonces se muestra "editor sin identificar #N".

Verificado en el repo tras T-004: `cell_change` tiene `window_start`, `window_end` y las columnas de atribución nulas (`attributed_editor_ids`, `attribution_certainty`, `attributed_at`). Este ticket las llena y **no altera `cell_change`** (T-006 corre en paralelo sobre ese esquema).

## Scope

**Dónde vive:** `app/craftech_os/ingest/drive_activity.py`, `app/craftech_os/attribution.py`, migración `0005_drive_activity.sql`, worker, CLI.

1. **Alcance nuevo** de la service account: `drive.activity.readonly` (solo lectura, ya verificado). Sin dependencias nuevas: el mismo `google-api-python-client` construye el cliente `driveactivity` v2.
2. **Migración `0005_drive_activity.sql`:**
   - `drive_activity`: id, source, `activity_at`, `actor_id` (texto `people/...`), `action_type` (edición, cambio de permiso, renombre, etc., tal como lo clasifica Google), `raw` jsonb (la actividad tal como vino, sin recortar), `content_hash` único para no duplicar al reimportar. Solo inserción.
   - `editor_profile`: id, `actor_id`, `person_name`, `author`, `reason`, `created_at`. Solo inserción; la asociación vigente es la última fila por `actor_id`. Vista `v_editor` que da, por `actor_id`, el nombre asociado o "editor sin identificar #N" con N estable por orden del menor `id` de `drive_activity` de cada actor (fijo desde la primera inserción; un backfill posterior de otra planilla no renumera).
   - `annotation`: id, `entity_type` (`source`, `source_tab`, `cell_change`, `issue`), `entity_key` (texto: id de la entidad), `body`, `author`, `reason`, `created_at`. Solo inserción. Es la tabla que llena la herramienta "anotar" del servidor MCP (T-007); acá se crea y se prueba por SQL.
   - `COMMENT ON` en español en todo.
3. **Importación hacia atrás:** `craftech-os drive import [--source <título>]` recorre `activity.query` con `itemName = items/<drive_id>` de cada planilla, paginando hasta agotar (Google devuelve hasta marzo de 2026), e inserta cada actividad una sola vez. Reintentos con espera creciente y `system_event` como en T-002. Reanudable.
4. **Importación incremental en el worker:** en cada vuelta en la que una planilla cambió de versión (y, al menos una vez por hora, para todas), consulta la actividad desde la última `activity_at` conocida menos 10 minutos de margen e inserta lo nuevo.
5. **Atribución:** para cada `cell_change` sin `attribution_certainty`, se toman las actividades de edición de esa planilla con `activity_at` dentro de `(window_start, window_end]`. Un solo actor distinto → `cierta`, `attributed_editor_ids = [actor]`, `attributed_at` = momento de su última edición en la ventana. Varios actores → `una_de` con la lista y `attributed_at` nulo. Ninguno → `sin_datos`. Corre después de cada diff en el worker y también sobre lo pendiente al final de `drive import`. Nunca escribe un nombre, solo identificadores; el nombre se resuelve al mostrar vía `v_editor`.
6. **CLI de apoyo:** `craftech-os editors` lista los `actor_id` vistos, con cuántas ediciones, en qué planillas y en qué franjas horarias, y el nombre asociado si lo hay. Es la información que Ariel usa para identificar a cada editor desde Claude Desktop en T-007. Solo lectura; la escritura de `editor_profile` es exclusiva del servidor MCP (propuesta 4.6: una sola superficie de escritura humana).
7. **Métrica del ADR:** porcentaje de cambios con atribución `cierta`, disponible como vista `v_attribution_stats` (por planilla y por día) para la pantalla Fuentes.
8. **Tests:** unitarios de la atribución con actividades y cambios sintéticos (un editor → cierta con la hora correcta; dos → una_de; ninguno → sin_datos; edición fuera de la ventana no cuenta; un cambio de permiso no es edición); de la importación con respuestas paginadas simuladas (no duplica al reimportar); de la numeración estable de "editor sin identificar #N". Integración contra PostgreSQL para las vistas. Identificadores de actor inventados.

**Descartado:** People API para resolver nombres (propuesta 4.4); Apps Script para autoría por celda (decisión 4 de Ariel, descartado para siempre); adivinar el autor por horario o por planilla habitual (nunca se inventa un "quién").

## Acceptance criteria

- [ ] `craftech-os drive import` sobre las 20 planillas reales termina y `drive_activity` tiene actividad desde marzo de 2026 para "FUNDINGS - Log de status [OFICIAL]" (del orden de 1.100 filas; el número exacto va a `## Implementation`); correrlo de nuevo no agrega filas.
- [ ] `SELECT count(DISTINCT actor_id)` para esa planilla da del orden de 8 y `v_editor` los muestra como "editor sin identificar #1" a "#8", con la misma numeración en dos consultas consecutivas.
- [ ] En la planilla de prueba propia de Ariel: una edición suya seguida de la vuelta del worker deja los `cell_change` resultantes con `attribution_certainty = 'cierta'`, `attributed_editor_ids` con su identificador y `attributed_at` igual a la hora de la edición según Drive (no a la hora de la lectura).
- [ ] En test, dos actores en la misma ventana dan `una_de` con ambos identificadores y `attributed_at` nulo; ninguno da `sin_datos`.
- [ ] Insertar una fila en `editor_profile` para un `actor_id` hace que `v_editor` muestre el nombre; insertar una segunda fila para el mismo actor hace que gane la última.
- [ ] Insertar una `annotation` sobre un `issue` y sobre un `cell_change` funciona con los cuatro `entity_type` y rechaza uno fuera de la lista (restricción en la base, no solo en Python).
- [ ] `v_attribution_stats` devuelve, por planilla y día, total de cambios y porcentaje `cierta`.
- [ ] `cell_change` no tiene columnas nuevas ni cambiadas respecto de T-004 (`\d cell_change` igual salvo datos).
- [ ] Ningún log ni `system_event` contiene nombres de personas ni valores de celdas; los `actor_id` sí pueden aparecer en logs (son identificadores opacos).
- [ ] `uv run pytest` y `ruff check` en limpio; ningún test llama a Google.

## Out of scope

- Herramienta para asociar editores a personas y para anotar (T-007): acá solo la tabla y la vista.
- Mostrar la atribución en la web (T-006 la muestra cuando este ticket mergee; mientras, "sin atribuir").
- Autoría por celda (imposible sin script en la planilla; descartado).
- Cambiar la fecha de un cobro o de cualquier hecho (etapa B).
- Alertas o resumen de "quién tocó qué" por Slack (etapa D).

## Decisions

- 2026-10-19 — **FUNDINGS tiene 13 actores, no ~8: ¿a quiénes numerar como 'editor sin identificar #N'?** → (a) Numerar a TODOS los actores de la actividad, incluidos los que solo cambiaron permisos. Anotar en el ticket el número final medido en la importación real (el criterio de '~8' se ajusta a lo medido).
- 2026-10-19 — **Actividades de cuentas eliminadas (deletedUser, sin identificador)** → (a) Guardarlas con un único actor_id = 'deletedUser', que cuenta como un actor más y aparece en v_editor como 'usuario eliminado'; si es el único de la ventana, sale cierta con ese identificador.
- 2026-10-19 — **Ventana de atribución: Drive Activity agrupa ediciones en tandas ~3 min y les pone hora 1,5–2,5 min después de la modificación; la ventana (window_start, window_end] atribuye mal** → (a) Ensanchar: contar actividad en (window_start, window_end + 5 min]; atribuir solo cuando ya se leyó la actividad posterior a window_end + 5 min. Nunca da cierta a la persona equivocada.

## Implementation

- **Migración `0005_drive_activity.sql`:** tablas `drive_activity` (`content_hash` único, índice por planilla y momento), `editor_profile` y `annotation` (con `CHECK` sobre los cuatro `entity_type`); vistas `v_editor` y `v_attribution_stats`; `COMMENT ON` en español en todo. `cell_change` no cambia de columnas: solo se reescriben los comentarios de `window_end`, `attributed_editor_ids` y `attributed_at` para reflejar la ventana ensanchada.
- **`ingest/google.py`:** se agrega el alcance `drive.activity.readonly`, el cliente `driveactivity` v2 (misma dependencia) y `activities(file_id, on_retry, since)`, que pagina de a 100 con los mismos reintentos y eventos `api_retry` de T-002.
- **`ingest/drive_activity.py`:** `parse` extrae el actor (`people/...`, `deletedUser` para cualquier cuenta eliminada, o el tipo de actor sin identificador: `anonymous`, `system`), el momento y el tipo de acción, y guarda la actividad entera en `raw` con un SHA-256 de su JSON canónico. `fetch` lee todas las páginas y recién después inserta, en una sola transacción y de la más vieja a la más nueva, para que la numeración siga el orden real de aparición. Si falla a mitad de camino no guarda nada (evento `activity_failed`) y la próxima vez pide el mismo rango: así queda reanudable sin estado parcial. Una lectura completa deja `activity_read` con la cantidad insertada, hasta cuándo se leyó (`through`) y la última actividad conocida (`latest`); la siguiente pide desde `latest` menos 10 minutos.
- **`attribution.py`:** una sola sentencia SQL atribuye los cambios pendientes de una planilla cuya ventana más cinco minutos ya quedó cubierta por la lectura (`window_end + 5 min < through`). Cuenta solo las acciones `edit` en `(window_start, window_end + 5 min]`: un actor distinto da `cierta` con `attributed_at` en su última edición, varios dan `una_de`, ninguno da `sin_datos`. Deja un evento `attributed` con las cantidades. Los cambios de pestaña no tienen ventana y quedan sin atribuir.
- **Worker:** al final de cada vuelta, para cada planilla leída en esa vuelta, con cambios esperando atribución cuyo margen ya pasó, o sin actividad leída hace una hora, trae la actividad y atribuye. Un error de la API en una planilla no frena la vuelta. La línea impresa por vuelta no cambia.
- **CLI:** `drive import [--source]` (imprime por planilla las actividades nuevas y los cambios atribuidos; termina con error si alguna lectura falló) y `editors` (cada actor con su etiqueta de `v_editor`, ediciones, planillas, franja horaria en UTC y primera y última fecha). Solo lectura.
- **Web:** `editor_names` ya no pregunta si existe `editor_profile`.
- **README:** sección "Quién hizo cada cambio".

**Medido en la importación real** (19-oct-2026, contra una base descartable, `craftech_os_test`; la base real queda para después del merge porque las migraciones se verifican por hash):

- 20 planillas, 63.150 actividades, en 6 min 21 s. Una segunda corrida agrega 0 y tarda 24 s.
- "FUNDINGS - Log de status [OFICIAL]": **1.154 actividades**, del 16-mar-2026 al 19-oct-2026, con **13 actores distintos** (12 `people/...` más `deletedUser`, con 84 actividades). Según la decisión del 19-oct, se numeran todos.
- En total hay 23 actores. Entre ellos están `anonymous` (14 `dlpChange`) y `system` (7 `permissionChange`). No tienen ediciones, así que no influyen en la atribución, pero reciben número como cualquier otro actor.
- Como la numeración es global, los actores de FUNDINGS no son #1 a #13 consecutivos: van #1–#3 y #7–#15, más "usuario eliminado". `v_editor` dio exactamente lo mismo en dos consultas seguidas.
- Tipos de acción: 63.065 `edit`, 25 `rename`, 20 `create`, 14 `permissionChange`, 14 `dlpChange`, 11 `move` y 1 `delete`.

## Test plan

- `app/tests/test_drive_activity.py`, contra PostgreSQL y con Google simulado:
  - Importación paginada y reimportación sin duplicados.
  - Una sola planilla con `--source`.
  - Lectura incremental desde la última actividad menos 10 minutos.
  - Importación interrumpida: no guarda nada y la siguiente lee todo.
  - Reintentos por cuota.
  - Ningún evento ni salida contiene nombres de Google.
- Atribución:
  - Un editor da `cierta` con la hora de su última edición.
  - Dos editores dan `una_de` con `attributed_at` nulo; ninguno da `sin_datos`.
  - `deletedUser` solo da `cierta`.
  - Un cambio de permiso no cuenta.
  - Un cambio espera hasta que se haya leído la actividad posterior a su margen.
  - Solo mira la actividad de su planilla.
  - `drive import` atribuye lo pendiente al final.
- Vistas y tablas:
  - Las columnas de `cell_change` no cambian.
  - Numeración estable por primera aparición, incluso con un backfill posterior.
  - La última fila de `editor_profile` manda.
  - `annotation` acepta los cuatro tipos y la base rechaza otro.
  - `v_attribution_stats` por planilla y día.
  - Salida de `editors`.
- Worker:
  - Trae la actividad y atribuye una vez pasado el margen.
  - Una falla de la API no frena la vuelta.
- Prueba de mutación:
  - Si un solo editor da `una_de`, fallan 6 tests.
  - Sin el margen de 5 minutos, fallan 3.
- Para QA:
  - Criterio 3: una edición real de Ariel en su planilla de prueba. No lo puede verificar el agente: requiere editar una planilla y el agente nunca escribe en Sheets.
  - Pantalla Cambios de la web: sigue mostrando el `actor_id` cuando no hay nombre (fuera de alcance).
- Alcance del cambio:
  - `ingest/google.py` (cliente y alcances nuevos).
  - La vuelta del worker (una llamada a la API por planilla y por hora, más las de las planillas leídas).
  - `test_import.FakeGoogle`.
  - `web/queries.editor_names`.

## Post-merge

1. Reconstruir las imágenes: `docker compose -f infra/docker-compose.yml build`.
2. Migrar la base real: `docker compose -f infra/docker-compose.yml run --rm app craftech-os migrate` (aplica `0005_drive_activity.sql`).
3. Traer la historia y atribuir lo pendiente: `docker compose -f infra/docker-compose.yml run --rm app craftech-os drive import`. Tarda unos 6–7 minutos y trae unas 63.000 actividades.
4. Reiniciar el worker: `docker compose -f infra/docker-compose.yml up -d`.
5. Verificar el criterio 3: editar una celda de la planilla de prueba propia y, después de la vuelta del worker, revisar que el `cell_change` quedó `cierta` con el `actor_id` y la hora de Drive.
