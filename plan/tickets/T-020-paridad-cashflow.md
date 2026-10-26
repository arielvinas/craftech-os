---
id: T-020
title: Paridad del cashflow recalculado contra el Resumen
status: in-progress
priority: medium
lane: core
depends_on: [T-019]
effort: S
milestone: C
branch: arielvinas/t-020-paridad-cashflow
---

## Context

Tercer ticket de la caja (`plan/adr/ADR-003-caja-desde-movimientos.md`, aprobado por Ariel el 25-oct-2026). Compara lo que recalculamos desde los movimientos con lo que dice el Resumen de Finanzas, celda por celda, para ver dónde no coinciden.

Decisiones del documento de arquitectura (ADR-003):
- Solo se comparan las celdas `recalculada` contra la misma fila y mes del Resumen, en la unidad de la fila. De las `importada` solo se informa cuántas hay (compararlas consigo mismas no dice nada).
- Las diferencias se muestran, no se corrigen.
- La tolerancia propuesta es una unidad de la fila (mil pesos o un dólar). No está ratificada: es pregunta abierta para Emi y Ro.

Verificado en el repo el 25-oct-2026:
- Las paridades que ya existen (`mcp.paridad_fundings` y `mcp.paridad_fundings_aws`, migración 0012) tienen `total_planilla`, `suma_fundings` y `diferencia`, y `GRANT SELECT` solo a `mcp_reader`. Esta sigue el mismo patrón.
- T-019 deja la migración 0015; esta es la 0016.

## Scope

**Dónde vive:**
- `app/migrations/0016_paridad_cashflow.sql`.
- `app/tests/`.

1. **`mcp.paridad_cashflow`.** Por bloque, fila y mes de las celdas `recalculada`: valor recalculado, valor del Resumen, diferencia, unidad, planilla, pestaña y celda, y si la diferencia supera la tolerancia propuesta.
2. **Resumen de cobertura.** Por mes (o en una vista hermana), cuántas celdas son `recalculada`, cuántas `importada` y cuántas `parametro`.
3. `GRANT SELECT` a `mcp_reader`, ninguno a `mcp_writer`, y `COMMENT ON` en castellano que diga que la tolerancia es propuesta.

**Descartado:**
- Corregir o reemplazar valores del Resumen cuando hay diferencia.
- Comparar las celdas `importada`.

## Acceptance criteria

- [ ] Con datos sintéticos, una celda `recalculada` igual al Resumen da diferencia 0; una distinta da la diferencia correcta en la unidad de la fila y la marca de fuera de tolerancia cuando la supera.
- [ ] Las celdas `importada` y `parametro` no aparecen en la comparación, pero sí en la cantidad por mes.
- [ ] `mcp_reader` puede leer la vista; `mcp_writer` no.
- [ ] Los tests usan solo datos sintéticos.

## Out of scope

- La pantalla (T-021 muestra la tabla; un bloque de paridad en `/caja` puede venir después).
- Ratificar la tolerancia (Emi y Ro).

## Decisions

- 2026-10-26 — **El ticket supone celdas con origen importada (valores tomados del Resumen); ¿siguen existiendo?** → No. Decisión de Ariel en T-019 (26-oct-2026): todo valor se calcula desde los movimientos y nunca se muestra un valor del Resumen, tenga o no fórmula. Seguir la nota agregada a plan/adr/ADR-003-caja-desde-movimientos.md: orígenes recalculada, sin_regla o parametro; las celdas sin regla quedan sin valor y con motivo, sin rayado; la planilla es solo referencia de paridad (recalculada contra cashflow_sheet_cell). Actualizar el ticket en consecuencia.
