---
id: T-008
title: Contenido actual de las celdas en el servidor MCP: vista de solo lectura sobre la última lectura de cada pestaña
status: done
priority: high
lane: core
depends_on: []
effort: S
milestone: A
branch: feat/t-008-celdas-en-mcp
---

## Context

Bug de producto encontrado por Ariel el 19-oct-2026 al usar Claude Desktop: preguntó por los pagos a "Grego" en la planilla de cashflow y el conector respondió "solo tiene el historial de cambios de las celdas, no su contenido actual. En ese historial no aparece 'Grego'…". Ariel aprobó resolverlo con este ticket antes de diseñar la etapa B.

**Repro:**
1. En Claude Desktop, con el servidor craftech-os conectado, preguntar qué celdas contienen "Grego" en cualquier planilla.
2. Claude busca en `mcp.changes` y `mcp.snapshots` con `consultar_sql`.

**Expected:** Claude encuentra las celdas que hoy contienen ese texto y cita planilla › pestaña › celda y el momento de lectura.
**Actual:** no hay ninguna vista con el contenido. `mcp.snapshots` excluye la columna `content` por decisión de T-007 (`app/migrations/0006_mcp_roles_views.sql`), y `mcp.changes` solo tiene diferencias: `cell_change` está vacía hasta que haya ediciones posteriores a la importación inicial.

Verificado en la base local el 19-oct-2026:
- El contenido vive en `snapshot.content` (jsonb, ver `app/migrations/0002_snapshot.sql`). Su forma es `{used, title, merges, sheet_id, grid, hidden, rows}`; `rows` es un arreglo de `{r, cells}` y cada celda es `{c, bg, text, value, format}`, más `formula` cuando la celda tiene fórmula (40.715 de 291.410 celdas en las últimas 40 lecturas). `value` puede ser un objeto o un escalar: no asumir un objeto.
- Desplegar la última lectura de las 342 pestañas da 3.277.546 celdas en 979 ms. Una búsqueda `text ILIKE '%grego%'` sobre todas tarda 1,35 s y devuelve 165 celdas. El `statement_timeout` de `mcp_reader` es de 10 s: no hace falta materializar nada.
- `source_tab.active` marca las pestañas vigentes.
- `GRANT SELECT ON ALL TABLES IN SCHEMA mcp TO mcp_reader` en `0006` solo alcanzó a las vistas que existían entonces: una vista nueva necesita su propio `GRANT`.

Seguridad (ADR-001, sección de seguridad): el texto de las celdas llega a Claude Desktop, incluidos sueldos y datos de clientes. Esto ya era cierto para `mcp.changes` y Ariel lo aceptó: el chat sobre los datos es justamente el objetivo. Riesgo de instrucciones escondidas en celdas: la mitigación vigente (contenido siempre en campos estructurados del JSON, escrituras confirmadas por Claude Desktop) se mantiene sin cambios.

## Scope

**Dónde vive:** migración nueva `app/migrations/0007_mcp_cells.sql`, instrucciones del servidor en `app/craftech_os/mcp/server.py`, `docs/claude-desktop.md`, tests en `app/tests/test_mcp.py`.

1. **Vista `mcp.celdas`:** las celdas de la última lectura (`DISTINCT ON (source_tab_id) ... ORDER BY read_at DESC`) de cada pestaña activa, desplegando `content->'rows'` y `->'cells'`. Columnas, en español como el resto del esquema `mcp`: `planilla`, `pestaña`, `pestaña_id`, `lectura_id`, `leido_en`, `celda` (notación A1, por ejemplo `B7`, calculada desde fila y columna, columnas de más de una letra incluidas), `fila`, `columna` (números, base 1), `texto` (lo que se ve en la planilla), `valor` (el valor tal como está guardado en el JSON), `formula` (nula si no hay) y `color_fondo`. Verificar en el código de lectura si `r` y `c` son base 0 o base 1 antes de calcular A1.
2. **`COMMENT ON`** en español sobre la vista y cada columna: es el catálogo `craftech://catalogo`. El comentario de la vista dice que son celdas crudas de la última lectura, sin interpretar, y que conviene filtrar por planilla y pestaña.
3. **`GRANT SELECT ON mcp.celdas TO mcp_reader`.** `mcp_writer` no recibe nada.
4. **Instrucciones del servidor:** una frase que diga que el contenido actual de las planillas está en `mcp.celdas` y que se busca con `consultar_sql` (por ejemplo filtrando por planilla y pestaña y `texto ILIKE`).
5. **`docs/claude-desktop.md`:** reemplazar la ruta fija `/usr/local/bin/docker` por la instrucción de usar la salida de `which docker` (con Docker Desktop puede ser `/usr/local/bin/docker` o `~/.docker/bin/docker`, y el bloque de configuración lleva la ruta completa), y agregar una pregunta de ejemplo sobre contenido ("¿en qué celdas de CASH FLOW MENSUAL aparece tal proveedor?").
6. **Tests**, solo con datos sintéticos: una lectura con celdas conocidas (una con fórmula, una con columna de dos letras como `AA`) devuelve la fila esperada con su referencia A1; con dos lecturas de la misma pestaña solo aparece la más nueva; una pestaña inactiva no aparece; `mcp_reader` puede leer la vista; `mcp_writer` no puede.

