---
id: T-019
title: Cashflow mensual con el origen de cada celda y vistas MCP
status: pr
priority: high
lane: core
depends_on: [T-018]
effort: M
milestone: C
branch: arielvinas/t-019-cashflow-mensual
---

## Context

Segundo ticket de la caja (`plan/adr/ADR-003-caja-desde-movimientos.md`, aprobado por Ariel el 25-oct-2026). Con los movimientos de T-018 y las reglas de `config/cashflow_rows.yaml`, arma el cashflow mensual con la forma del Resumen de Finanzas y dice de dónde sale cada número: recalculado por nosotros, importado de la planilla o parámetro.

Decisiones del documento de arquitectura (ADR-003), que este ticket aplica sin reabrir:
- **Origen de cada celda:**
  - `recalculada`: mes real y fila con regla.
  - `importada`: mes proyectado, fila sin regla o celda fijada a mano en el Resumen (sin fórmula).
  - `parametro`: el valor para «traer dólares para cerrar el mes con 4 millones de pesos».
- **Mes real:** hasta el último mes completo con movimientos. El mes en curso se recalcula y se marca como tal. El resto son proyectados y todos se importan hasta que Emi y Ro ratifiquen las reglas de proyección; en la primera versión cerca de la mitad de la tabla es importada, y está bien.
- **Indicadores propuestos** (no ratificados; la pantalla muestra la fórmula al lado del número):
  - caja hoy = último saldo real;
  - salida mensual = promedio de egresos de los últimos tres meses reales;
  - meses de cobertura = caja hoy ÷ salida mensual;
  - cierre de marzo-27 de los dos bloques de Craftech Inc. (con y sin pagos proyectados).
- **Sueldos solo como total** también en las vistas MCP.

Verificado en el repo el 25-oct-2026:
- "Resumen mensual Cash Flow ARG-USA", en la planilla CASH FLOW MENSUAL, es de clase **DERIVADA** en `config/sources.yaml`. `interpret.run()` devuelve `None` para cualquier pestaña que no sea CARGA, así que la proyección de `cashflow_sheet_cell` necesita su propio camino (una función aparte llamada después de leer esa pestaña, o una excepción explícita en el despacho), no un intérprete más en `INTERPRETERS`.
- La fórmula de cada celda ya viene en el contenido de la lectura (`cell->>'formula'`, como lo usa `mcp.celdas` en la migración 0007). Celda fijada a mano = celda del Resumen sin fórmula.
- Las vistas MCP llevan columnas en castellano y `GRANT SELECT ... TO mcp_reader`, nunca a `mcp_writer` (por ejemplo `mcp.paridad_fundings_aws` en 0012).
- T-018 deja la migración 0014; esta es la 0015. El documento de arquitectura ponía las dos tablas en 0014; se separan porque cada ticket de `core` trae su propia migración.

## Scope

**Dónde vive:**
- `app/migrations/0015_cashflow_cell.sql`.
- `app/craftech_os/cashflow.py` (nuevo): la proyección del Resumen y el armado de las celdas.
- el punto donde se llama a la interpretación después de una lectura (`app/craftech_os/cli.py`, cerca de `interpret.run`), para proyectar también la pestaña del Resumen.
- `app/tests/`.

1. **`cashflow_sheet_cell`.** Rehecha por cada lectura del Resumen: `source_tab_id`, `snapshot_id`, bloque, fila, mes, valor, `cell_ref` y si la celda tiene fórmula. Guarda lo que dice la planilla; no interpreta.
2. **`cashflow_cell` (vista).** Bloque, fila, mes, valor, unidad, origen (`recalculada`, `importada`, `parametro`, con `CHECK` o equivalente), y la referencia a la celda del Resumen.
   - Lo `recalculada` sale de sumar `cash_movement` según la regla de la fila en `config/cashflow_rows.yaml`, en la unidad de la fila (miles de pesos o dólares).
   - Lo `importada` y `parametro` sale de `cashflow_sheet_cell`.
   - El mes en curso se distingue de los reales cerrados (una columna o una marca), para que la pantalla lo tinte.
