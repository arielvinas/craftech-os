---
id: T-004
title: Diferencias celda a celda entre versiones, alineación de filas por clave y problemas con clave estable
status: in-progress
priority: high
lane: core
depends_on: [T-003]
effort: L
milestone: A
branch: arielvinas/t-004
---

## Context

Unidad 3 del corte del ADR (`plan/adr/ADR-001-espejo-de-planillas-en-postgres.md`, cambios 4 y 9, riesgo "una fila insertada arriba de un bloque genera cientos de cambios falsos"). Es lo que el KICKOFF pide ver en la v0: qué cambió (celda, valor anterior y nuevo, color), en qué planilla y pestaña, cuándo. Origen de producto: `docs/03-proposal.md` sección 3.2 (tipos de cambio), 3.6 (identidad de fila: alineación por clave dentro de bloques; si es ambiguo no se adivina, se genera un problema), 3.5 (problemas) y 4.3 (qué detecta).

Reglas del documento base que este ticket toca, con su texto:
- **R29** (ratificada por Emi): cinco colores de estado de factura, `#00ffff` FC A CONFIRMAR, `#4a86e8` FC CONFIRMADA, `#ff9900` FC ENVIADA, `#d9ead3` FC PAGADA, `#ff00ff` RETRASO PAGO; celda con monto y sin color = A FACTURAR; mapeo único y global. En la etapa A solo se **detecta** el color y se reporta el desconocido; el estado de factura es etapa B.
- **R30** (ratificada): vaciar la celda = el dato deja de existir; celda con monto y otro color = cambio de estado; lo ilegible se reporta, no se adivina.
- **R38** (ratificada): una cotización tipeada a mano en una celda de conversión se marca para revisión. En la etapa A se detecta como "fórmula pisada" (la celda pasa de tener fórmula a tener un valor).
- **R26** (ratificada): la identidad de la factura es fila de cliente + mes + entidad legal; para dos contratos separados se usan dos filas. Dos filas con la misma clave en el mismo bloque son dos series legítimas.

Hechos verificados en la etapa 2 (`docs/02-questions.md`, F-05): además de los cinco colores de R29 aparecen `#c9daf8` en celdas vacías futuras de "Pagos" de "Facturación - Craftech Total", `#d0e0e3` en "Pagos ARG", `#ea9999` en "Pagos" de "Facturación - SleakOps Total" y blanco explícito. Esos van a ser los primeros problemas de "color desconocido"; por eso el problema es por (pestaña, color) y no por celda (ADR, cambio 4).

Decisiones de Ariel (18-oct-2026, sesión de tickets):
- Alineación por clave solo para las seis pestañas con esquema declarado: "Pagos", "Pagos ARG" y "VENTAS" de "Facturación - Craftech Total" y de "Facturación - SleakOps Total", y "FUNDINGS" de "FUNDINGS - Log de status [OFICIAL]". Las demás pestañas se comparan por posición (número de fila y columna) hasta que alguien les agregue esquema en `sources.yaml`.
- "Valor ilegible" en la etapa A: solo dentro de los bloques declarados de esas seis pestañas, texto no numérico donde la grilla de meses espera número; clave estable pestaña + fila clave + columna.
- ADR, cambio 9: la alineación usa el texto crudo normalizado (minúsculas, sin acentos, sin espacios dobles), no la tabla de aliases; un cliente renombrado es un cambio registrado, no un alias resuelto.

Verificado en el repo tras T-003: hay snapshots consecutivos por pestaña con `sheet_id` estable; no existe ninguna comparación entre ellos. **Restricción de esquema para T-006:** la web se construye sobre `cell_change` tal como la crea este ticket y corre en paralelo con T-005; por eso las columnas de atribución nacen acá, nulas, y T-005 solo las llena. Ningún ticket posterior de la etapa A altera `cell_change`.

## Scope

**Dónde vive:** `app/craftech_os/diff/` (algoritmo puro, sin base de datos), `app/craftech_os/issues/`, migración `0004_cell_change_issue.sql`, `config/sources.yaml` (esquemas), worker (T-003) que llama al diff después de cada snapshot nuevo, CLI.