**Descartado:** una tabla de celdas normalizada o una vista materializada (ADR-001 rechaza una fila por celda por versión; la medición muestra que la vista alcanza); una herramienta MCP nueva para buscar celdas (`consultar_sql` ya cubre la búsqueda y una herramienta más es otra superficie que mantener); exponer `snapshot.content` entero como columna (obligaría a Claude a desarmar el JSON y devolvería pestañas completas).

## Acceptance criteria

- [ ] Con `consultar_sql`, una búsqueda por texto sobre `mcp.celdas` devuelve la celda con `planilla`, `pestaña`, `celda` en notación A1 y `leido_en`; la referencia A1 coincide con la de Google Sheets para una celda conocida de la planilla de prueba de Ariel.
- [x] Solo aparecen celdas de la última lectura de cada pestaña activa (test con dos lecturas y con una pestaña inactiva).
- [x] Una búsqueda `texto ILIKE` sobre toda la vista, hecha como `mcp_reader`, termina por debajo de los 10 s con los datos locales actuales; el tiempo medido queda en `## Implementation`.
- [x] `craftech://catalogo` lista `mcp.celdas` con los comentarios de la vista y de sus columnas.
- [x] `mcp_writer` recibe un error de permisos al leer `mcp.celdas`.
- [x] Las instrucciones del servidor y `docs/claude-desktop.md` mencionan la vista; el documento ya no da por hecho `/usr/local/bin/docker`.
- [x] Ninguna celda de datos reales entra en tests, fixtures ni logs.

## Out of scope

- Interpretar el cashflow, los pagos o los ingresos: eso es de las etapas B y C.
- Versiones anteriores de las celdas (solo la última lectura).
- Herramientas MCP nuevas o cambios en las existentes.
- Mitigaciones nuevas contra instrucciones escondidas en celdas.
- Cambios en el worker, en la lectura o en la forma del JSON guardado.

## Implementation

