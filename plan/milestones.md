# Milestones de Craftech OS

Las etapas vienen de `docs/03-proposal.md`, sección 6, ajustadas por `plan/adr/ADR-001-espejo-de-planillas-en-postgres.md`.

| Milestone | Nombre | Entregable | Tickets | Estado |
|---|---|---|---|---|
| A | Espejo | Importación inicial de las 20 planillas, lectura continua, cambios celda a celda con quién y cuándo, problemas básicos, web (Cambios, Problemas, Fuentes), servidor MCP mínimo | T-001 … T-008 | done (18-oct-2026; T-008 sumó las celdas actuales al servidor MCP) |
| B | Ingresos y servidor MCP completo | Devengados, facturas por color, cobros, fundings, clientes canónicos con aliases; pantallas Facturas y cobros, Fundings, Clientes | se cortan con `/ticket` sobre `plan/adr/ADR-002-ingresos-como-proyeccion-de-lecturas.md` (T-009 … T-014 sugeridos) | ADR-002 propuesto (19-oct-2026) |
| C | Gastos, sueldos, budget y paridad | Movimientos bancarios, nómina, budget; P&L y cashflow regenerados; tablero de paridad | T-018 … T-021 (caja desde movimientos, `plan/adr/ADR-003-caja-desde-movimientos.md`); nómina, budget y resultado se cortan después | T-018 y T-019 hechos (26-oct-2026); T-020 y T-021 en curso |
| D | Hosting y Finanzas adentro | AWS, login, Emi y Ro, Slack, alertas, rotación de la clave | — | — |

## Reglas de carriles de este proyecto

- Los archivos de migración (`app/migrations/NNNN_*.sql`) se numeran en orden y solo los crea el carril `core`, que es secuencial: un ticket de `core` activo a la vez.
- Un ticket de `ui` no agrega migraciones. Un ticket de `api` solo agrega una migración si ningún ticket de `core` está activo (T-007 lo cumple: depende de T-005, el último `core` de la etapa A).
- `config/sources.yaml` lo tocan T-001, T-002 y T-004 (todos `core`, secuenciales); agregar un esquema de pestaña después es un commit directo en `main`, no un ticket.
- Nada de datos reales (clientes, sueldos, valores de celdas) en tests, fixtures, logs, capturas de QA ni en el repo. Las pruebas en vivo se hacen sobre una planilla de prueba propia de Ariel, nunca sobre las de Finanzas.
