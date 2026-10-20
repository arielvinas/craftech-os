# QA T-012 — Ronda 2

**Verdict: PASS**
**Branch:** arielvinas/t-012-fundings @ 3d6615b
**Gates:** typecheck — (el repo no tiene) · lint ✓ (`ruff check`; `ruff format --check`: 54 archivos) · tests ✓ (289 passed con `TEST_DATABASE_URL`) · build — (no hay)
**Criteria:** 6/6 se cumplen. Los criterios 2, 3 y 5 se verificaron con el Google falso de los tests y con la última lectura local real; falta el paso humano en la planilla de prueba (ver "No verificado").
**Mutation:** arnés `plan/qa/evidence/T-012-r2-mutants.py`: es el de la ronda 1, con el patrón del corte de Pagos ajustado al código nuevo y 6 mutantes nuevos; corre solo `app/tests/test_fundings.py`. Mata 22 de 24. Los 6 sobrevivientes de la ronda 1 ahora mueren. Los 2 nuevos sobrevivientes son caminos de problemas sin test (F1). El cambio central de esta ronda muere en las dos direcciones:
- volver a saltear la fila que abre el bloque (`rows[1:]`);
- convertir esa fila en hito.

## Qué cambió desde la ronda 1

- `from_pagos` recorre todas las filas del bloque. Un monto tipeado en la fila que abre un bloque de funding, en un mes hasta febrero de 2026, abre `fila_sin_interpretar` con la celda, en lugar de perderse.
- El corte de meses (marzo de 2026 en adelante) se evalúa antes de decidir si abrir un problema.
- En SleakOps, "General" pasa a ser bloque de funding, igual que en Craftech. Está documentado como supuesto pendiente de ratificar.
- Tres tests nuevos:
  - la fila de apertura, con una copia en una fila de cliente;
  - un duplicado que necesita el mismo monto, con alias que unen textos, más el borde del 24/2/2026;
  - una columna faltante y un monto ilegible en el tracker.

## Findings

### F1 [minor] Dos caminos de problemas de Pagos sin test
- **Repro:** `python3 -I plan/qa/evidence/T-012-r2-mutants.py <raíz>` con `TEST_DATABASE_URL`.
- **Actual:** sobreviven dos mutantes:
  - **"keyless row becomes a milestone":** se saca `row["key"] is None` de la condición que abre `fila_sin_interpretar` en `from_pagos` (`app/craftech_os/interpret/fundings.py`, línea 147). Una fila sin clave dentro de un bloque de funding daría un hito sin cliente ni texto de alias, y ningún test cae.
  - **"pagos unreadable amount":** sin el `if amount is None and unreadable(cell)` de `from_pagos`, un monto ilegible en un bloque de funding de Pagos se descarta sin abrir `valor_ilegible`, y ningún test cae. El mismo camino del tracker sí se prueba desde esta ronda.
- **Expected:** un test por cada problema que el intérprete abre.
- **Por qué es minor:** son caminos que ya existían en la ronda 1, no forman parte de lo corregido y el ticket no los promete en su plan de pruebas. En la última lectura real no aparece ninguno de los dos casos.

### F2 [nit] Una fila sin clave con monto desde marzo de 2026 ya no abre problema
- **Actual:** como el corte de meses ahora va antes de la condición de "sin clave", una fila sin clave dentro de un bloque de funding, con monto en marzo de 2026 o después, se saltea en silencio. En la ronda 1 abría `fila_sin_interpretar`. Es coherente con la regla R28: después del corte, el tracker tiene los hitos y Pagos no da nada. Además, para la fila de apertura era necesario: si no, las celdas T96, X96, S77 e Y77, de 2026, abrirían problemas. Se anota solo porque cambia el comportamiento.

### F3 [minor] (sigue de la ronda 1, F4) El único `funding_duplicado` real parece un falso positivo
- Sigue igual: cruza la celda I4 de FUNDINGS (cargado en febrero de 2026) con la celda K110 de Pagos de Craftech (el mismo cliente con otro texto de alias, agosto de 2025). Ahora está en el ticket como la pregunta pendiente 3 para Emi y Ro (si hay que acotar el cruce por fecha). No es decisión de implement ni de QA, y el problema solo avisa: no junta ni borra nada.

