---
id: T-019
title: Cashflow mensual con el origen de cada celda y vistas MCP
status: todo
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

- [ ] La migración 0015 crea `cashflow_sheet_cell`, la vista `cashflow_cell`, la vista de indicadores y las tres vistas MCP, con `COMMENT ON` en castellano.
- [ ] Una lectura sintética del Resumen proyecta `cashflow_sheet_cell` aunque la pestaña sea DERIVADA, y una segunda lectura la reemplaza entera.
- [ ] Con movimientos y un Resumen sintéticos: un mes real con fila con regla sale `recalculada` con la suma de los movimientos; un mes proyectado sale `importada`; una fila sin regla sale `importada`; una celda del Resumen sin fórmula sale `importada` aunque el mes sea real; la fila de «traer dólares para cerrar el mes con 4 millones de pesos» sale `parametro`.
- [ ] El mes en curso se distingue de los meses reales cerrados.
- [ ] Los indicadores dan el valor esperado sobre los datos sintéticos y cada uno trae su fórmula en texto y la marca de propuesto.
- [ ] `mcp_reader` puede leer `mcp.caja_mensual`, `mcp.movimientos_de_caja` y `mcp.indicadores_de_caja`; `mcp_writer` no.
- [ ] Un test siembra un movimiento de «01. Sueldos» y verifica que ningún sueldo individual se filtra: ni `mcp.movimientos_de_caja` ni `mcp.caja_mensual` devuelven Detalle, Subdetalle, Equipo o un monto por persona, solo totales por fila y mes.
- [ ] Los tests usan solo datos sintéticos.

## Out of scope

- La paridad contra el Resumen (T-020) y la pantalla `/caja` (T-021).
- Ratificar las fórmulas de los indicadores y las reglas de proyección (Emi y Ro).
- Escenarios, «Pagos en disputa» e IVA.

## Decisions

- 2026-10-26 — **Origen de cada celda del Resumen mensual (todos los meses reales están tipeados sin fórmula)** → Ariel: todos los valores se calculan en el software a partir de los datos (los movimientos de caja). No se muestra ningún valor tomado del Resumen de la planilla, tenga o no fórmula; la planilla queda solo como referencia para la comparación de paridad. Si una fila no se puede calcular desde los datos (no hay regla ratificada), no se inventa: queda sin valor y marcada, y lo reportás.
