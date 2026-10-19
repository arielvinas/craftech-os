# QA T-003 — Ronda 1

**Verdict: PASS**
**Branch:** arielvinas/t-003 @ e20432f
**Gates:** ruff check ✓ · ruff format --check ✓ · pytest ✓ (98 passed, 0 skipped, con `TEST_DATABASE_URL` apuntando a un PostgreSQL 16 propio de QA) · build de las imágenes `app` y `worker` ✓
**Criteria:** 7/9 verificados; los criterios 2 y 3 (editar la planilla de prueba de Ariel) quedan sin verificar de punta a punta, cubiertos con tests y mutantes. Ver "No verificado": no bloquean el veredicto.
**Mutation:** 18 mutantes sobre `worker.py`, `importer.py` y `0003_read_request.sql`. Los 18 hacen fallar `app/tests/test_worker.py` corrido solo, así que los detectan los tests nuevos y no los que ya existían.

## Cómo se probó

- Todo en un proyecto de Compose aparte (`-p qa-t003`, con volumen propio, sin puerto publicado y un `.env` temporal), sin tocar la base de desarrollo `craftech-os` ni la base `_test` compartida. Los tests de integración corrieron contra otro contenedor `postgres:16` descartable, en `127.0.0.1:55432`. Al final borré todo: contenedores, volúmenes, imágenes `qa-t003-*` y el `infra/.env` temporal.
- No leí ninguna planilla de Finanzas ni escribí nada en Google. La única llamada real a Google fue un `files.get` con la cuenta de servicio de solo lectura, sobre un `drive_id` que no existe (`qa-nonexistent-file-id`).

## Criterios

1. ✓ `docker compose up -d` levanta solo `postgres` y `worker`; `app` quedó en el perfil `cli`. Logs durante 20 minutos (hora de Buenos Aires):
   ```
   22:34:45 tick: checked 0, read 0, stored 0, 1 ms
   22:34:46 dumped craftech-os-2026-10-18.dump
   22:39:45 tick: checked 0 …
   22:44:45 tick: checked 0 …
   22:49:45 tick: checked 1, read 0, stored 0, 513 ms
   ```
   Las vueltas salen cada 300,01 segundos. Los logs no muestran valores de celdas, y `test_no_worker_event_or_output_contains_cell_values` lo comprueba con un marcador.
2. ⚠ No verificado de punta a punta (ver abajo). Lo cubren `test_a_new_version_waits_for_two_quiet_minutes_and_stores_only_changed_tabs` y `test_an_edit_during_the_wait_restarts_the_quiet_window`, que comprueban `version_changed` → `calm_wait` de 120 segundos → que solo se lea `Resumen` → un solo snapshot nuevo.
3. ⚠ No verificado de punta a punta. `test_first_tick_reads_only_carga_and_derivada_tabs` comprueba que no se lee la pestaña `HISTORICA` ("Nueva"). El filtro es una lista de clases permitidas (`READ_CLASSES`), así que `IGNORAR`, `A_CONFIRMAR` y `SIN_CLASIFICAR` quedan afuera por construcción. El mutante "no class filter" lo detecta un test. `import --source` sigue leyendo todas las clases: `classes=None` y los tests de T-002 en verde.
4. ✓ Real, en Compose:
   - `read-now "QA Falsa"` dos veces → "read requested" y después "already pending", con una sola fila pendiente.
   - En la vuelta siguiente, Google devolvió 404, quedó `source_failed {"status": 404}` y el pedido siguió pendiente, que es lo correcto.
   - El camino que cierra el pedido (`served_at` + `snapshot_count` sin cambio de versión) lo cubre `test_read_now_is_idempotent_and_served_without_waiting`.
   - `read-now` sale con 1 para "Nope", para la planilla sin `drive_id` y para `''`, `<script>` y `'; DROP TABLE source;--`. Las consultas usan parámetros, y la tabla `source` quedó intacta.
5. ✓ `test_the_wait_is_capped_at_ten_minutes_and_reads_anyway` deja `{"waited_s": 600, "capped": true}`. Si se saca el tope, el test se cuelga: lo detecta el timeout del harness.
6. ✓ `test_a_quota_error_on_the_version_check_is_retried_and_the_tick_ends` produce un `api_retry` con 429. Con `test_a_source_that_keeps_failing_does_not_stop_the_others`, la vuelta sigue con las demás planillas y la siguiente lee la planilla que había fallado.
7. ✓ Real, en Compose:
   - Con 15 `craftech-os-2026-09-*.dump`, el `.dump` de hoy y un `keep-me.txt`, `craftech-os dump` dejó 14 `.dump` (borró 09-01 y 09-02) y no tocó el `.txt`.
   - `pg_restore --list` lista 18 objetos `TABLE`.
   - `system_event` tiene `dump {"file": …, "size_bytes": 29688}`.
   - Un dump a una carpeta no escribible (`--dir /proc`) deja `dump_failed` con la última línea de `pg_dump` y sale con 1; no hay contraseña en el mensaje.
