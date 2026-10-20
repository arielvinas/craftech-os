---
id: T-012
title: Fundings: esquema del tracker FUNDINGS e interpretación del bloque de AWS de Pagos y del tracker, con corte al 25/2/2026 y paridad
status: todo
priority: high
lane: core
depends_on: [T-011]
effort: M
milestone: B
branch: arielvinas/t-012-fundings
---

## Context

ADR-002, sección 4, reglas de funding (R28, R22 y R15) y riesgos ("FUNDINGS sin esquema de bloques ni grilla").

Decisiones de Ariel del 19-oct-2026: ADR-002 aprobado.

Pregunta abierta a Ro, que no bloquea: para el corte, ¿decide la columna de mes o la fecha de carga del hito? El supuesto del ADR, que se implementa así hasta que Ro conteste, es la columna de mes en Pagos y la fecha de carga en el tracker.

Verificado en el repo el 19-oct-2026:
- En `config/sources.yaml`, la planilla "FUNDINGS - Log de status [OFICIAL]" tiene:
  - FUNDINGS como pestaña CARGA, con encabezado "EMPRESA", clave A y sin bloques ni grilla;
  - "Pagos confirmados", "DB" y "SUMA" como pestañas DERIVADAS;
  - "2025" como HISTÓRICA.
- Los bloques de funding de Pagos se llaman distinto: "Funding de AWS confirmados" en Craftech y "Fundings de AWS" en SleakOps.
- Una regla de `plan/milestones.md`: un esquema nuevo en `sources.yaml` es un commit directo a main. Acá va dentro del ticket porque el intérprete depende de él, y en el mismo PR.

## Scope

**Dónde vive:**
- `config/sources.yaml`, la entrada de FUNDINGS
- `app/migrations/0011_fundings.sql`
- `interpret/fundings.py`
- tests

1. **Descubrir la estructura.** Leer la estructura del tracker en la planilla de prueba de Ariel y en la última lectura local (`mcp.celdas`): columnas de programa, oportunidad, fund claim ID, estado, monto, fechas de sign-off estimado y de carga. Escribir el esquema en `sources.yaml` y anotar en `## Implementation` qué columnas se usaron y por qué. Si la estructura no permite ubicar las columnas por encabezado, parar con `QUESTIONS:`.
2. **Migración 0011:**
   - Tabla `funding_milestone`, el hito de funding: origen (`pagos` o `tracker`), planilla, pestaña, `row_key`, programa y oportunidad como texto, fund claim ID, orden dentro del programa, si la clave es provisional, mes, monto en USD, estado, sign-off estimado, cobro estimado, fecha de carga, `snapshot_id`, `cell_ref` y `rules_version`.
   - Vistas `mcp.fundings` (cliente por alias) y `mcp.paridad_fundings`: por mes, la suma interpretada contra la pestaña "Pagos confirmados", con la diferencia.
   - `COMMENT ON` y `GRANT SELECT` a `mcp_reader`.
3. **Corte (regla R28).**
   - El bloque de AWS de Pagos de las dos planillas da hitos para las columnas de mes hasta febrero de 2026.
   - El tracker da hitos con fecha de carga desde el 25/2/2026.
   - La misma oportunidad en los dos lados abre `funding_duplicado` y se guardan los dos, sin deduplicar.
4. **Clave del hito.** Es el fund claim ID cuando existe; si no, programa + orden dentro del programa, marcada provisional.
5. **Cobro estimado (regla R22).** Es el sign-off estimado + 30 días.
6. **Funding separado (regla R15).** Ninguna vista suma fundings con facturas.
7. **Tests sintéticos:**
   - bloque de AWS con los dos nombres;
   - el corte en febrero y marzo de 2026;
   - un duplicado;
   - una clave provisional;
   - el cobro estimado;
   - la paridad en cero y distinta de cero.

**Descartado:**
- Deduplicar automáticamente: el ADR dice que el duplicado es un problema.
- Tabla `aws_program`: el programa va como texto hasta la etapa C.

## Acceptance criteria

- [ ] `config/sources.yaml` tiene el esquema de FUNDINGS y `craftech-os sources load` lo acepta.
- [ ] En la planilla de prueba, un hito cargado en el tracker aparece en `mcp.fundings` con origen `tracker`, cobro estimado = sign-off + 30 días y la celda de origen.
- [ ] Un funding en una columna de mes de enero de 2026 del bloque de AWS de Pagos aparece con origen `pagos`; uno en marzo de 2026 en ese bloque no genera hito por esa vía.
- [ ] La misma oportunidad en los dos lados abre `funding_duplicado` y las dos filas siguen en `mcp.fundings`.
- [ ] Con la planilla de prueba consistente, `mcp.paridad_fundings` da diferencia 0. Con las lecturas reales locales, la diferencia por mes queda en `## Implementation`.
- [ ] Ninguna vista de facturas incluye montos de funding.

## Out of scope

- Devengamiento del funding en dos vistas (regla R24, etapa C).
- Cargar el fund claim ID en la planilla: es de Ro, y el sistema nunca escribe en Sheets.
- Herramientas MCP (T-013) y pantallas (T-014).
