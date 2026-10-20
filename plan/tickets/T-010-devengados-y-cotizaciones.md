---
id: T-010
title: Devengados y cotizaciones: módulo interpret con VENTAS y las filas de cotización de Pagos ARG, enganchado al worker
status: done
priority: high
lane: core
depends_on: [T-009]
effort: M
milestone: B
branch: arielvinas/t-010-devengados-y-cotizaciones
---

## Context

ADR-002, secciones 1 a 4 y 7. Este ticket crea el módulo `interpret`, que los tickets T-011 y T-012 extienden. Su primer uso son los devengados de VENTAS y las cotizaciones de Pagos ARG; las facturas ARG de T-011 las necesitan.

Decisiones de Ariel del 19-oct-2026:
- ADR-002 aprobado.
- La carga real de clientes y aliases queda en el post-merge de T-009, así que este ticket no espera datos reales.

Verificado en el repo el 19-oct-2026:
- El punto de enganche natural es `app/craftech_os/diff/store.py`, función `record`: guarda los `cell_change` de una lectura nueva y ya llama a `detect.find` y `detect.upsert`. El worker está en `app/craftech_os/worker.py`.
- Funciones reutilizables de `diff/compare.py`:
  - `blocks`: separa los bloques de una pestaña.
  - `column_index` y `column_letters`: convierten entre letra y número de columna.
  - `a1`: arma la referencia de celda.
  - `value`: lee el valor de una celda.

  Las filas tienen `key` (el `row_key` normalizado) y `ordinal`.
- `issues/detect.upsert(conn, issue_type, stable_key, source_id, source_tab_id, details)` abre problemas idempotentes por `UNIQUE(issue_type, stable_key)`. El CHECK de `issue.issue_type` hoy admite solo `color_desconocido`, `alineacion_ambigua`, `valor_ilegible` y `pestana_sin_clasificar` (`0004`).
- Esquemas de VENTAS en `config/sources.yaml`:
  - Craftech: encabezado "Cliente", bloque "Total Ingresos", grilla E:AN.
  - SleakOps: encabezado "Mes", bloques "General" y "Total Ingresos", grilla D:AM.

  La columna de mes se deduce del encabezado de la grilla, no de la letra.

## Scope

**Dónde vive:**
- `app/migrations/0009_accruals_fx.sql`
- `app/craftech_os/interpret/`: un submódulo por pestaña y un `run(conn, snapshot_id)` común.
- el enganche en `diff/store.record` o en el worker, justo después de guardar la lectura
- `cli.py`
- tests

1. **Migración 0009:**
   - Tabla `accrual`, el devengado: pestaña, bloque, `row_key`, orden de la serie, mes, monto en USD tal como está en la celda, unidad de negocio y POD como texto, `snapshot_id`, `cell_ref` y `rules_version`.
   - Tabla `fx_rate`, la cotización: tipo (`mep`, `oficial`, `tipeada`), mes, pestaña, valor, si es "tipo a confirmar", `snapshot_id`, `cell_ref` y `rules_version`.
   - Los siete tipos de problema nuevos en el CHECK de `issue`: `alias_sin_cliente`, `cotizacion_tipeada`, `cotizacion_discrepante`, `cotizacion_tipo_a_confirmar`, `funding_duplicado`, `identidad_en_revision`, `fila_sin_interpretar`.
   - Vistas `mcp.devengados` (con el cliente resuelto por alias, nulo si no hay) y `mcp.cotizaciones`, con columnas de origen (planilla, pestaña, celda, lectura), `COMMENT ON` en español y `GRANT SELECT` a `mcp_reader`.
