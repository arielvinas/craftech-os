# QA T-002 — Ronda 1

**Verdict: FAIL**
**Branch:** arielvinas/t-002 @ f0c5dfa
**Gates:** typecheck — (el repo no tiene typecheck configurado) · lint ✓ (`ruff check` y `ruff format --check`) · tests ✓ (70 pasan, ninguno salteado, con `TEST_DATABASE_URL` apuntando a la base `_test`) · build ✓ (`docker compose build app`)
**Criteria:** 8/9 verificados; el criterio de la segunda corrida no se cumple en vivo (F1)
**Mutation:** 18 mutantes a mano sobre importer, google, document, sources y cli → los 18 ponen la suite en rojo ✓ (harness en `/tmp/qa-t002/mutants.py`; falla si un archivo o patrón no existe)

No hay interfaz web en este ticket: no corresponde navegador ni capturas. Todas las consultas en vivo se hicieron sobre la base de desarrollo con conteos; no se mostró ningún valor de celda.

## Findings

### F1 [blocker] Una segunda importación sin cambios en Google agrega snapshots en 4 pestañas
- **Criterio:** "Correr `craftech-os import` de nuevo sin que cambie nada en Google no agrega filas a `snapshot` (mismo hash), y sí agrega `system_event` de lectura."
- **Repro:** `docker compose -f infra/docker-compose.yml run --rm app craftech-os import --source "CASH FLOW MENSUAL"` (tercera lectura de esa planilla, hecha por QA el 18-oct-2026).
- **Expected:** `0 stored, 13 unchanged`. **Actual:** `4 stored, 9 unchanged, 0 failed`. Las mismas cuatro pestañas que reportó implement: "CASH FLOW ARG", "Cash Flow - c/ pagos proyectados", "CASH FLOW USA" y "Resumen mensual Cash Flow ARG-USA". Cada una tiene ahora 3 snapshots, los tres con la misma versión de Drive (41562) y el mismo `modifiedTime`.
- **Causa, medida por SQL entre los dos últimos snapshots de cada pestaña:** solo cambia `value` (valor efectivo). El texto formateado, la fórmula y el color de fondo no cambian en ninguna celda, y no aparece ni desaparece ninguna celda. La diferencia numérica máxima es de 6e-8, y cambian entre 70 y 1.203 celdas por pestaña. Es ruido de punto flotante del recálculo de Google, y se repite en cada lectura.
- **Por qué blocker:** el criterio está escrito sin excepción y se cumple para 338 de 342 pestañas. Implement no lo tildó y lo pasó a T-004, pero el `## Out of scope` del ticket no excluye este criterio, y la regla de QA es FAIL con cualquier criterio sin cumplir. Además, cada corrida suma 4 filas nuevas a `snapshot` (unas 1.500 celdas por corrida) sin que nadie haya tocado la planilla.
- **Cómo destrabarlo:** es una decisión de producto, no un arreglo técnico obvio. Opciones, de la más simple a la más compleja:
  1. Ariel ajusta el criterio. Por ejemplo: "no agrega filas salvo en las pestañas cuyo recálculo de Google cambia valores efectivos sin cambiar la versión de Drive; se resuelve en T-003/T-004". Con esto el ticket pasa sin tocar código.
  2. No guardar un snapshot nuevo si la versión de Drive y el `modifiedTime` son iguales a los del último snapshot de la pestaña. Es la misma regla que T-003 va a usar para no releer, no interpreta ningún valor y es un cambio de pocas líneas en `read_tab`. La contra: se pierde el ruido del recálculo, que hoy igual no tiene valor para nadie.
  3. Normalizar los números antes del hash (por ejemplo, redondearlos). Lo desaconsejo: interpreta el contenido, y el ticket dice que el lector guarda lo que vino.

### F2 [minor] Si a la respuesta de Drive le falta `version` o `modifiedTime`, se corta toda la importación
- **Dónde:** `app/craftech_os/ingest/importer.py`, en `read_tab`. `int(version["version"])` y `version["modifiedTime"]` se evalúan afuera del `try` que marca la pestaña como fallida.
- **Escenario:** si `files.get` devuelve un cuerpo sin esas claves, sale un `KeyError` que no se captura. El comando muere con traceback y las planillas que faltaban no se leen. Lo normal es que Google siempre mande esas claves, así que el riesgo es bajo. Pero contradice la decisión del propio ticket: "un error al leer una pestaña la marca fallida y la corrida sigue". Probado leyendo el código, no en vivo.
- **Más simple:** validar las dos claves dentro del `try`, o capturar `KeyError` junto con `ValueError` y `TypeError`.

### F3 [nit] Se importan `httplib2` y `google_auth_httplib2` sin declararlos en `pyproject.toml`
- `google.py` e `importer.py` los importan directamente, pero solo llegan como dependencias transitivas de `google-api-python-client`. Hoy funciona (el `uv.lock` los fija). Si la librería deja de traerlos, el import se rompe sin aviso. Se arregla declarándolos.

