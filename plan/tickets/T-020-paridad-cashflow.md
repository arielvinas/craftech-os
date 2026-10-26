---
id: T-020
title: Paridad del cashflow recalculado contra el Resumen
status: done
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
- Solo se comparan las celdas `recalculada` contra la misma fila y mes del Resumen, en la unidad de la fila. De las `sin_regla` y `parametro` solo se informa cuántas hay por mes (no tienen valor). (El ADR decía `importada`; ese origen ya no existe, ver Decisions.)
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
2. **Resumen de cobertura.** Por mes (o en una vista hermana), cuántas celdas son `recalculada`, cuántas `sin_regla` y cuántas `parametro` (el origen `importada` ya no existe; ver Decisions).
3. `GRANT SELECT` a `mcp_reader`, ninguno a `mcp_writer`, y `COMMENT ON` en castellano que diga que la tolerancia es propuesta.

**Descartado:**
- Corregir o reemplazar valores del Resumen cuando hay diferencia.
- Comparar las celdas `sin_regla` y `parametro` (no tienen valor).

## Acceptance criteria

Ajustados el 2026-10-26 según la sección Decisions: el origen `importada` pasó a ser `sin_regla`.

- [x] Con datos sintéticos, una celda `recalculada` igual al Resumen da diferencia 0; una distinta da la diferencia correcta en la unidad de la fila y la marca de fuera de tolerancia cuando la supera (`test_the_parity_compares_recalculated_cells_with_the_resumen`).
- [x] Las celdas `sin_regla` y `parametro` no aparecen en la comparación, pero sí en la cantidad por mes (`test_only_recalculated_cells_are_compared_and_the_rest_are_counted`).
- [x] `mcp_reader` puede leer las dos vistas; `mcp_writer` no (`test_the_reader_reads_the_parity_views_and_the_writer_does_not`).
- [x] Los tests usan solo datos sintéticos.

## Out of scope

- La pantalla (T-021 muestra la tabla; un bloque de paridad en `/caja` puede venir después).
- Ratificar la tolerancia (Emi y Ro).

## Decisions

- 2026-10-26 — **El ticket supone celdas con origen importada (valores tomados del Resumen); ¿siguen existiendo?** → No. Decisión de Ariel en T-019 (26-oct-2026): todo valor se calcula desde los movimientos y nunca se muestra un valor del Resumen, tenga o no fórmula. Seguir la nota agregada a plan/adr/ADR-003-caja-desde-movimientos.md: orígenes recalculada, sin_regla o parametro; las celdas sin regla quedan sin valor y con motivo, sin rayado; la planilla es solo referencia de paridad (recalculada contra cashflow_sheet_cell). Actualizar el ticket en consecuencia.

## Implementation

- `app/migrations/0016_paridad_cashflow.sql`:
  - `mcp.paridad_cashflow`: cada celda `recalculada` de `mcp.caja_mensual` junto a la celda de la misma fila y mes en `cashflow_sheet_cell`. Columnas: bloque, fila, mes, periodo, `valor_recalculado`, `valor_resumen`, `diferencia`, unidad, `tolerancia`, `fuera_de_tolerancia`, planilla, pestaña, celda y lectura.
  - `diferencia` = Resumen − recalculado, redondeada al centavo, igual que `mcp.paridad_fundings_aws`. Una celda vacía del Resumen cuenta como 0.
  - Una fila de la configuración que no está en el Resumen aparece igual (cruce `LEFT JOIN`), con `en_resumen` falso y el Resumen contado como 0, para que `mcp.cobertura_cashflow` y la paridad cuenten las mismas celdas (hallazgo F1 de QA y CodeRabbit en el PR #20).
  - `tolerancia`: 1.000 en las filas en pesos y 1 en las filas en dólares. Los valores en pesos están en la misma escala que la planilla, así que «mil pesos» es 1.000. `fuera_de_tolerancia` = |diferencia| > tolerancia. El `COMMENT ON` dice que es propuesta y que la ratifican Emi y Ro.
  - El mes en curso también se compara (es `recalculada`). Se distingue con `periodo` = `en_curso`, porque es esperable que no coincida.
  - `mcp.cobertura_cashflow` (vista hermana): por mes y periodo, cuántas celdas `recalculadas`, `sin_regla` y `parametro` hay.
  - `GRANT SELECT` de las dos vistas solo a `mcp_reader`.
- `app/tests/test_cashflow.py`: tres tests con un Resumen sintético propio. `app/tests/test_db.py`: la 0016 en la lista de migraciones.
- No toqué el catálogo de `app/craftech_os/mcp/server.py`; T-019 tampoco agregó ahí las vistas de caja.

**Prueba de humo** (copia de la base de desarrollo del 2026-10-26, ya borrada; solo cantidades):
- 507 celdas comparadas. 19 tienen diferencia 0, 30 tienen la celda del Resumen vacía y 488 quedan fuera de la tolerancia propuesta.
- Meses reales dentro de la tolerancia: Argentina 2 % (228 celdas) y Craftech Inc. 6 % (266 celdas).
- Cobertura: 53 meses, con 507 celdas recalculadas, 882 sin regla y 42 de parámetro. Son las 1.431 celdas de `cashflow_cell`.
- Cada vista tarda menos de 0,3 s.

## Test plan

- `uv run pytest -q`: pasan 353. También pasan `ruff check`, `ruff format --check` y `uv build`.
- Mutaciones (todas hacen fallar la suite): sin el filtro `recalculada`, tolerancia en pesos de 1, `>=` en lugar de `>`, diferencia sin `coalesce`, cobertura sin el mes proyectado y `GRANT` sin la vista de paridad. Sin la migración, fallan los tres tests.
- Casos para QA:
  - `SELECT * FROM mcp.paridad_cashflow WHERE periodo = 'proyectado'` → vacío.
  - En `mcp.cobertura_cashflow`, la suma de las tres columnas da igual a `count(*)` de `mcp.caja_mensual` por mes.
  - Los meses proyectados tienen 0 recalculadas y 3 de parámetro.
  - Ninguna celda `sin_regla` o `parametro` aparece en `mcp.paridad_cashflow`.
  - Una celda del Resumen vacía da `valor_resumen` nulo y una diferencia igual a −recalculado.
  - Una diferencia de exactamente 1 dólar no queda fuera de tolerancia; una de 1,01 sí.
  - `mcp_writer` recibe «permission denied» en las dos vistas.
- Puntos ciegos: ningún fixture tiene una fila con `sign` −1 en la paridad. Solo hay un Resumen y una lectura, y nunca se lee la pestaña dos veces durante la paridad. Ningún valor del Resumen tiene decimales.
- Alcance del cambio: solo vistas nuevas, nada que ya existía cambia. T-021 puede leer `mcp.paridad_cashflow` si más adelante suma un bloque de paridad.

## Post-merge

1. En la base de desarrollo: `craftech-os migrate` (aplica la 0016). Para verificar, `SELECT count(*) FROM mcp.paridad_cashflow` tiene que dar unas 500 filas.
2. Llevar a Emi y Ro la tolerancia propuesta. Con una unidad de la fila, el 94 % de las celdas reales quedan fuera: mostrar la tabla junto con las reglas de filas pendientes de T-019.