- `app/migrations/0007_mcp_cells.sql`: vista `mcp.celdas` con las columnas del alcance, sus `COMMENT ON` en español y `GRANT SELECT ... TO mcp_reader` (nada para `mcp_writer`). La última lectura es `DISTINCT ON (source_tab_id) ... ORDER BY source_tab_id, read_at DESC, id DESC` (el `id` desempata dos lecturas con el mismo `read_at`); se une con `source_tab` filtrando `active`.
- `r` y `c` del JSON son base 0 (`app/craftech_os/ingest/document.py`, función `build`), igual que el `a1()` de `app/craftech_os/diff/compare.py` que usa `mcp.changes`. La letra de columna se calcula con un `CASE` en SQL de una, dos o tres letras (Google Sheets llega hasta la columna ZZZ, 18.278 columnas). Un test compara las 18.278 columnas contra `a1()` de Python: la equivalencia queda probada para todas, no muestreada.
- `valor`: en los datos locales (19-oct-2026, última lectura de cada pestaña) el valor es siempre un objeto `stringValue` / `numberValue` / `errorValue`, o `null` de JSON en celdas que solo tienen color. La vista convierte ese `null` de JSON en un NULL de SQL (`nullif`) para que `valor IS NULL` funcione; lo demás se devuelve tal cual (un escalar también pasaría intacto: lo cubre un test).
- `app/craftech_os/mcp/server.py`: una frase en las instrucciones del servidor que apunta a `mcp.celdas` y `consultar_sql`.
- `docs/claude-desktop.md`: `command` pasa a ser `<docker>`, con el paso `which docker` antes (y los dos lugares habituales en Docker Desktop); `mcp.celdas` descrita en `consultar_sql`; pregunta de prueba sobre contenido; requisitos dicen "las migraciones" en vez de solo la `0006`.
- `app/tests/test_db.py`: la lista de migraciones esperadas suma `0007`.
- **Tiempo medido** como `mcp_reader` con `statement_timeout = 10s`, sobre la base local (342 pestañas, 3.277.546 celdas), aplicando la `0007` dentro de una transacción que se deshizo: `SELECT count(*) FROM mcp.celdas WHERE texto ILIKE '%grego%'` → 165 celdas en 1.420 ms y 1.341 ms; `count(*)` de toda la vista 979 ms. Muy por debajo de los 10 s.
- Sin consultas al asesor. Sin dependencias nuevas.
- **Sin verificar**: que la referencia A1 coincida con Google Sheets para una celda conocida de la planilla de prueba de Ariel (no está en `config/sources.yaml` ni en la base local). Lo que sí está probado: la vista da la misma referencia que `a1()` de Python para todas las columnas posibles, y esa función es la que ya usan las celdas de `mcp.changes`. Tampoco probé Claude Desktop real (queda para Ariel tras aplicar la migración).

## Test plan

1. `uv run pytest app/tests/test_mcp.py`: `test_celdas_has_the_cells_of_the_last_read_with_their_a1_reference` (A1, B7 con fórmula, AA7, una celda solo color en C1, dos lecturas de la misma pestaña, una pestaña inactiva con el mismo texto, búsqueda `ILIKE`), `test_celdas_spells_every_sheets_column_like_google` (A..ZZZ), escritor sin permiso, catálogo con `mcp.celdas`, instrucciones.
2. Aplicar `0007` en la base local (ver Post-merge) y, como `mcp_reader`, `SELECT planilla, pestaña, celda, texto, leido_en FROM mcp.celdas WHERE texto ILIKE '%<texto conocido>%'` termina en menos de 10 s.
3. Para una celda conocida de una pestaña (idealmente de la planilla de prueba de Ariel, si se agrega), abrir Google Sheets y comparar la celda: misma referencia A1 y mismo texto mostrado.
4. Una celda con fórmula: `formula` trae la fórmula y `texto` el resultado mostrado.
5. Leer `craftech://catalogo` desde Claude Desktop: aparece `## mcp.celdas` con el comentario de la vista y de las 12 columnas.
6. Conectado como `mcp_writer`: `SELECT * FROM mcp.celdas` da `permission denied`.
7. En Claude Desktop: "¿en qué celdas de <pestaña> aparece <texto>?" → Claude usa `consultar_sql` sobre `mcp.celdas` y cita planilla › pestaña › celda y `leido_en`.
8. Pestaña que se renombró o se dio de baja (`active = false`): sus celdas no aparecen.

**Blast radius**: `server.py` solo cambió el texto de las instrucciones (ninguna herramienta). `test_db.py` lista una migración más. La vista no toca tablas: el worker, la web y las otras vistas no cambian. Puntos ciegos: todos los fixtures tienen `content->'rows'` presente o ausente entero (nunca `cells` ausente dentro de una fila: `build` no lo genera); los textos de prueba son cortos; nunca hay dos lecturas con el mismo `read_at` exacto (lo desempata el `id`, sin test).

## Post-merge

1. En `main`, con el stack levantado: `docker compose -f infra/docker-compose.yml run --rm app craftech-os migrate` (aplica `0007_mcp_cells.sql`; los usuarios `mcp_reader` y `mcp_writer` ya existen desde T-007). Verificar: `docker compose -f infra/docker-compose.yml exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT count(*) FROM mcp.celdas"'` devuelve unos 3,2 millones.
2. Reconstruir el contenedor web para que el servidor MCP tome las instrucciones nuevas: `docker compose -f infra/docker-compose.yml up -d --build web`, y reiniciar Claude Desktop.
3. Si `claude_desktop_config.json` usa una ruta de `docker` que ya no existe, reemplazarla por la salida de `which docker`.