2. **Proyección por pestaña.** `interpret.run` toma la lectura nueva de una pestaña con esquema y, en una sola transacción, borra los hechos de esa pestaña e inserta los nuevos con el `rules_version` vigente (una constante del módulo). Pestañas sin intérprete: no hace nada. Registra en `system_event` la cantidad de hechos insertados, la cantidad de problemas abiertos y los segundos que tardó, nunca valores.
3. **VENTAS:**
   - Un devengado por fila de cliente y columna de mes, con el monto tal como está en la celda: sin recalcular el prorrateo por días, que ya hizo Ro (regla R1), y neto de IVA (regla R14).
   - "Ventas Argentina 2025" no se lee (regla R37).
   - Si un texto se repite dentro de un bloque, son dos series: se les agrega el orden como sufijo y se abre `identidad_en_revision` (regla R26).
   - Una fila con monto sin alias vigente abre `alias_sin_cliente`, con la pestaña y el texto en `details`.
   - Una fila que no se puede ubicar en ningún bloque o mes abre `fila_sin_interpretar`.
   - Un monto que no parsea abre `valor_ilegible` y no genera hecho.
4. **Cotizaciones de Pagos ARG:**
   - Las filas de cotización se ubican por su texto en la columna A ("Dólar oficial", la MEP operativa y la otra MEP), nunca por número de fila.
   - Se guarda una cotización por tipo y mes.
   - Si la MEP de control (la fila 23 de hoy) difiere de la operativa (la fila 27 de hoy), se abre `cotizacion_discrepante` (regla R10).
   - "Dólar oficial" se guarda marcada "tipo a confirmar" y abre `cotizacion_tipo_a_confirmar`, mientras siga abierta la pregunta F-01 a Emi.
5. **Comando `craftech-os interpret [--all] [--tab <id>]`.** Reinterpreta la última lectura de una pestaña o de todas. Correrlo dos veces deja la base igual.
6. **Tests:** fixtures sintéticos de VENTAS y Pagos ARG con nombres inventados, que cubran:
   - las dos variantes de encabezado, "Cliente" y "Mes";
   - una fila repetida;
   - una fila sin alias;
   - un monto ilegible;
   - filas de cotización corridas una posición, para probar que se ubican por texto;
   - MEP discrepante;
   - idempotencia de `interpret`;
   - que una pestaña sin intérprete no se toca.

**Descartado:**
- Interpretar desde las diferencias: ADR-002, alternativas descartadas.
- Un servicio aparte o dbt.
- Guardar `client_id` en `accrual`.

## Acceptance criteria

- [ ] Cuando el worker guarda una lectura nueva de VENTAS en la planilla de prueba, `mcp.devengados` muestra los devengados de esa lectura, cada uno con planilla, pestaña, celda y `lectura_id` que llevan a la celda de origen.
- [ ] Si se edita un monto en VENTAS de la planilla de prueba, después de la lectura siguiente cambia el devengado y no quedan filas de la lectura anterior.
- [x] Una fila con un cliente inventado sin alias abre `alias_sin_cliente`; después de cargar ese alias, el devengado muestra el cliente sin reinterpretar.
- [x] `craftech-os interpret --all` corrido dos veces seguidas deja las mismas filas en `accrual` y `fx_rate` y no duplica problemas.
- [x] Con las filas de cotización corridas en el fixture, las cotizaciones salen iguales. Con la MEP de control distinta de la operativa se abre `cotizacion_discrepante`.
- [x] `system_event` registra los segundos por pestaña; en la base local con las lecturas actuales, ninguna pestaña supera los 10 segundos (el tiempo medido queda en `## Implementation`).
- [x] Ningún log ni `details` de un problema contiene montos.

## Out of scope

- Facturas, cobros y bajas de Pagos y Pagos ARG (T-011); fundings (T-012).
- Herramientas MCP nuevas (T-013) y pantallas (T-014).
- Contratos, objetivos de venta (pregunta F-23) y el P&L de la etapa C.

## Decisions

- 2026-10-20 — **¿Cómo se identifica la fuente de un alias? Hoy es texto libre y 'Pagos' y 'pagos' quedan como dos fuentes distintas (pregunta que dejó QA de T-009).** → Planilla + pestaña: la fuente de un alias es el par planilla y pestaña; el mismo alias en la misma pestaña es uno solo, sin distinguir mayúsculas. Si cambiar esto no entra en el alcance de T-010, registrarlo en plan/improvements.md.

## Implementation

