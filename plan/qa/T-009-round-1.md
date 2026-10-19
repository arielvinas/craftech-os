# QA T-009 — Ronda 1

**Verdict: PASS**
**Branch:** arielvinas/t-009-clientes-canonicos @ fe2aff8
**Gates:** typecheck — (el repo no tiene) · lint ✓ (`ruff check`) · formato ✓ (`ruff format --check`, 74 archivos) · tests ✓ (233 passed, 0 skipped, 21 s) · build ✓ (`docker build -f infra/Dockerfile`)
**Criteria:** 6/7 verificados localmente; el criterio 6 (pintar una celda vacía en la planilla de prueba real de Ariel) queda diferido a Post-merge, y el diferimiento es aceptable (ver "No verificado")
**Mutation:** 23 mutantes a mano sobre lo central (carga de Zoho, carga de aliases, vista `mcp.aliases`, permisos del rol de escritura del servidor MCP, trigger de auditoría, celdas pintadas vacías, filtro del diff): 20 muertos, 3 sobrevivientes (uno equivalente en la configuración actual; los otros dos son huecos de test menores, F4 y F5)

Entorno: contenedor propio `qa-t009-pg` (postgres 16, scripts de `infra/postgres-init`), con bases `craftech_test` (suite), `craftech` y `stagea`. Datos de prueba inventados en `/tmp/qa-t009/`. Nada se escribió en Google Sheets ni en Drive.

## Criterios

1. **Migración 0008 sobre una base existente** ✓ — base `stagea` migrada hasta 0007 con el código de `main` (`git archive main`), después `migrate` de la rama aplicó 0008; una segunda corrida dijo "nothing to apply". `legal_entity` tiene exactamente las dos razones sociales de Craftech (Craftech S.A./Argentina/bejerman y Craftech-io Inc./Estados Unidos/zoho).
2. **Carga del export de Zoho** ✓ — primera corrida: 9 leídas, 7 creadas, 2 actualizadas; segunda corrida idéntica: 0 creadas. "Due on receipt" da 0 días, "Net 7" da 7, "Net -5" y "Custom" caen al valor por defecto de 10 días. Una segunda razón social con el mismo Display Name queda bajo el mismo cliente. Textos con `<script>`, unicode y 1200 caracteres se guardan tal cual. Encabezados con BOM y en otra capitalización se leen bien.
3. **Carga de aliases decididos** ✓ — archivo con encabezados "Fuente,TEXTO,Cliente,Decidio,Motivo": 6 leídas, 5 creadas, 1 salteada, 1 cliente nuevo; una segunda corrida: 0 creadas, 6 salteadas. El cliente se resuelve también por razón social ("taxdup b inc" → cliente Taxdup A). Una fila con campos vacíos aborta con `error:` y número de línea, sin escribir nada. Una segunda decisión para el mismo texto cambia lo que muestra `mcp.aliases` y conserva la anterior (`decisiones_anteriores`). Archivo inexistente: `error: [Errno 2] ...` y salida 1.
4. **Vistas para el servidor MCP** ✓ — `mcp.clientes`, `mcp.razones_sociales` y `mcp.aliases` las lee el rol de lectura del servidor MCP y aparecen en el catálogo con comentario en cada columna (cubierto por `test_mcp`; los mutantes que quitan el permiso de lectura o un comentario de columna mueren). `mcp.aliases` muestra la decisión más reciente y cuántas decisiones anteriores hubo (mutantes de orden ascendente y de conteo mueren).
5. **El rol de escritura del servidor MCP solo puede insertar, y queda auditado** ✓ — INSERT en `client` y `client_alias` funciona y queda en la auditoría con la herramienta `vincular_alias`; UPDATE y DELETE fallan con permiso insuficiente. Mutantes que agregan UPDATE/DELETE, quitan el INSERT o disparan el trigger en DELETE mueren.
6. **Celda vacía pintada en la planilla de prueba real** — no verificado contra la planilla (ver "No verificado"); el equivalente local sí: en una pestaña CARGA con esquema la celda pintada vacía se guarda como `{c, bg}` y levanta `color_desconocido`; en una pestaña sin esquema se descarta; una fila hecha solo de celdas pintadas no se alinea ni genera altas o bajas en el diff.
7. **Sin datos de clientes en el repo ni en los logs** ✓ — los tests usan nombres inventados; los eventos `clients_loaded` y `aliases_loaded` guardan solo conteos (un mutante que mete un nombre en el evento muere); el diff contra `main` no contiene identificaciones fiscales, mails ni nombres reales.
Además (blast radius del cambio de celdas pintadas): **la primera lectura después del deploy no genera cambios espurios** ✓ (por lectura de `cell_changes`, `blocks`, `_align` y `detect.find`): celda antes ausente y ahora `{c, bg}` no genera cambio; celda con valor que pasa a `{c, bg}` sigue siendo "vaciada", como antes.