3. **Indicadores.** Una vista con los cinco indicadores propuestos, cada uno con su valor, su fórmula en texto y la marca de que está propuesto, no ratificado.
4. **Vistas MCP.**
   - `mcp.caja_mensual`: bloque, fila, mes, valor, unidad, origen, planilla, pestaña, celda y lectura.
   - `mcp.movimientos_de_caja`: los movimientos de `cash_movement` con nombres en castellano. Detalle, Subdetalle y Equipo salen vacíos en las filas de «01. Sueldos» (ya vienen vacíos de T-018; la vista no los vuelve a exponer de otra fuente).
   - `mcp.indicadores_de_caja`.
   - `GRANT SELECT` a `mcp_reader` en las tres; ninguna a `mcp_writer`.
   - `COMMENT ON` en castellano en cada vista y columna.

**Descartado:**
- Un intérprete más en `INTERPRETERS` para el Resumen: el despacho solo corre sobre pestañas CARGA y el Resumen es DERIVADA.
- Proyectar meses futuros con reglas propias: todo lo proyectado se importa hasta que Emi y Ro ratifiquen.

## Acceptance criteria

Reescritos el 2026-10-26 según la sección Decisions: ninguna celda muestra un valor del Resumen; lo que no se calcula desde los movimientos queda sin valor y marcado (origen `sin_regla` o `parametro`, con `motivo`). El origen `importada` desaparece.

- [x] La migración 0015 crea `cashflow_row`, `cashflow_sheet_cell`, la vista `cashflow_cell`, la vista de indicadores `cashflow_indicator` y las tres vistas MCP, con `COMMENT ON` en castellano en cada tabla, vista y columna (`test_db.py`, `test_mcp.py`).
- [x] Una lectura sintética del Resumen proyecta `cashflow_sheet_cell` aunque la pestaña sea DERIVADA, y una segunda lectura la reemplaza entera (`test_the_resumen_is_projected_though_derivada_and_a_new_read_replaces_it`); las otras pestañas no se tocan (`test_other_tabs_are_not_projected`); `interpret` también la proyecta (`test_the_cli_interpret_projects_the_resumen_too`).
- [x] Con movimientos y un Resumen sintéticos: un mes real con fila con regla sale `recalculada` con la suma de los movimientos, aunque la celda del Resumen sea tipeada y tenga otro valor (`test_real_months_add_the_movements_and_no_sheet_value_is_shown`); un mes proyectado y una fila sin regla salen sin valor, con origen `sin_regla` y su motivo (`test_projected_months_and_rows_without_a_rule_have_no_value_and_say_why`); «$ recibidos de la INC» y «USD enviados a la S.A.» de los dos bloques de Craftech Inc. salen `parametro`, sin valor, en los meses proyectados (`test_the_four_million_parameter_rows_are_marked_in_projected_months`).
- [x] El mes en curso se recalcula y se distingue de los meses reales cerrados: periodo `en_curso` (`test_the_current_month_is_recalculated_and_marked`). Los meses reales llegan hasta el último mes cerrado con movimientos; un mes cerrado sin movimientos queda proyectado y no entra en los indicadores (`test_a_closed_month_without_movements_is_not_real_yet`).
- [x] Los indicadores (solo Craftech Inc., en dólares) dan el valor esperado sobre los datos sintéticos y cada uno trae su fórmula en texto y la marca de propuesto (`test_the_indicators_are_proposed_with_their_formula`).
- [x] `mcp_reader` puede leer `mcp.caja_mensual`, `mcp.movimientos_de_caja` y `mcp.indicadores_de_caja`; `mcp_writer` no (`test_the_reader_reads_the_cash_views_and_the_writer_does_not`).
- [x] Un test siembra un movimiento de «01. Sueldos» y verifica que ningún sueldo individual se filtra por `mcp.movimientos_de_caja` ni por `mcp.caja_mensual`: solo totales por fila y mes (`test_no_salary_of_a_person_reaches_the_cash_views`). En `mcp.movimientos_de_caja` los sueldos van como un total por mes, banco, moneda, tipo de movimiento, rubro y agrupador, sin celda ni tipo de cambio.
- [x] Los tests usan solo datos sintéticos; los eventos llevan cantidades, nunca montos (`test_projection_events_carry_counts_only`).

