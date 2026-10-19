---
id: T-009
title: Clientes canónicos: razones sociales, clientes y aliases, con sus cargadores, y lectura que conserva celdas con solo color
status: done
priority: high
lane: core
depends_on: [T-008]
effort: M
milestone: B
branch: arielvinas/t-009-clientes-canonicos
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

- [x] `craftech-os migrate` aplica `0008` sobre una base con la etapa A, y `SELECT * FROM legal_entity` devuelve exactamente Craftech S.A. y Craftech-io Inc.
- [x] Con un CSV inventado de contactos de Zoho, `clients load-zoho` crea los clientes y razones sociales esperados. Una segunda corrida informa 0 creados. El log muestra solo cantidades.
- [x] Con un CSV inventado de aliases, `aliases load` crea los alias. Una segunda decisión para el mismo texto cambia lo que muestra `mcp.aliases` sin borrar la anterior.
- [x] Desde Claude Desktop, o con el rol `mcp_reader` en psql, `mcp.clientes`, `mcp.razones_sociales` y `mcp.aliases` se leen y aparecen en `craftech://catalogo` con sus comentarios.
- [x] `mcp_writer` puede hacer INSERT en `client` y `client_alias` (queda un registro de auditoría) y recibe error de permisos en UPDATE y DELETE.
- [ ] En la planilla de prueba de Ariel, una celda vacía pintada en una pestaña con esquema aparece en la lectura siguiente con su color, y un color fuera de la lista abre `color_desconocido`.
- [x] Ningún nombre real, tax ID ni archivo de `craftech-os-data` entra al repo, los tests o los logs.

## Out of scope

- Interpretar VENTAS, Pagos o FUNDINGS (T-010 a T-012).
- La herramienta MCP `vincular_alias` (T-013) y las pantallas web (T-014).
- Sincronizar con HubSpot o leer Zoho por API.
- Resolver la pregunta R32 de Emi sobre múltiples razones sociales: se modela de 1 a n igual.

## Implementation

- **Celdas con solo color** (commit `d3a9de9`).
  - `document.build(grid, keep_color_only)` guarda como `{c, bg}` las celdas vacías pintadas de un color distinto de blanco.
  - `importer.read_tab` lo activa solo para pestañas CARGA con esquema.
  - `diff/compare.py` no alinea, inserta ni borra filas hechas solo de celdas pintadas. Sin esto, pintar una fila vacía daría un `row_inserted`.
  - `issues/detect.py` ya toleraba celdas sin `value`, así que `color_desconocido` ve los colores nuevos.
  - Pintar o despintar una celda vacía **no** genera un cambio `color`: una celda ausente en un documento anterior a T-009 puede estar pintada, porque no se guardaba. Un cambio `color` necesita la celda en los dos documentos. CodeRabbit pidió lo contrario en la ronda 1 y se revirtió en la ronda 3 de QA (F1 de la ronda 2): la primera lectura después del deploy registraba cambios `color` falsos en cada celda vacía de una fila pintada. Queda anotado en `plan/improvements.md` para decidirlo después.
  - Las referencias de las fórmulas se corren contando solo las filas con valor (pedido de CodeRabbit en la ronda 1).
- **Migración `0008_clients.sql`.**
  - `legal_entity` tiene `billing_system` único (`bejerman` para Craftech S.A., `zoho` para Craftech-io Inc.).
  - `client_legal_entity.source_system` es una clave foránea a esa columna. Eso cumple el CHECK de valores y además dice qué sociedad de Craftech factura.
  - Índice único parcial `(source_system, tax_id)`.
  - `client_alias` solo recibe inserts y exige autor y motivo no vacíos.
  - Vistas `mcp.clientes`, `mcp.razones_sociales` y `mcp.aliases`, con la decisión vigente por fuente y texto (`ORDER BY created_at DESC, id DESC`) y `decisiones_anteriores`. Cada vista tiene su `GRANT SELECT` y todas las columnas comentadas.
  - `record_mcp_write()` se reemplaza para leer el autor con `to_jsonb(NEW)->>'author'`: `client` no tiene autor, así que su evento lleva la herramienta y el autor nulo.
  - Triggers con la herramienta `vincular_alias` en `client` y `client_alias`, y `GRANT INSERT` a `mcp_writer`. Las columnas identity no necesitan permiso sobre la secuencia; el test lo prueba.