## Re-verificación de la ronda anterior

- **F1 (r1, blocker), montos de CEI de la fila de apertura de "General" perdidos:** ✓ resuelto. En la base local (solo lectura) se abren los siete `fila_sin_interpretar`, con estas celdas:
  - E96, H96, K96 y N96 en Craftech;
  - E102, H102 y K102 en SleakOps.

  Los hitos siguen siendo 91 en Craftech (enero de 2025 a febrero de 2026) y 10 en SleakOps. Quedan afuera con razón:
  - T96 y X96, y también S77 e Y77, por ser de 2026;
  - Q96, por ser `IMPORTRANGE`.

  El test `test_an_amount_typed_in_the_row_that_opens_a_block_is_a_problem_not_lost` mata los mutantes en las dos direcciones. Que esos montos sean hitos del programa CEI queda como la pregunta 1 para Emi y Ro.
- **F2 (r1, major), duplicados y borde del corte sin test negativo:** ✓ resuelto. Mueren "duplicate without amount", "duplicate without client alias" y "R28 cut date moved". Este último muere porque la fila cargada el 24/2/2026 no da hito en el tracker.
- **F3 (r1, minor), tres caminos de problemas sin test:** ✓ resuelto. Mueren:
  - "tracker missing column issue";
  - "tracker unreadable amount";
  - "copied amounts are milestones", ahora con la copia `='Otra planilla'!D5` en una fila de cliente.
- **F4 (r1, minor), el único duplicado real:** sigue abierto como pregunta para Emi y Ro. Ver F3 de esta ronda.
- **F5 (r1, minor), "General" como bloque de funding sin ratificar:** documentado como la pregunta 2. Ahora las dos planillas lo tratan igual. Cambiar `funding_blocks` de SleakOps no toca facturas: `pagos.py` solo lee facturas del bloque del encabezado.

## Criterios

1. Esquema en `sources.yaml` aceptado: ✓. Lo prueba `test_the_real_config_has_the_fundings_schema`, que ahora incluye "General" en SleakOps, y los esquemas inválidos se rechazan.
2. Hito del tracker en `mcp.fundings` con origen `tracker`, cobro = sign-off + 30 días y celda: ✓ en tests y en la lectura real (94 hitos del tracker).
3. Enero de 2026 da hito `pagos` y marzo de 2026 no: ✓ en tests. El mutante "off by one" del corte (`LAST_PAGOS_MONTH` en enero) muere.
4. El duplicado abre `funding_duplicado` y quedan las dos filas: ✓. Ahora también está probado el negativo (distinto monto, distinto cliente) y la unión por alias.
5. Paridad en 0 con datos consistentes: ✓ en tests. Con las lecturas reales, `mcp.paridad_fundings` coincide exactamente con la tabla del ticket: la única diferencia es un mes de Craftech (2026-06).
6. Ninguna vista de facturas incluye fundings: ✓ en tests. En la base real, el cruce de celdas entre `mcp.facturas` y `mcp.fundings` da 0.

## No verificado

- **Criterios 2, 3 y 5 en la planilla de prueba de Ariel:** QA no escribe en Google Sheets. Falta el paso humano: cargar un hito en la planilla de prueba y ver la fila y la celda en `mcp.fundings`.
- **Diferencia en junio de 2026:** no es un error de esta ronda. Es la consecuencia documentada del supuesto del ADR: un hito cargado antes del corte y cobrado después no queda en ningún lado, y la paridad lo muestra (no es silencioso). Depende de la respuesta de Ro sobre el criterio de corte.
- **Navegador:** no aplica, no hay interfaz en esta etapa.

## Split-outs sugeridos (fuera del alcance)

- Ninguno nuevo. El de la ronda 1 (filas de apertura de `pagos.py` y `ventas.py`) ya está en `plan/improvements.md`.