1. **Migración `0004_cell_change_issue.sql`:**
   - `cell_change`: id, source_tab, `from_snapshot`, `to_snapshot`, `change_type` (`value`, `formula_overridden`, `formula`, `color`, `emptied`, `row_inserted`, `row_deleted`, `row_moved`, `column_inserted`, `tab_added`, `tab_deleted`, `tab_renamed`), `block` (texto, nulo sin esquema), `row_key` (texto crudo normalizado, nulo sin esquema), `row_ordinal` (sufijo de orden para claves repetidas, R26), `cell_ref` (notación A1 en coordenadas del snapshot nuevo; nulo en cambios de fila o pestaña), `old_value`, `new_value`, `old_formula`, `new_formula`, `old_color`, `new_color` (texto), `detected_at` (`read_at` del snapshot nuevo), `window_start` y `window_end` (`drive_modified_at` del snapshot anterior y del nuevo), y las columnas de atribución **nulas hasta T-005**: `attributed_editor_ids` (texto[]), `attribution_certainty` (`cierta`, `una_de`, `sin_datos`, nulo = sin procesar), `attributed_at`. Solo inserción.
   - `issue`: id, `issue_type`, `stable_key` (único junto con el tipo), source, source_tab opcional, `first_seen_at`, `last_seen_at`, `details` jsonb, `owner` texto nulo. Tipos de la etapa A: `color_desconocido` (clave: pestaña + color), `alineacion_ambigua` (pestaña + bloque + clave de fila), `valor_ilegible` (pestaña + clave de fila + columna), `pestana_sin_clasificar` (planilla + `sheet_id`).
   - `issue_resolution`: id, issue, `action` (`resuelto`, `ignorado`), `author`, `reason`, `created_at`. Solo inserción. El estado del problema se deriva: sin resolución = abierto; última resolución = su acción; resuelto y visto de nuevo después (`last_seen_at` posterior) = "reabierto" al consultar, sin escribir nada.
   - `COMMENT ON` en español en todo; vistas `v_issue` (estado derivado) para la web y el servidor MCP.
2. **Esquemas en `sources.yaml`** para las seis pestañas: fila de encabezado, columna clave, lista de bloques (texto del encabezado que los abre, en la columna clave) y rango de columnas de la grilla de meses. Se relevan leyendo las planillas con la service account; en el YAML van nombres de columnas y encabezados de bloque, nunca nombres de clientes. `source_tab.schema` se carga desde ahí con `sources load`.
3. **Algoritmo de diferencias** (función pura: dos documentos JSONB → lista de cambios), por pestaña:
   - **Con esquema:** las filas se agrupan por bloque (desde su encabezado hasta el siguiente) y dentro del bloque se alinean por clave normalizada. Clave repetida dentro del bloque: se numera por orden de aparición (`row_ordinal`); si la cantidad de repeticiones cambia entre versiones o una fila cambia de clave y de posición a la vez, no se adivina: problema `alineacion_ambigua` y las filas afectadas se comparan por posición en esa corrida. Fila con clave nueva = `row_inserted`; clave que desaparece = `row_deleted`; misma clave y mismo contenido en otra posición = `row_moved` sin cambios de celda. Filas sin clave (celda clave vacía) se alinean por posición dentro del bloque. Encabezado nuevo en la fila de encabezado = `column_inserted`.
   - **Sin esquema:** comparación por posición, celda a celda. Es la cola de la decisión de Ariel: se documenta en el README.
   - **Por celda alineada:** cambió el valor → `value`; tenía fórmula y ahora tiene valor → `formula_overridden`; cambió la fórmula → `formula`; cambió solo el color de fondo → `color`; tenía valor y ahora está vacía → `emptied` (R30). Una celda puede generar más de un cambio (valor y color a la vez).
   - **Pestañas:** `sheet_id` nuevo en la planilla → `tab_added` y alta en `source_tab` como `SIN_CLASIFICAR` con problema `pestana_sin_clasificar` (reemplaza el `system_event` de T-002); `sheet_id` que desaparece → `tab_deleted` y `activa = false`; mismo `sheet_id` con otro nombre → `tab_renamed` y se actualiza el nombre.
