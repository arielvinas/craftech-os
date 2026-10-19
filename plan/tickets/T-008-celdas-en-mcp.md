---
id: T-008
title: Contenido actual de las celdas en el servidor MCP: vista de solo lectura sobre la última lectura de cada pestaña
status: backlog
priority: high
lane: core
depends_on: []
effort: S
milestone: A
branch:
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
- [ ] Solo aparecen celdas de la última lectura de cada pestaña activa (test con dos lecturas y con una pestaña inactiva).
- [ ] Una búsqueda `texto ILIKE` sobre toda la vista, hecha como `mcp_reader`, termina por debajo de los 10 s con los datos locales actuales; el tiempo medido queda en `## Implementation`.
- [ ] `craftech://catalogo` lista `mcp.celdas` con los comentarios de la vista y de sus columnas.
- [ ] `mcp_writer` recibe un error de permisos al leer `mcp.celdas`.
- [ ] Las instrucciones del servidor y `docs/claude-desktop.md` mencionan la vista; el documento ya no da por hecho `/usr/local/bin/docker`.
- [ ] Ninguna celda de datos reales entra en tests, fixtures ni logs.

## Out of scope

- Interpretar el cashflow, los pagos o los ingresos: eso es de las etapas B y C.
- Versiones anteriores de las celdas (solo la última lectura).
- Herramientas MCP nuevas o cambios en las existentes.
- Mitigaciones nuevas contra instrucciones escondidas en celdas.
- Cambios en el worker, en la lectura o en la forma del JSON guardado.
