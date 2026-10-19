---
id: T-009
title: Clientes canónicos: razones sociales, clientes y aliases, con sus cargadores, y lectura que conserva celdas con solo color
status: backlog
priority: high
lane: core
depends_on: [T-008]
effort: M
milestone: B
---

## Context

Primer ticket de la etapa B ("Ingresos y servidor MCP completo"). La verdad es `plan/adr/ADR-002-ingresos-como-proyeccion-de-lecturas.md`, secciones 2, 5, 6 y 7, más la sección de seguridad. Los hechos de ingresos de T-010 a T-012 no llevan `client_id`: el cliente se resuelve en las vistas cruzando con `client_alias`. Por eso este ticket va primero.

Decisiones de Ariel del 19-oct-2026:
- ADR-002 aprobado; los tickets T-009 a T-014 lo citan como la verdad de la etapa B.
- La carpeta `~/repos/craftech-os-data/` todavía no existe. El ticket se prueba con nombres inventados y la carga real va en `## Post-merge`; el ticket no se bloquea por los archivos.

Verificado en el repo el 19-oct-2026:
- La última migración es `app/migrations/0007_mcp_cells.sql`, así que esta es la `0008`.
- `app/craftech_os/ingest/document.py`, función `_cell`: devuelve `None` si la celda no tiene `effectiveValue`, `formattedValue` ni `userEnteredValue`. Por eso hoy se pierden las celdas vacías que solo tienen color de fondo. `plan/improvements.md` lo anota (QA de T-004: `color_desconocido` nunca ve `#c9daf8` ni `#d0e0e3`, pregunta F-05).
- Hay pestañas CARGA con esquema en `config/sources.yaml`: Pagos, Pagos ARG y VENTAS de las dos planillas de Facturación, y FUNDINGS.
- `mcp_writer` hoy tiene INSERT en `issue_resolution`, `annotation` y `editor_profile`, auditados por el trigger `record_mcp_write` (`app/migrations/0006_mcp_roles_views.sql`). `GRANT SELECT ON ALL TABLES IN SCHEMA mcp` solo alcanzó a las vistas de ese momento, así que cada vista nueva necesita su propio `GRANT` (lo aprendido en T-008).
- Los comandos de la CLI se registran como `cmd_*` con subparsers de argparse en `app/craftech_os/cli.py`.

## Scope

**Dónde vive:**
- `app/migrations/0008_clients.sql`
- un módulo `app/craftech_os/clients.py` (o `clients/`)
- `cli.py`
- `ingest/document.py`
- tests en `app/tests/`

1. **Migración 0008.** Tablas en inglés con `COMMENT ON` en español y enumeraciones por CHECK, como en `0004`:
   - `legal_entity`, sembrada con dos filas: Craftech S.A. (Argentina) y Craftech-io Inc. Son de Craftech, no datos de clientes.
   - `client`: nombre de fantasía e id de HubSpot opcional.
   - `client_legal_entity`, de 1 a n: razón social, país, tipo y número de tax ID, sistema de origen (`bejerman` o `zoho`) y plazo de pago en días (por defecto 10).
   - `client_alias`: fuente o pestaña, texto normalizado, cliente, quién decidió, cuándo y motivo. Solo se agregan filas y la última decisión para el mismo texto y fuente es la que manda.

   La normalización del texto es la misma que usa `row_key` en la etapa A (reutilizar la función, no copiarla).
2. **Vistas MCP** `mcp.clientes`, `mcp.razones_sociales` y `mcp.aliases`. Las de aliases muestran solo la decisión vigente, más una columna con la cantidad de decisiones anteriores. Columnas en español con `COMMENT ON`, `GRANT SELECT` a `mcp_reader`.
3. **Permiso de escritura para T-013.** `GRANT INSERT ON client, client_alias TO mcp_writer` (más el uso de las secuencias) y el trigger `record_mcp_write` en las dos tablas. Ningún UPDATE ni DELETE para roles MCP. La herramienta en sí es de T-013; el permiso va acá porque este carril es el único que crea migraciones.
4. **`craftech-os clients load-zoho <Contacts.csv>`.**
   - Crea o actualiza clientes y razones sociales desde el export de contactos de Zoho Books.
   - Es idempotente: correrlo dos veces no duplica nada. La clave natural es el tax ID; si no hay, la razón social normalizada.
   - El plazo de pago sale de "Payment Terms" (Net 10 son 10 días y Due on Receipt son 0).
   - Las columnas que usa se verifican contra el CSV real en el post-merge; el test usa un CSV inventado con esos encabezados.