4. **Detección de problemas** después de cada snapshot nuevo (no solo cuando hay cambios): colores de fondo dentro de la grilla de meses de las seis pestañas con esquema que no sean los cinco de R29 ni sin color/blanco → `color_desconocido` por (pestaña, color); texto no numérico en la grilla de meses → `valor_ilegible`. Un problema ya existente actualiza `last_seen_at`; nunca se duplica ni se borra.
5. **Integración con el worker:** tras guardar un snapshot nuevo, el worker calcula los cambios contra el snapshot anterior de esa pestaña y los inserta en la misma transacción que los problemas detectados. `craftech-os diff --tab <planilla> <pestaña> [--from <id> --to <id>]` recalcula a mano e imprime conteos por tipo (sin valores). `system_event` `tab_diffed` con conteo por tipo; la métrica del ADR es cambios por pestaña por día (un pico de más de 200 en una pestaña se revisa a mano).
6. **Tests, todos con fixtures sintéticos** (clientes "Cliente A", "Cliente B", montos inventados): insertar una fila arriba de un bloque produce exactamente un `row_inserted` y cero `value`; borrar una fila produce un `row_deleted`; mover una fila sin tocarla produce un `row_moved` y nada más; cambiar un color produce un `color` con hexadecimales anterior y nuevo; vaciar produce `emptied`; reemplazar una fórmula por un número produce `formula_overridden`; dos filas con la misma clave se siguen por orden; agregar una tercera repetida produce `alineacion_ambigua`; un color fuera de la lista produce un único `color_desconocido` aunque aparezca en 50 celdas; `814,8` como texto en la grilla produce `valor_ilegible`; renombrar una pestaña produce `tab_renamed` y no `tab_deleted` + `tab_added`. Test de mutación: quitar la normalización de la clave hace fallar el test de "fila movida".

**Descartado:** alineación pasando por la tabla de aliases (ADR, cambio 9: los aliases son interpretación, etapa B); problema de color por celda (miles por pestaña); versionar hechos (ADR, cambio 3); `row_identity` como tabla aparte (la propuesta la nombraba; la clave y el ordinal en `cell_change` alcanzan en la etapa A).

## Acceptance criteria

- [x] Los tests sintéticos del punto 6 pasan, y el de mutación falla cuando se quita la normalización (evidencia: salida de pytest en el QA).
- [ ] En la planilla de prueba propia de Ariel (nunca una de Finanzas) con un esquema de prueba: insertar una fila arriba del bloque y esperar la vuelta del worker deja exactamente un `cell_change` `row_inserted` para esa pestaña y ningún `value`; cambiar el color de una celda deja un `color` con `old_color` y `new_color` en hexadecimal; borrar el contenido deja un `emptied`.
- [ ] Pintar una celda de la grilla de prueba con un color fuera de la lista de R29 crea un `issue` `color_desconocido` con `stable_key` = pestaña + color; pintar diez celdas más del mismo color no crea otro y actualiza `last_seen_at`.
- [x] Insertar `issue_resolution` con `ignorado` hace que `v_issue` muestre estado `ignorado`; una nueva lectura con el color presente no cambia ese estado; para una resolución `resuelto` seguida de una nueva detección, `v_issue` muestra `reabierto`.
- [ ] Renombrar una pestaña de la planilla de prueba deja `tab_renamed`, conserva el `source_tab` (mismo id, nombre nuevo) y los snapshots previos; agregar una pestaña deja `tab_added` + `pestana_sin_clasificar`.
- [x] `sources.yaml` tiene esquema para las seis pestañas acordadas y `sources load` lo deja en `source_tab.schema`; `git diff` del YAML no contiene nombres de clientes (revisión manual en el PR).
- [x] Sobre una pestaña sin esquema, un cambio de valor produce `value` con `cell_ref` y `row_key` nulo.
- [ ] Tras el merge y un día de worker sobre las planillas reales, `craftech-os diff` no es necesario: los cambios aparecen solos y `system_event` `tab_diffed` existe por cada snapshot nuevo (verificación posterior al merge, anotada en `## Post-merge`).
- [x] Ningún test, fixture, log o `system_event` contiene datos reales; `cell_change` sí guarda valores (es su función) y solo se lee desde la base.
- [x] `uv run pytest` y `ruff check` en limpio.

