# QA T-002 — Ronda 2

**Verdict: PASS**
**Branch:** arielvinas/t-002 @ 61c5e70
**Gates:** typecheck — (el repo no tiene typecheck configurado) · lint ✓ (`ruff check` y `ruff format --check`) · tests ✓ (72 pasan, ninguno salteado, con `TEST_DATABASE_URL` apuntando a la base `_test`) · build ✓ (`docker compose build app`)
**Criteria:** 9/9 verificados (el 3 con el texto reescrito por la decisión de Ariel del 18-oct-2026)
**Mutation:** los 18 mutantes de la ronda 1 (`/tmp/qa-t002/mutants.py`) siguen muertos ✓; 2 mutantes nuevos sobre el arreglo de F2 (sacar `KeyError` del `except`, y volver a leer `version`/`modifiedTime` fuera del `try`) ponen la suite en rojo con el test nuevo ✓

No hay interfaz web en este ticket: no corresponde navegador ni capturas. Todas las consultas en vivo se hicieron sobre la base de desarrollo con conteos y comparaciones; no se mostró ningún valor de celda.

## Findings

Ninguno nuevo. El arreglo de la ronda es chico (dos líneas en `read_tab`, un test parametrizado y dos dependencias declaradas) y no abre caminos nuevos. Hice una pasada adversarial extra sobre él (abajo) porque una ronda sin hallazgos es sospechosa; se sostiene.

## Re-verificación de la ronda anterior

- **F1 (r1) [blocker] segunda corrida agrega snapshots:** ✓ resuelto por decisión de producto. Ariel eligió la opción a (ajustar el criterio, sin tocar el hash), registrada en `## Decisions`, y el criterio 3 se reescribió con la excepción. Lo verifiqué en vivo con una **importación completa** de las 20 planillas (6 min 44 s, 0 fallidas):
  - Sumó exactamente 4 snapshots, todos de "CASH FLOW MENSUAL" (CASH FLOW ARG, Cash Flow - c/ pagos proyectados, CASH FLOW USA y Resumen mensual Cash Flow ARG-USA). Las otras 338 pestañas: `unchanged`.
  - Para cada uno de los 4, contra su snapshot anterior: misma `drive_version`, mismo `drive_modified_at`, distinto hash. Ninguna celda aparece ni desaparece; en ninguna celda cambia otro campo que no sea `value` (texto formateado, fórmula, color y formato idénticos); el documento fuera de `rows` (merges, tamaños, oculta, título) es idéntico; todas las celdas con `value` distinto tienen fórmula (70, 116, 1.203 y 171). Diferencia numérica máxima: 6e-8. Es exactamente el caso que la excepción permite.
  - En toda la tabla, las únicas pestañas con más de un snapshot son esas 4, y cada una tiene una sola versión de Drive y un solo `modifiedTime` en todos sus snapshots.
  - La corrida agregó 342 `tab_read` (uno por pestaña activa), 20 `source_read` y 8 `google_retry` (429 reales recuperados).
- **F2 (r1) [minor] falta de `version`/`modifiedTime` corta la importación:** ✓ resuelto. Las dos claves se leen dentro del `try` y `KeyError` está en la lista de errores de la pestaña. `test_a_drive_answer_without_version_fails_only_that_tab` (dos casos) verifica un `tab_failed` `{"error": "KeyError"}`, que se guardan los otros snapshots y que el comando sale con 1. Los dos mutantes que deshacen el arreglo lo matan.
- **F3 (r1) [nit] `httplib2` y `google-auth-httplib2` sin declarar:** ✓ resuelto. `pyproject.toml` los declara (pisos 0.32 y 0.4, coherentes con el lock) y `uv.lock` los lista como dependencias directas. En la imagen recién construida, `import httplib2.decode, google_auth_httplib2` funciona (httplib2 0.32.0).

## Criterios, uno por uno

1. ✓ Sin cambios desde la ronda 1 (`config/sources.yaml` y `resolve` no se tocaron en esta ronda). Los mutantes de `resolve` siguen muertos.
2. ✓ 342 pestañas activas, ninguna sin `sheet_id`, todas con snapshot; ningún nulo en los campos exigidos y todos con `origin = 'lectura'` (verificado en la ronda 1; esta ronda no cambia la inserción salvo el origen de dos variables).
3. ✓ Ver re-verificación de F1, con la importación completa en vivo.
4. ✓ Sin cambios en `document.py`; verificado en la ronda 1 ("Pagos": colores hex, 1.097 fórmulas, 4 combinadas). Mutantes de color, fórmula y combinadas muertos.
5. ✓ 342 activas con `sheet_id`. El caso `SIN_CLASIFICAR` sigue cubierto por test y mutantes.
6. ✓ Los eventos de la corrida de hoy solo llevan las claves `cell_count`, `stored`, `unchanged`, `failed`, `call`, `status`, `attempt` y `wait_s`. El `tab_failed` nuevo lleva solo el nombre del tipo de error (`KeyError`), nunca el mensaje (que podría citar una clave o un valor). Mutante "no values in events" muerto.
7. ✓ Tests de 429/503 y mutantes de reintento muertos; en vivo hubo 8 `google_retry` recuperados.
8. ✓ Imagen recién construida, sin montaje: `/run/secrets` no existe, `find` no encuentra `gcp-*` ni `google-sa*`, `docker history --no-trunc` no los menciona. Con Compose, la clave aparece solo en `/run/secrets/google-sa.json` (montaje de solo lectura). Ningún archivo de clave en `git ls-files`.
9. ✓ `ruff check`, `ruff format --check` y `pytest` (72) en limpio; los tests usan el Google falso en memoria.

## Pasada adversarial sobre el arreglo

- `KeyError` ahora se captura en todo el bloque de lectura, no solo en las dos claves de Drive. Revisé qué más puede tirarlo: `document.build` usa `.get` en todo y `Google.grid` valida la cantidad de pestañas con `GoogleError`, así que en la práctica solo lo tiran las dos claves de Drive. Si alguna vez saliera de otro lado, igual falla ruidoso: `tab_failed` con el tipo de error y código de salida 1. No esconde nada.
- El orden se mantiene: se valida la respuesta de Drive antes de pedir la grilla, así que una respuesta incompleta no gasta una lectura pesada.
- Complejidad: no agrega capas ni opciones; el test reutiliza el Google falso existente con un campo opcional.

## No verificado

- FileVault: lo verifica Ariel, como dice el ticket. El README lo deja anotado.

## Nota para el runner

La importación completa de esta ronda dejó en la base de desarrollo 4 snapshots más de "CASH FLOW MENSUAL" (ruido de recálculo, permitido por la decisión). No hace falta limpiarlos.

## Split-outs sugeridos (fuera del alcance)

- [data] (repetido de la ronda 1) `craftech_app` tiene permiso de `DELETE`, `UPDATE` y `TRUNCATE` sobre `snapshot`; "nunca se borra" lo garantiza solo un test sobre el código. Se podría reforzar en la base (trigger o `REVOKE`), si Ariel lo quiere.