- `app/migrations/0009_accruals_fx.sql`: tablas `accrual` y `fx_rate` (únicas por pestaña, bloque, texto del alias, orden de la serie y mes, y por tipo, mes y pestaña), los siete tipos de problema nuevos en el CHECK de `issue`, y las vistas `mcp.devengados` (cliente por el alias vigente de la fuente "planilla / pestaña") y `mcp.cotizaciones`, con comentarios y `GRANT` a `mcp_reader`.
- `app/craftech_os/interpret/`: `run(conn, snapshot_id)` borra e inserta los hechos de la pestaña en una transacción, abre los problemas y registra `tab_interpreted` (milisegundos y cantidades). `ventas.py` y `pagos_arg.py` son los intérpretes; `cells.py` lee meses y números de la grilla.
- Enganche: `ingest/importer.py` llama a `interpret.run` después de `store.record`, dentro de la misma transacción; el worker pasa por ahí.
- `craftech-os interpret --all | --tab <id>` reinterpreta la última lectura.
- Decisión del 20-oct (fuente de alias = planilla + pestaña): `aliases load` normaliza la `fuente`; README explica el formato "Planilla / Pestaña". Cerrado en `plan/improvements.md`.
- La MEP operativa es la última fila "MEP" de la pestaña; las anteriores son de control. "Dólar oficial" se ubica aunque esté arriba del encabezado.
- Medido en la base local (20-oct-2026, `interpret --all`, lecturas actuales): Craftech Pagos ARG 10 ms (72 cotizaciones), Craftech VENTAS 53 ms (860 devengados), SleakOps Pagos ARG 3 ms (72), SleakOps VENTAS 30 ms (1057). El comando completo tardó 4,2 s.
- Lo que encontró en datos reales: 1 `cotizacion_discrepante` en Craftech (MEP de control distinta de la operativa en un mes), 185 `alias_sin_cliente` (los aliases cargados usan la fuente vieja; ver post-merge), 26 `identidad_en_revision`, 1 `fila_sin_interpretar` (la fila "General" de SleakOps tiene montos).
- Ronda de arreglos 1 (`plan/qa/T-010-round-1.md`):
  - F1: un mes repetido en el encabezado queda solo en su primera columna (`cells.grid`); los montos de la columna repetida abren `fila_sin_interpretar` y la lectura sigue. La unicidad de `accrual` pasa a ser por pestaña, bloque, texto del alias, orden de la serie y mes, así que una fila "Cliente Uno (2)" literal ya no choca con la segunda serie de "Cliente Uno". La 0009 cambió: en la base local principal (que la tenía aplicada desde esta rama) se reemplazó la restricción a mano y se actualizó su `sha256`; `migrate` dice "nothing to apply".
  - F2: en Pagos ARG, una cotización en una columna sin mes propio (mes repetido) abre `fila_sin_interpretar` en vez de pisar la primera.
  - F3: se conserva la rama del intérprete y se agrega el test con una celda `#REF!` (que `detect.find` no ve) en VENTAS y en Pagos ARG.
  - F4: test con una pestaña "VENTAS" sin esquema y otra reclasificada como HISTORICA.
  - F5: un número del encabezado es mes solo si su formato muestra el año (`yy`); los cuatro encabezados reales usan `mmmm yyyy`. Test con un `2025` numérico y una fecha de mitad de mes.
  - La clase general (excepciones distintas de `DataError` que tumban el worker) quedó en `plan/improvements.md`; no se tocó el importer.
  - `pyproject.toml`: `ruff` excluye `plan/` (el arnés de mutantes de QA en `plan/qa/evidence/` rompía `ruff check`).
  - `interpret --all` sobre las lecturas reales después del arreglo: mismas cantidades (860, 1057, 72 y 72), 4 a 50 ms por pestaña.