## Out of scope

- Atribución de autor (T-005): las columnas existen y quedan nulas.
- Mostrar cambios y problemas (T-006), resolver problemas desde Claude Desktop (T-007): acá la resolución solo se prueba por SQL en tests.
- Interpretar colores como estado de factura, cobros, bajas (etapa B, reglas R29, R30, R31).
- Esquemas para pestañas distintas de las seis acordadas: se agregan después en `sources.yaml` sin tocar código; cada esquema nuevo es un commit, no un ticket.
- Importar revisiones viejas y calcular diferencias hacia atrás (decisión 3 de Ariel).

## Implementation

- `app/migrations/0004_cell_change_issue.sql`: `cell_change` (solo inserción; atribución nula hasta T-005), `issue` (único por tipo + clave estable), `issue_resolution` y la vista `v_issue` (abierto, resuelto, ignorado, reabierto). `COMMENT ON` en español. En `row_*`, `old_value`/`new_value` guardan el número de fila anterior/nuevo.
- `app/craftech_os/diff/compare.py`: algoritmo puro. Bloques por los textos de la columna clave, alineación por clave normalizada con ordinal para repetidas, ambigüedad → por posición + `alineacion_ambigua`, `column_insert` por encabezado nuevo, sin esquema o sin encabezado → por posición. Compara por texto formateado (ruido de punto flotante no cuenta).
- `app/craftech_os/issues/detect.py`: `color_desconocido` (por pestaña y color, con cantidad y cinco celdas de muestra) y `valor_ilegible` (texto en la grilla de meses), solo en pestañas con `grid`; `upsert` actualiza `last_seen_at`.
- `app/craftech_os/diff/store.py`: guarda cambios y problemas en la transacción del snapshot nuevo, evento `tab_diffed` con conteos por tipo y `schema_mismatch` si el encabezado no aparece.
- `importer.py`: `tab_added`, `tab_deleted`, `tab_renamed` en `cell_change`; `pestana_sin_clasificar` reemplaza el evento `tab_unclassified` de T-002.
- `sources.py` + `config/sources.yaml`: `schemas:` validado (pestaña listada, no `all_tabs`, `key` columna, `grid` rango, `blocks` textos) y cargado en `source_tab.schema`. Siete esquemas: el ticket dice "seis pestañas" pero nombra siete (tres por cada planilla de facturación más "FUNDINGS").
- CLI `craftech-os diff --tab <planilla> <pestaña> [--from --to]`: solo conteos, no escribe.
- README: sección "Cambios y problemas".

Ronda de arreglos (QA ronda 1):
- F1: antes de comparar fórmulas, la fórmula anterior se reescribe como lo haría Google tras las filas y columnas insertadas o borradas (`_shift` + `_moved_formula` en `compare.py`). Cada referencia a una fila alineada va a su fila nueva; una fila sin par (vacía o borrada) cae justo antes de la siguiente fila que no se movió; las referencias a otra pestaña y los textos entre comillas no se tocan. Las referencias absolutas (`$C$5`) también se corren, igual que en Google. Una fórmula que se edita de verdad sigue siendo `formula`, y la que quedó apuntando al número de fila viejo también.
- F2: test del hueco con distinta cantidad de filas con clave (dos de un lado, una del otro).
- F3: una clave que se va y otra que aparece en lugares distintos solo son `alineacion_ambigua` si alguna de las dos filas nuevas tiene el mismo contenido (sin contar la clave y sin importar la columna) que alguna de las que se fueron. Insertar una fila arriba y borrar otra abajo en la misma lectura da `row_inserted` + `row_deleted` sin problemas.
- F4: sin cambio de código; una fila completamente vacía no existe en el documento de la foto (T-002), así que no deja `row_inserted`. Para la prueba en vivo del criterio 2, insertar una fila con la clave escrita.
- F5: la clave de `valor_ilegible` lleva el número de repetición cuando la clave de fila se repite (regla R26: `cliente a (2):feb`); la primera aparición conserva la clave de siempre. Los colores sobre celdas vacías quedan fuera (los descarta el documento de T-002): logueado en `plan/improvements.md`.