- **`app/craftech_os/clients.py`.**
  - `load_zoho` y `load_aliases`, cada uno en una sola transacción.
  - Los encabezados se comparan normalizados con `diff.compare.normalize`, la misma función de `row_key`. El CSV se lee como `utf-8-sig` porque Zoho exporta con BOM.
  - Zoho:
    - La clave es el tax ID y, si no hay, la razón social normalizada.
    - Una fila igual a lo guardado cuenta como salteada; una distinta, como actualizada. Una fila sin nombre se saltea.
    - "Net N" son N días y "Due on Receipt" es 0. Cualquier otro plazo (vacío, "Custom") queda en 10: no se interpreta.
  - Aliases:
    - El texto se guarda normalizado.
    - El cliente se busca por nombre de fantasía o por razón social, normalizados; si no hay, se crea con el nombre dado.
    - Se saltea una decisión idéntica a una ya guardada.
    - Una fila sin algún campo frena toda la carga, con el número de línea y sin el contenido.
- **CLI.** `clients load-zoho <csv>` y `aliases load <csv>` imprimen y registran (`clients_loaded`, `aliases_loaded`) solo cantidades. `ClientsError` sale como `error:` con código 1.
- **README.** Nueva sección "Clientes y aliases": cómo montar `~/repos/craftech-os-data/` de solo lectura con `docker compose run -v` y las reglas de carga. También se actualizó la lista de tablas de `mcp_writer`.

## Test plan

- `tests/test_clients.py` (siete tests):
  - la siembra de `legal_entity`;
  - la carga de Zoho crea y luego saltea todo, y ni la salida ni los eventos contienen nombres ni tax IDs;
  - una actualización por tax ID y por razón social;
  - la carga de aliases es idempotente y crea el cliente que falta;
  - la decisión más reciente manda y la anterior queda contada;
  - una fila sin motivo no carga nada;
  - un CSV sin columnas falla.
- `tests/test_mcp.py`:
  - `mcp_writer` inserta en `client` y `client_alias` y quedan dos eventos `mcp_write`;
  - UPDATE y DELETE en `client` y `client_alias`, y cualquier escritura en `client_legal_entity`, dan `InsufficientPrivilege`;
  - `mcp_reader` lee las tres vistas, y el catálogo las lista con comentarios en todas sus columnas.
- `tests/test_document.py` y `tests/test_diff_store.py`:
  - una celda pintada se conserva solo en CARGA con esquema y abre `color_desconocido`;
  - una fila solo pintada no genera cambios.
- `tests/test_diff_compare.py`: la misma grilla leída como en la etapa A y como en T-009 da 0 cambios, en los dos sentidos, con esquema, sin esquema y con esquema sin fila de encabezado (comparación por posición).
- `tests/test_db.py`: las tablas y migraciones nuevas.
- Mutaciones, cada una pone la suite en rojo:
  - ordenar los aliases de forma ascendente;
  - apagar `keep_color_only`;
  - contar como `color` el paso de una celda ausente a una pintada;
  - no saltear las decisiones repetidas.
- Prueba de humo: el CLI real contra la base de prueba con CSVs inventados en `/tmp`, dos corridas de cada carga y un archivo que no existe.
- **Alcance del cambio:**
  - El reemplazo de `record_mcp_write()` toca la auditoría de las tres herramientas existentes; sus tests siguen en verde.
  - El hash de las pestañas CARGA con esquema cambia una vez en la primera lectura después del deploy, y eso no genera cambios espurios.
  - Las demás pestañas no cambian.

## Post-merge

1. Ariel exporta a `~/repos/craftech-os-data/` el `Contacts.csv` de Zoho Books y el CSV con las 51 decisiones del artefacto de Aliases.
2. `craftech-os clients load-zoho /data/Contacts.csv` y `craftech-os aliases load /data/aliases.csv`, dentro del contenedor como indica el paso 4. Verificar con las cantidades que informan, y con `SELECT count(*)` en `mcp.clientes` y `mcp.aliases`.
3. Si los encabezados reales del CSV de Zoho difieren de los supuestos, ajustar el mapeo en un commit chico antes de cargar.
4. Los comandos corren en el contenedor con la carpeta montada: `docker compose -f infra/docker-compose.yml run --rm -v ~/repos/craftech-os-data:/data:ro app <comando del paso 2>`; la carpeta queda en `/data` (ver la sección "Clientes y aliases" del README).
5. Cargar Zoho antes que los aliases. Zoho nombra cada cliente con su Display Name, que es la razón social. En el CSV de aliases, la columna `cliente` tiene que coincidir, normalizada, con esa razón social o con un nombre ya cargado. Si trae un nombre de fantasía distinto, se crea un cliente aparte. Revisar `mcp.clientes` después de la carga: si hay duplicados, hace falta decidir cómo unir el nombre de fantasía con la razón social.
6. Criterio pendiente: en la planilla de prueba, pintar una celda vacía en una pestaña con esquema y verificar en la lectura siguiente su color en `mcp.celdas`. Un color fuera de la lista tiene que abrir `color_desconocido`.