- Los criterios 1 y 2 (lectura del worker sobre la planilla de prueba) están probados con el Google falso por el mismo camino del importer (`test_ventas_with_a_cliente_header...`, `test_a_new_read_replaces...`); falta verlos contra la planilla de prueba real.
- Revisión de CodeRabbit (PR #10):
  - La fuente de un alias se escribe con un espacio a cada lado de "/" en los dos lados (`clients.alias_source`), así "Planilla/VENTAS" en el CSV coincide con la pestaña.
  - Un número del encabezado fuera del rango de fechas no es mes (antes tiraba `OverflowError` y frenaba el worker); cerrado en `plan/improvements.md`.
  - `sources.yaml` rechaza una pestaña VENTAS o Pagos ARG de clase CARGA sin esquema o con un esquema sin `grid` (de otra clase no se interpreta y no lo necesita). El intérprete sigue sin tocar una pestaña sin esquema si la base quedó así.
  - `mcp.devengados` y `mcp.cotizaciones` muestran solo los hechos de la última lectura de cada pestaña (como `mcp.celdas`): si la lectura nueva no se interpreta (pestaña reclasificada o sin esquema), los hechos viejos no aparecen como vigentes. La 0009 cambió otra vez: en la base local principal se reemplazaron las dos vistas a mano y se actualizó su `sha256`; `migrate` dice "nothing to apply".

## Test plan

1. `test_ventas_with_a_cliente_header_gives_one_accrual_per_client_row_and_month`: devengado por fila y mes, unidad de negocio y POD, sin "Total Ingresos", celda que lleva a `mcp.celdas`.
2. `test_ventas_with_a_mes_header_and_a_general_block`: variante SleakOps.
3. `test_a_repeated_client_is_a_second_series_to_be_reviewed`: sufijo " (2)" e `identidad_en_revision`.
4. `test_unreadable_amounts_and_rows_with_amounts_and_no_client_are_problems`: `valor_ilegible` sin hecho; `fila_sin_interpretar` para fila sin cliente y fila de apertura con montos.
5. `test_a_client_without_alias_shows_up_once_the_alias_is_loaded`: `alias_sin_cliente`; el alias con otra capitalización de la fuente resuelve el cliente sin reinterpretar.
6. `test_rates_are_found_by_their_text`: filas corridas dos posiciones dan las mismas cotizaciones; oficial "tipo a confirmar".
7. `test_a_control_mep_that_differs_from_the_operational_one_is_a_problem`.
8. `test_interpret_twice_leaves_the_same_rows_and_problems`.
9. `test_a_tab_without_interpreter_is_not_touched`.
10. `test_a_new_read_replaces_the_accruals_of_the_previous_one` y `test_events_count_facts_and_time_and_nothing_carries_amounts`.

11. Ronda 1: `test_a_repeated_month_column_is_a_problem_and_the_read_goes_on`, `test_a_row_whose_text_ends_like_a_series_suffix_is_its_own_row`, `test_an_error_in_a_grid_cell_is_unreadable`, `test_a_ventas_tab_without_schema_or_not_carga_is_not_touched`, `test_a_header_number_that_is_not_a_date_is_not_a_month`.
12. Revisión de CodeRabbit: `test_a_header_date_out_of_range_is_not_a_month`, `test_an_interpreted_carga_tab_without_schema_or_grid_is_rejected`, `test_facts_of_an_older_reading_are_hidden_once_a_newer_one_is_not_interpreted`, y el alias de `test_a_client_without_alias_shows_up_once_the_alias_is_loaded` escrito "planilla/pestaña" sin espacios.

Blast radius: toda importación pasa ahora por `interpret.run` dentro de su transacción (un error del intérprete frena la lectura de esa pestaña); `aliases load` normaliza la fuente (`test_clients` actualizado); el CHECK de `issue_type` se recrea.

## Post-merge

1. `craftech-os migrate` (aplica 0008 si falta y 0009). Si alguna base tiene aplicada la 0009 de una versión anterior de esta rama, `migrate` falla con "changed after it was applied": borrar `accrual`, `fx_rate`, las vistas `mcp.devengados` y `mcp.cotizaciones` y la fila de `schema_migration`, o reemplazar la restricción única de `accrual` y las dos vistas (`CREATE OR REPLACE VIEW` con el texto de la 0009) y actualizar el `sha256` (así se hizo en la base local principal el 20-oct).
2. Recargar los aliases con la `fuente` en formato "Planilla / Pestaña" (por ejemplo "Facturación - Craftech Total / VENTAS"); los cargados con la fuente vieja no resuelven clientes.
3. `craftech-os interpret --all` y revisar `alias_sin_cliente` y `cotizacion_discrepante`.