## Test plan

- `uv run pytest -q` → 140 passed; `ruff check` y `ruff format --check` limpios.
- `app/tests/test_diff_compare.py` (22, puros) cubre el punto 6 del alcance; `app/tests/test_diff_store.py` (integración, sintéticos) cubre fila insertada guardada, color/valor/vaciado, color desconocido en 51 celdas → un problema y `last_seen_at` que avanza, `814,8` → `valor_ilegible`, tercera clave repetida → `alineacion_ambigua`, `v_issue` ignorado/reabierto, renombre solo en Google → `tab_renamed` (mismo id), pestaña nueva/borrada, pestaña sin esquema por posición, CLI `diff`, ningún valor en eventos, problemas ni salida.
- Mutación: con `normalize` devolviendo el texto sin cambios fallan 10 tests, entre ellos `test_a_moved_row_respelled_still_aligns_by_normalized_key` (sale `row_deleted` + `row_inserted` en vez de `row_moved` + `value`); restaurado, 22 passed.
- Humo de solo lectura sobre las fotos reales locales (solo conteos): los siete encabezados y sus bloques se encuentran, ninguna pestaña cae a posición, comparar una foto consigo misma da 0 cambios; FUNDINGS (única con dos fotos) da 2 `value` y 0 ambiguas.
- Ronda 2: `uv run pytest -q` → 147 passed. Nuevos en `test_diff_compare.py`: fila insertada arriba de fórmulas (por fila, con `$`, rango y referencia a otra pestaña) → solo `row_inserted`; fila borrada → solo `row_deleted`; fórmula editada tras la inserción → `formula` con la fórmula vieja original; fórmula que quedó con el número viejo → `formula`; hueco 2↔1 → ambiguas; alta + baja en el mismo bloque → sin ambiguas. En `test_diff_store.py`: dos filas con la misma clave y texto en la grilla → dos `valor_ilegible`.
- Mutación ronda 2: comparar la fórmula sin reescribir → 4 rojos; la guarda del hueco en `if False:` → 1 rojo (antes sobrevivía); ambigüedad sin mirar el contenido → 1 rojo; traducir también referencias a otra pestaña → 3 rojos; fila sin par corrida con el desplazamiento del vecino → 1 rojo; sin ordinal en `valor_ilegible` → 1 rojo.
- Humo ronda 2 (solo lectura, solo conteos, copia en `/tmp` borrada): en el último snapshot real de las siete pestañas con esquema, insertar una fila con clave como lo haría Google (filas y referencias corridas) da exactamente un `row_inserted`; con la comparación de fórmulas anterior daba entre 91 y 1087 `formula` por pestaña.
- Para la prueba en vivo del criterio 2: insertar una fila **con la clave escrita**; una fila totalmente vacía no deja ningún cambio (ver F4).
- Pendiente de Ariel: los criterios en vivo sobre su planilla de prueba (fila insertada, color, vaciado, color fuera de lista, renombre y alta de pestaña) con un esquema de prueba en `sources.yaml`.

## Post-merge

- `craftech-os migrate` y `craftech-os sources load` (carga los esquemas), reconstruir la imagen y reiniciar el worker.
- Tras un día de worker: `SELECT count(*) FROM system_event WHERE kind = 'tab_diffed'` igual a la cantidad de snapshots nuevos del día; revisar cambios por pestaña por día (más de 200 se revisa a mano) y los primeros `color_desconocido` (se espera `#ea9999`; `#c9daf8` y `#d0e0e3` están en celdas vacías y no se ven, ver `plan/improvements.md`).