## Out of scope

- La paridad contra el Resumen (T-020) y la pantalla `/caja` (T-021).
- Ratificar las fórmulas de los indicadores y las reglas de proyección (Emi y Ro).
- Escenarios, «Pagos en disputa» e IVA.

## Decisions

- 2026-10-26 — **Sociedad y moneda de los cinco indicadores** → Opción a: solo Craftech Inc., en dólares. Caja hoy = Saldo Final de Craftech Inc. en dólares del último mes real cerrado; salida mensual = promedio de Sueldos + Gastos + USD enviados a la S.A. de los últimos tres meses reales cerrados; cobertura = caja ÷ salida; cierres de mar-27 = Saldo Final de cada bloque de Craftech Inc. El mes en curso no cuenta como cerrado. Todo calculado por el software.
- 2026-10-26 — **Celdas con origen parametro (traer dólares para cerrar el mes con 4 millones de pesos)** → Opción b: la fila «$ recibidos de la INC» del bloque Argentina más «USD enviados a la S.A.» de los dos bloques de Craftech Inc., en los meses proyectados. El parámetro (4 millones de pesos) lo aplica el software, no se lee el valor calculado de la planilla.
- 2026-10-26 — **Origen de cada celda del Resumen mensual (todos los meses reales están tipeados sin fórmula)** → Ariel: todos los valores se calculan en el software a partir de los datos (los movimientos de caja). No se muestra ningún valor tomado del Resumen de la planilla, tenga o no fórmula; la planilla queda solo como referencia para la comparación de paridad. Si una fila no se puede calcular desde los datos (no hay regla ratificada), no se inventa: queda sin valor y marcada, y lo reportás.

## Implementation

- `app/migrations/0015_cashflow_cell.sql`:
  - tablas `cashflow_row` (las reglas de `config/cashflow_rows.yaml`) y `cashflow_sheet_cell` (lo que dice el Resumen, solo para ubicar filas y meses y para la paridad de T-020);
  - vista `cashflow_cell`: suma `cash_movement` por regla. Saldo inicial y final son acumulados por banco; las transferencias internas se cancelan. Los subtotales suman filas del bloque. Periodo `real`, `en_curso` o `proyectado`; origen `recalculada`, `sin_regla` o `parametro`, con `motivo`;
  - vista `cashflow_indicator` y las vistas `mcp.caja_mensual`, `mcp.movimientos_de_caja` y `mcp.indicadores_de_caja`, con `GRANT SELECT` solo a `mcp_reader`.
- `config/cashflow_rows.yaml`: 27 filas en 5 bloques, con regla de cálculo (rubros, bancos, saldo, suma, signo) para 13 filas; las demás quedan sin regla.
- `app/craftech_os/cashflow.py`:
  - `rows()` valida el yaml: unidad, saldo con bancos, signo, y que cada suma nombre filas del bloque con regla;
  - `locate()` ubica secciones, filas y meses en el Resumen;
  - `project()` rehace las dos tablas y registra el evento `cashflow_projected` con cantidades.
- El importador y `craftech-os interpret` llaman a `cashflow.project` en cada lectura; vuelve sin hacer nada si la pestaña no es el Resumen.

**Prueba de humo** (copia de la base de desarrollo, 2026-10-26; solo cantidades y proporciones):
- Las 27 filas quedan ubicadas: 1.431 celdas, 53 meses, `filas_sin_ubicar` = 0, en 0,17 s.
- 38 meses reales, 1 en curso y 14 proyectados.
- 507 celdas recalculadas y 42 de parámetro; las demás quedan sin regla (sin valor y marcadas).
- Caja hoy, salida mensual y cobertura tienen valor; los dos cierres de marzo-27 quedan nulos hasta que haya reglas de proyección.
- Paridad orientativa contra la planilla (dentro del 3 %):
  - Craftech Inc. en dólares: 49 % de las celdas recalculadas. Saldo inicial, saldo final y cobros: 70 % cada uno. Gastos: 8 %. USD enviados: 21 %.
  - Argentina: 14 %.
  - Lo cierra T-020.
