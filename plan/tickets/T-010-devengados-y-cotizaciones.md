---
id: T-010
title: Devengados y cotizaciones: módulo interpret con VENTAS y las filas de cotización de Pagos ARG, enganchado al worker
status: backlog
priority: high
lane: core
depends_on: [T-009]
effort: M
milestone: B
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
- [ ] Una fila con un cliente inventado sin alias abre `alias_sin_cliente`; después de cargar ese alias, el devengado muestra el cliente sin reinterpretar.
- [ ] `craftech-os interpret --all` corrido dos veces seguidas deja las mismas filas en `accrual` y `fx_rate` y no duplica problemas.
- [ ] Con las filas de cotización corridas en el fixture, las cotizaciones salen iguales. Con la MEP de control distinta de la operativa se abre `cotizacion_discrepante`.
- [ ] `system_event` registra los segundos por pestaña; en la base local con las lecturas actuales, ninguna pestaña supera los 10 segundos (el tiempo medido queda en `## Implementation`).
- [ ] Ningún log ni `details` de un problema contiene montos.

## Out of scope

- Facturas, cobros y bajas de Pagos y Pagos ARG (T-011); fundings (T-012).
- Herramientas MCP nuevas (T-013) y pantallas (T-014).
- Contratos, objetivos de venta (pregunta F-23) y el P&L de la etapa C.
