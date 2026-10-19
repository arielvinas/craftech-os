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

- [ ] Los tests sintéticos del punto 6 pasan, y el de mutación falla cuando se quita la normalización (evidencia: salida de pytest en el QA).
- [ ] En la planilla de prueba propia de Ariel (nunca una de Finanzas) con un esquema de prueba: insertar una fila arriba del bloque y esperar la vuelta del worker deja exactamente un `cell_change` `row_inserted` para esa pestaña y ningún `value`; cambiar el color de una celda deja un `color` con `old_color` y `new_color` en hexadecimal; borrar el contenido deja un `emptied`.
- [ ] Pintar una celda de la grilla de prueba con un color fuera de la lista de R29 crea un `issue` `color_desconocido` con `stable_key` = pestaña + color; pintar diez celdas más del mismo color no crea otro y actualiza `last_seen_at`.
- [ ] Insertar `issue_resolution` con `ignorado` hace que `v_issue` muestre estado `ignorado`; una nueva lectura con el color presente no cambia ese estado; para una resolución `resuelto` seguida de una nueva detección, `v_issue` muestra `reabierto`.
- [ ] Renombrar una pestaña de la planilla de prueba deja `tab_renamed`, conserva el `source_tab` (mismo id, nombre nuevo) y los snapshots previos; agregar una pestaña deja `tab_added` + `pestana_sin_clasificar`.
- [ ] `sources.yaml` tiene esquema para las seis pestañas acordadas y `sources load` lo deja en `source_tab.schema`; `git diff` del YAML no contiene nombres de clientes (revisión manual en el PR).
- [ ] Sobre una pestaña sin esquema, un cambio de valor produce `value` con `cell_ref` y `row_key` nulo.
- [ ] Tras el merge y un día de worker sobre las planillas reales, `craftech-os diff` no es necesario: los cambios aparecen solos y `system_event` `tab_diffed` existe por cada snapshot nuevo (verificación posterior al merge, anotada en `## Post-merge`).
- [ ] Ningún test, fixture, log o `system_event` contiene datos reales; `cell_change` sí guarda valores (es su función) y solo se lee desde la base.
- [ ] `uv run pytest` y `ruff check` en limpio.

## Out of scope

- Atribución de autor (T-005): las columnas existen y quedan nulas.
- Mostrar cambios y problemas (T-006), resolver problemas desde Claude Desktop (T-007): acá la resolución solo se prueba por SQL en tests.
- Interpretar colores como estado de factura, cobros, bajas (etapa B, reglas R29, R30, R31).
- Esquemas para pestañas distintas de las seis acordadas: se agregan después en `sources.yaml` sin tocar código; cada esquema nuevo es un commit, no un ticket.
- Importar revisiones viejas y calcular diferencias hacia atrás (decisión 3 de Ariel).