- Las vistas MCP tardan 0,65 s (`caja_mensual`) y 1,5 s (`indicadores_de_caja`). `mcp_reader` lee las tres y `mcp_writer` recibe «permission denied».

### Ronda 2 (hallazgos de QA ronda 1)

- **Hallazgo 1, sueldos en `mcp.movimientos_de_caja`.** El runner resolvió la ambigüedad: valen el Contexto y el criterio 7. La vista da los movimientos que no son sueldos tal cual. Los de «01. Sueldos» o del tipo Sueldos van en una fila por mes, banco, moneda, tipo de movimiento, rubro y agrupador, con `monto` y `monto_usd` sumados y `tipo_cambio`, `celda`, detalle, subdetalle y equipo nulos. El test siembra dos sueldos en el mismo mes y banco y exige que se vea solo su total. Con la vista anterior falla.
- **Hallazgo 2, mes real.** Es real hasta el último mes cerrado que tiene movimientos, es decir el mayor mes de `cash_movement` anterior al mes de hoy. Un mes cerrado sin movimientos queda `proyectado`: no tiene valor y lleva su motivo. Caja hoy toma ese último mes real, y salida mensual promedia los tres últimos meses reales (nula si hay menos de tres). El test nuevo saca los movimientos del último mes cerrado. Con la vista anterior falla.
- **Hallazgo 3 (minor).** Va como split-out en `plan/improvements.md`.
- **Hallazgo 4 (nit).** El comentario de `mcp.caja_mensual.unidad` aclara que el bloque «en miles de pesos» está en la misma escala que la planilla.
- **Hallazgo 5 (nit).** Sin cambios: la guarda de tres meses ahora sí actúa cuando hay menos de tres meses reales.
- Sin verificar en la ronda 2: la prueba de humo sobre una copia de la base de desarrollo. Solo corrieron los tests.

## Test plan

- `uv run pytest -q`: 350 pasan en la ronda 2 (13 en `test_cashflow.py`, más los cambios de `test_db.py` y `test_consolidado.py`). Además pasan `ruff check`, `ruff format --check` y `uv build`.
- Mutaciones:
  - 7 muertas: saldo final sin el mes, signo ignorado, valor en meses proyectados, suma sin chequear la regla, primera aparición de la etiqueta, parámetro ignorado, salida sin USD enviados.
  - 1 que sobrevivía: el `CASE` de sueldos en la vista. Era redundante con el `CHECK` de la tabla y se sacó.
  - 1 equivalente: un `GRANT` a `mcp_writer` no le da acceso, porque no tiene `USAGE` sobre el esquema `mcp`.
- Manual: la prueba de humo de arriba sobre una copia de la base, ya borrada.

## Post-merge

- En la base de desarrollo: `craftech-os migrate` (aplica la 0015) y después `craftech-os interpret --all`, para proyectar el Resumen ya leído.
- Llevar a Emi y Ro:
  - las fórmulas de los indicadores;
  - las reglas de las filas sin regla (Ventas y Gastos en pesos, saldo en dólares, bloque con pagos proyectados, diferencias);
  - por qué el saldo de Argentina no coincide: faltan el saldo de apertura y las inversiones.

Ronda 2, casos para QA:
- `SELECT mes, banco, count(*), sum(monto) FROM mcp.movimientos_de_caja WHERE rubro = '01. Sueldos' GROUP BY 1, 2`: una fila por agrupador y moneda, nunca una por pago.
- La suma de `monto` por mes y rubro en `mcp.movimientos_de_caja` coincide con la de `cash_movement`. Los totales de sueldos no pierden plata.
- Si se borran los movimientos del último mes cerrado, ese mes pasa a `proyectado` y caja hoy toma el mes anterior.
- Radio de impacto: solo la migración 0015, que todavía no está en main.