## Criterios, uno por uno

1. ✓ `config/sources.yaml` tiene 20 `drive_id`. `git diff main...HEAD -- config/sources.yaml` muestra 20 líneas agregadas, todas `drive_id: "…"`, y ninguna otra. En la base, ninguna fila de `source` tiene `drive_id` nulo. `resolve` con duplicados y en modo parcial está cubierto por tests, con los mutantes muertos.
2. ✓ Hay 342 pestañas activas, todas con al menos un snapshot. Ningún snapshot tiene nulos en `drive_version`, `drive_modified_at`, `content_hash` ni `content`, y todos tienen `origin = 'lectura'`. Tras la primera corrida hay uno por pestaña; los duplicados de hoy son solo los de F1. Entran también las pestañas ocultas: 192 de los últimos snapshots tienen `hidden = true`.
3. ✗ Ver F1. Se cumple que la segunda corrida agrega `tab_read`: hay 754 en total, uno por pestaña en cada corrida.
4. ✓ En "Pagos" de "Facturación - Craftech Total" hay 2.176 celdas, todas con fondo `#rrggbb`. Hay 9 colores distintos (no es todo blanco), 1.097 celdas con fórmula y 4 rangos combinados. Lo verifiqué con una consulta SQL, solo con conteos.
5. ✓ Las 342 pestañas activas tienen `sheet_id`, y el `sheet_id` del contenido coincide con el de `source_tab` en todos los snapshots. En vivo no hay pestañas `SIN_CLASIFICAR`. El caso lo cubre `test_import_stores_one_snapshot_per_tab_and_registers_tabs`; los mutantes "unclassified class" y "unclassified event" murieron.
6. ✓ Ningún `tab_read` está sin `duration_ms` o sin `cell_count`. Las claves que aparecen en los `details` de todos los eventos son solo identificadores y conteos (`cell_count`, `stored`, `unchanged`, `failed`, `call`, `status`, `attempt`, `wait_s`). Hay un test con texto marcador sobre los eventos y la salida; el mutante que mete `str(e)` en el evento murió, porque el cuerpo del `HttpError` falso lleva el marcador.
7. ✓ Los tests de 429 y 503 verifican esperas de 1 y 2 segundos, un evento por intento, la pestaña fallida tras el máximo y que la corrida sigue. Los mutantes "retry 429", "growing wait", "retry event" y "continue after fail" murieron. En vivo hubo 8 `google_retry` reales en las corridas de implement.
8. ✓ La imagen recién construida no tiene la clave: `find` no encuentra `gcp-*` ni `google-sa*`, no existe `/run/secrets`, y `docker history` no la menciona. El Dockerfile solo copia `app/` y `config/`. En el contenedor de Compose, `/run/secrets/google-sa.json` existe y `touch` falla con "Read-only file system". En el repo no hay ningún archivo de clave.
9. ✓ `ruff check` y `pytest` en limpio. Los tests reemplazan `Google.from_environment` por un Google falso en memoria, así que ninguno llama a la red.

## Pasada adversarial (sin hallazgos además de los de arriba)

- Nombres de pestaña con `'` (se escapan como `''` en el rango), con acentos ("Dolar - Inflación") y con espacio final en el título de la planilla ("Base informe Craftech "): se leen bien en vivo y en el código.
- Errores de Google: el 403 no se reintenta; el 404 de planilla falla solo esa planilla; el `DecodeLimitError` y el `\u0000` fallan solo su pestaña. Todo con tests y mutantes.
- La salida del CLI muestra el status de un `HttpError`, no su mensaje (que podría citar el pedido), y lista títulos y tiempos, nunca valores.
- Se mantiene el aviso de `sources load` de T-001: las pestañas `SIN_CLASIFICAR` no se desactivan (mutante muerto).
- Complejidad: no encontré capas ni opciones que ningún criterio necesite. El cambio de `decode_limit_ratio` está justificado con una medición escrita en el ticket.

## No verificado

- La importación completa de las 20 planillas no la repetí: leí de nuevo en vivo solo "CASH FLOW MENSUAL", la planilla de F1, y verifiqué las corridas de implement contra la base. El tiempo de 44,6 segundos de "Facturación - Craftech Total" es la medición de implement.
- FileVault: lo verifica Ariel, como dice el ticket. El README lo deja anotado.

## Split-outs sugeridos (fuera del alcance)

- [data] La app tiene `DELETE`, `UPDATE` y `TRUNCATE` sobre `snapshot` (`has_table_privilege` da verdadero para `craftech_app`). Hoy "nunca se borra" lo garantiza solo un test sobre el código, y de hecho en esta rama se hizo un `TRUNCATE` a mano. Se podría reforzar en la base, por ejemplo con un trigger que rechace `UPDATE` y `DELETE`, si Ariel lo quiere.
- [data] El ruido de punto flotante de F1 ya está anotado por implement en `plan/improvements.md`, para T-003 y T-004.