8. ✓ Lo cubre `test_a_tick_killed_mid_read_leaves_no_partial_or_duplicated_snapshots`: no queda ningún `content_hash` duplicado por pestaña. La versión se registra solo si no falló ninguna pestaña, y el mutante "version recorded on failure" lo detecta un test. Prueba real del reinicio:
   - Apagué `postgres` con el worker corriendo.
   - El worker salió con código 1 ("terminating connection due to administrator command"), Compose lo reinició 2 veces, y al volver la base siguió con sus vueltas (`22:54:47 tick: checked 1`).
   - No repitió el dump del día.
9. ✓ `uv run pytest` y `ruff check` en limpio; los tests usan un Google y un reloj falsos y no necesitan red.

## Findings

### F1 [minor] `pg_dump` recibe la URL con la contraseña como argumento
- **Repro:** mientras corre el dump, `ps` dentro del contenedor `worker` muestra `pg_dump … --dbname postgresql://craftech_app:<pw>@postgres/...`.
- **Expected:** la contraseña no queda a la vista de otros procesos. **Actual:** queda, solo dentro del contenedor y mientras dura el dump; el mensaje de error sí se cuidó con `DumpFailed`.
- **Alternativa más simple:** pasarla por `PGPASSWORD` en el `env` de `subprocess.run`, o usar `libpq` con `PGHOST/PGUSER/...`. El riesgo es bajo, porque en el contenedor solo corre ese proceso; no bloquea.

### F2 [nit] La retención ordena por nombre cualquier `craftech-os-*.dump`
- **Repro:** un archivo `craftech-os-manual.dump` en la carpeta ordena después de las fechas (`m` > `2`) y nunca se borra; ocupa uno de los 14 lugares y deja afuera un dump real.
- **Fix posible:** usar un patrón con fecha, `craftech-os-????-??-??.dump`.

### F3 [nit] Un pedido pendiente de una planilla que pierde su `drive_id` queda pendiente para siempre
- **Repro:** `read-now X` y después `UPDATE source SET drive_id = NULL` (por ejemplo, si se recarga `sources.yaml`). El worker filtra `drive_id IS NOT NULL` y ese pedido no se atiende ni se descarta. No tiene impacto hoy; T-006 lo va a mostrar como "pendiente".

### Observación (no es un finding)
Las esperas de calma son secuenciales dentro de una vuelta, como pide el ticket. Si una planilla anterior llega al tope de 10 minutos, la vuelta pasa de 5 minutos, y el plazo de 8 minutos del criterio 2 puede no cumplirse para las planillas que siguen. Con el uso esperado (pocas planillas editadas a la vez) no pasa.

## No verificado

- **Criterios 2 y 3, de punta a punta con la planilla de prueba de Ariel.** No hay un `sources.yaml` de prueba en esta máquina, y la regla del proyecto prohíbe que un agente escriba en Google Sheets, así que ningún agente puede hacer esta prueba: es manual de Ariel por diseño. **Mi juicio: el hueco es aceptable y no bloquea el veredicto.** Las razones:
  - La lógica que deciden estos criterios está cubierta por tests que fallan ante cada mutante relevante: el filtro de clases, la ventana de 2 minutos, el reinicio de la ventana con una edición nueva, el tope y la deduplicación por hash.
  - Lo que queda sin probar es solo el comportamiento real de Drive: que `version` suba con cada edición de celda y que `modifiedTime` se actualice enseguida. Es comportamiento documentado de la API, y `files.get` con esos campos ya se midió en el anexo B de la propuesta.
  - El plazo de 8 minutos cierra en el peor caso normal: hasta 5 minutos hasta la próxima vuelta, más hasta 2 de calma, más la lectura.

  **Prueba manual pendiente para Ariel** (pasos 2 y 3 del `## Test plan` del ticket), con una planilla propia y un `sources.yaml` de prueba, nunca con las de Finanzas. Si falla, se abre un ticket de bug.
- La alerta de "más de 48 horas sin dump" es de T-006.

## Split-outs sugeridos (fuera del alcance)

- Ninguno severo. F2 y F3 se pueden anotar en `plan/improvements.md` si el runner lo cree útil.

Ronda inusualmente limpia. Hice una segunda pasada adversarial sobre la base real (títulos maliciosos, un 404 real, base caída con reinicio, carpeta sin permiso de escritura) y el resultado se sostuvo.