5. **`craftech-os aliases load <csv>`.**
   - Columnas: fuente, texto, cliente, decidió, motivo.
   - Un cliente que no existe se crea por nombre de fantasía.
   - Volver a cargar el mismo archivo no agrega filas repetidas.
6. **Reglas comunes a los dos cargadores.** Leen desde cualquier ruta, pero la documentada es `~/repos/craftech-os-data/`. En logs y en `system_event` registran solo cantidades (leídas, creadas, actualizadas, salteadas), nunca nombres ni tax IDs.
7. **Lectura de celdas con solo color.** En pestañas CARGA con esquema, `document.build` conserva las celdas sin valor que tienen un fondo distinto de blanco o vacío. Se guardan como `{c, bg}`, sin `value` ni `text`.
   - Las demás pestañas no cambian.
   - El hash de cada pestaña afectada cambia una sola vez, y eso está bien.
   - Revisar que `diff/compare.py` y `issues/detect.py` toleren celdas sin `value`; con esto `color_desconocido` ya ve los colores de las celdas vacías.
8. **Tests, solo con datos sintéticos:**
   - siembra de `legal_entity`;
   - las dos cargas, idempotentes;
   - la última decisión de alias es la que manda;
   - `mcp_writer` puede insertar en `client_alias` y la escritura queda auditada;
   - `mcp_writer` recibe un error al hacer UPDATE o DELETE;
   - una celda con solo color se conserva en una pestaña con esquema y se descarta en una sin esquema.

**Descartado:**
- Aliases en un YAML del repo: son datos de clientes.
- Escribir `client_id` en los hechos: ADR-002, alternativas descartadas.
- Que el worker lea el artefacto de Aliases: el ADR lo prohíbe; las 51 decisiones entran por CSV.

## Acceptance criteria

- [ ] `craftech-os migrate` aplica `0008` sobre una base con la etapa A, y `SELECT * FROM legal_entity` devuelve exactamente Craftech S.A. y Craftech-io Inc.
- [ ] Con un CSV inventado de contactos de Zoho, `clients load-zoho` crea los clientes y razones sociales esperados. Una segunda corrida informa 0 creados. El log muestra solo cantidades.
- [ ] Con un CSV inventado de aliases, `aliases load` crea los alias. Una segunda decisión para el mismo texto cambia lo que muestra `mcp.aliases` sin borrar la anterior.
- [ ] Desde Claude Desktop, o con el rol `mcp_reader` en psql, `mcp.clientes`, `mcp.razones_sociales` y `mcp.aliases` se leen y aparecen en `craftech://catalogo` con sus comentarios.
- [ ] `mcp_writer` puede hacer INSERT en `client` y `client_alias` (queda un registro de auditoría) y recibe error de permisos en UPDATE y DELETE.
- [ ] En la planilla de prueba de Ariel, una celda vacía pintada en una pestaña con esquema aparece en la lectura siguiente con su color, y un color fuera de la lista abre `color_desconocido`.
- [ ] Ningún nombre real, tax ID ni archivo de `craftech-os-data` entra al repo, los tests o los logs.

## Out of scope

- Interpretar VENTAS, Pagos o FUNDINGS (T-010 a T-012).
- La herramienta MCP `vincular_alias` (T-013) y las pantallas web (T-014).
- Sincronizar con HubSpot o leer Zoho por API.
- Resolver la pregunta R32 de Emi sobre múltiples razones sociales: se modela de 1 a n igual.

## Post-merge

1. Ariel exporta a `~/repos/craftech-os-data/` el `Contacts.csv` de Zoho Books y el CSV con las 51 decisiones del artefacto de Aliases.
2. `craftech-os clients load-zoho ~/repos/craftech-os-data/Contacts.csv` y `craftech-os aliases load ~/repos/craftech-os-data/aliases.csv`. Verificar con las cantidades que informan, y con `SELECT count(*)` en `mcp.clientes` y `mcp.aliases`.
3. Si los encabezados reales del CSV de Zoho difieren de los supuestos, ajustar el mapeo en un commit chico antes de cargar.