## Findings

### F1 [minor] Un plazo "Net" enorme tira un traceback y aborta toda la carga de Zoho
- **Repro:** 1. CSV de Zoho con una fila de Payment Terms "Net 99999999999" → 2. `craftech-os clients load-zoho <archivo>`.
- **Expected:** `error:` con la fila culpable y salida 1 (o la fila con el plazo por defecto de 10 días, como "Net -5").
- **Actual:** traceback de `psycopg.errors.NumericValueOutOfRange`; la transacción se revierte (no hay datos a medias), pero el mensaje no dice qué fila es. El límite del archivo (validación en la frontera) debería atajarlo en `payment_terms_days`.

### F2 [minor] Filas que chocan dentro del mismo export se pisan en cada corrida
- **Repro:** CSV con dos filas de la misma razón social normalizada ("Duplicada SA" / "duplicada sa") o con la misma identificación fiscal para dos empresas ("33-3" en Taxdup A y Taxdup B) → cargar dos veces el mismo archivo.
- **Expected:** la segunda corrida idéntica reporta 0 actualizadas, o la carga avisa del choque.
- **Actual:** la segunda corrida reporta "4 updated" y `updated_at` se mueve en cada corrida; la razón social de Taxdup B reemplaza en silencio la de Taxdup A bajo el cliente Taxdup A (la clave por identificación fiscal está documentada, pero nada avisa). Un export real de Zoho con duplicados quedaría oscilando sin que nadie se entere.

### F3 [minor] El campo `fuente` de los aliases no se normaliza ni se valida
- **Repro:** archivo de aliases con dos filas iguales salvo `fuente` "Pagos" y "pagos".
- **Actual:** quedan dos aliases distintos. No está definido qué es `fuente` (¿nombre de pestaña? ¿planilla más pestaña?), y las dos planillas de Facturación tienen una pestaña "Pagos", así que el nombre de pestaña solo es ambiguo. Conviene fijarlo antes de que T-010 consuma los aliases (pregunta de producto, sugerencia: planilla + pestaña, comparada con `normalize`).

### F4 [minor] Hueco de test: la búsqueda del cliente por razón social en la carga de aliases
- **Repro:** quitar `clients.setdefault(normalize(legal_name), client_id)` en `load_aliases` → la suite sigue verde.
- El comportamiento funciona (lo probé a mano, criterio 3), pero el test usa un cliente cuyo Display Name es igual a su razón social, así que no distingue. Falta un caso con nombres distintos.

### F5 [minor] Hueco de test: celda pintada en una pestaña CARGA sin esquema
- **Repro:** cambiar la consulta de `read_tab` a `SELECT schema IS NOT NULL ...` (sin la condición de clase CARGA) → la suite sigue verde.
- El test "se descarta en una sin esquema" usa la pestaña "Resumen", que no es CARGA, así que no cubre la combinación CARGA sin esquema. El mutante simétrico (quitar la condición de esquema) también sobrevive, pero es equivalente hoy: en `config/sources.yaml` todos los esquemas cuelgan de pestañas CARGA.

## Re-verificación de la ronda anterior
- No hay: es la primera ronda.

## No verificado
- **Criterio 6 contra la planilla real**: necesita pintar una celda en la planilla de prueba de Ariel y QA nunca escribe en Google Sheets. El diferimiento a Post-merge es aceptable: lo verificable localmente (guardado de `{c, bg}`, issue `color_desconocido`, descarte sin esquema, diff sin altas espurias) está probado y con mutantes muertos. Queda como prueba manual de Ariel después del merge.
- **Encabezados reales del export de Zoho**: probados con un CSV inventado con los nombres de columna que espera el código (display name, company name, payment terms, billing country, cf.codigo tax id, cf.tipo de tax id). Si el export real los nombra distinto, la carga no los encuentra; verificar con el primer export real.
- **Tamaño con rellenos decorativos**: pestañas reales con columnas enteras o bandas pintadas agrandarían el snapshot y el rango usado, y podrían levantar muchos `color_desconocido`. Solo se ve contra la planilla real; mirarlo en la misma prueba post-merge del criterio 6.

## Split-outs sugeridos (fuera del alcance)
- [producto] Definir el dominio de `fuente` en los aliases (planilla + pestaña) antes de T-010 — ver F3.

Harness de mutantes en `/tmp/qa-t009-harness/` (`mutants.sh` + `list.txt`; falla fuerte si falta un archivo o un patrón y revierte con `git checkout`).
