---
id: T-005
title: Actividad de Drive: importación desde marzo de 2026, perfiles de editor, atribución de cada cambio y anotaciones
status: todo
priority: high
lane: core
depends_on: [T-004]
effort: M
milestone: A
branch:
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
