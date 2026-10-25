# QA T-018 — Ronda 1

**Verdict: PASS**
**Branch:** arielvinas/t-018-movimientos-de-caja @ 31f34d1
**Gates:** typecheck — (el repo no tiene verificador de tipos) · lint ✓ (`ruff check`, `ruff format --check`: 56 archivos) · tests ✓ (337 passed) · build ✓ (`uv build`)
**Criteria:** 11/13 verificados; los criterios 11 y 12 piden contenido en la descripción del pedido de cambios, que todavía no existe (ver "No verificado")
**Mutation:** 15 mutantes a mano sobre el intérprete, el registro, la migración y la web → los 15 muertos, suite roja en cada uno ✓

## Cómo se probó

- Suite completa contra la base de tests (`*_test`) y 16 tests nuevos de `app/tests/test_consolidado.py` revisados uno por uno contra los criterios.
- Datos reales, **solo lectura**: se corrió la función pura `interpret` sobre la última lectura guardada de Consolidado (snapshot 1850) en la base local, sin escribir nada. Nada de esos datos entra a este reporte salvo conteos.
- Sondas adversariales con lecturas sintéticas en un archivo de tests descartable (ya borrado).
- Web de esta rama levantada en el puerto 8018 contra la base de tests, `/problemas` filtrado por los tres tipos nuevos, capturas en escritorio y 375 px.

## Criterios

1. Migración 0014 con `COMMENT ON` en castellano y rechazo de «01. Sueldos» con detalle: ✓. Leí cada comentario; el mutante que saca la restricción `cash_movement_sueldos_without_detail` muere.
2. `issue_issue_type_check` y `ISSUE_TYPES` con los tres tipos: ✓. En la web, `/problemas?tipo=<cada tipo nuevo>` responde 200 con el tipo seleccionado; un tipo inventado responde 400. Capturas: `evidence/T-018-r1-problemas-filtro.png`, `evidence/T-018-r1-problemas-375.png`.
3. Un movimiento por fila con todos los campos: ✓. Con datos reales: 21.534 movimientos y 6 montos nulos (celdas vacías).
4. Bancos por entidad, históricos y ajustes: ✓. Datos reales: S.A. 11.183, Inc. 9.796, ajuste 428, histórico 127, ninguno desconocido.
5. Banco desconocido → `cash_unknown_bank` y fila sin entidad: ✓. Probado también con un banco `<script>`, con uno de 5000 caracteres y con unicode: se guardan y se reportan sin romper nada.
6. Otros encabezados → `cash_header_mismatch`, sin tocar los movimientos anteriores ni insertar filas: ✓. Una columna 18 extra también da mismatch. Encabezados en minúscula se aceptan, porque la comparación normaliza, lo cual es razonable.
7. Rubro sin regla → `cash_unmapped_rubro`: ✓. Datos reales: 14 rubros sin regla, la misma lista que la tabla del ticket.
8. Sueldos sin Detalle/Subdetalle/Equipo y nada de eso en `issue.details` ni en `system_event.details`: ✓ por la vía del rubro. Datos reales: 0 filas de sueldos con detalle. Hay un hueco en la vía de Tipo Mov, ver F1.
9. La pestaña DERIVADA Consolidado de «Budget por Area 2026 - Final» no se interpreta: ✓ (`ONLY_IN` más `interpreter(title, name)`; el mutante que ignora `ONLY_IN` muere).
10. Una segunda lectura reemplaza los movimientos: ✓. Una lectura con encabezado y sin filas deja 0 movimientos.
11. Evento con `duration_ms` y cantidades, sin montos: la parte de código está ✓ (busqué montos en `system_event.details` y no aparece ninguno; el mutante que saca `movements` muere). La parte que va en la descripción del pedido de cambios queda pendiente: el dato ya está en `## Implementation` del ticket.
12. `cashflow_rows.yaml` sin montos: ✓ (solo etiquetas). Listar las filas sin regla en la descripción del pedido de cambios queda pendiente, igual que el criterio 11.
13. Tests con datos sintéticos: ✓. Revisé fixtures y tests nuevos: no tienen nombres, clientes ni montos reales.

## Findings

### F1 [minor] Tipo Mov «sueldos» en minúscula no oculta el detalle si el rubro no es «01. Sueldos»
- **Dónde:** `app/craftech_os/interpret/consolidado.py:123`. El rubro se compara normalizado (`normalize(rubro) == normalize(SUELDOS)`), pero el Tipo Mov se compara exacto (`movement_type == "Sueldos"`).
- **Repro:** lectura sintética con una fila de Tipo Mov `sueldos`, rubro `CCSS` y Detalle con un nombre sintético.
- **Expected:** Detalle, Subdetalle y Equipo nulos, como en cualquier fila de sueldos. **Actual:** el nombre queda guardado en `cash_movement.detalle`. `movement_type` queda nulo, se abre `fila_sin_interpretar`, y la restricción de la base no lo ataja porque mira `movement_type = 'Sueldos'`.
- **Por qué minor y no major:** en los datos reales esto pasa 0 veces (todas las filas de sueldos traen el Tipo Mov exacto o el rubro «01. Sueldos»), y el texto no sale en `issue.details` ni en eventos, solo en la tabla. Igual es un hueco de privacidad latente: con una normalización en la comparación del Tipo Mov se cierra.

### F2 [minor] Los comentarios de la base dicen que `cash_unmapped_rubro` mira el agrupador, pero el código solo mira el rubro
- **Dónde:** `app/migrations/0014_cash_movement.sql:68-70` («rubro o agrupador … que ninguna regla nombra»; stable_key «pestaña + rubro (+ agrupador, si alguna regla nombra el rubro)») y `config/cashflow_rows.yaml:4`, que describe una clave `agrupadores` que ninguna regla usa y que el código no lee.
- **Expected:** el comentario, que es lo que lee Claude Desktop vía MCP, describe lo que pasa. **Actual:** la clave es solo pestaña + rubro y no se abre ningún problema por agrupador. La regla de CCSS existe solo como comentario del YAML (línea 9).
- **Simplificación:** sacar del comentario y del encabezado del YAML la mención al agrupador hasta que haya una regla que lo use.

### F3 [nit] La transferencia Mercury→Mesh se reconoce solo con el texto exacto
- `MESH_TRANSFER = ("MERCURY", "CAJA. Mesh", "MESH")` (línea 51) se compara sin normalizar, así que «Mercury» o «CAJA. MESH» no salen como `Interno`. Los datos reales usan exactamente ese texto (135 filas Interno). Es inconsistente con el resto del intérprete, que sí normaliza los bancos.

### F4 [nit] Celda con valor vacío explícito llega como texto `{"stringValue": ""}` (preexistente)
- Una celda con `formattedValue` vacío y `effectiveValue.stringValue = ""` pasa por `value()` como el texto `{"stringValue": ""}`, y en Consolidado eso termina en un banco desconocido con ese nombre. Viene de `value()`, no de este ticket. Datos reales: 0 celdas así en banco, rubro, agrupador, detalle, subdetalle o equipo.

## Observaciones (no son findings)

- Las 157 filas del lado que recibe la transferencia (banco Mesh, rubro «CAJA. Mesh», agrupador MESH) no se marcan `Interno` sino que quedan sin regla. No hay doble conteo porque no suman en ninguna fila del cashflow, pero conviene que Emi y Ro confirmen el criterio cuando se arme el cashflow.
- Valores `inf`/`NaN` en una celda numérica rompen la lectura en las sondas, pero la API de Sheets no puede mandarlos en JSON: es un artefacto del helper de tests y no lo cuento.
- La base local todavía no tiene `banks` en el esquema de Consolidado: después del merge hace falta `sources load`, como dicen los pasos post-merge del ticket.

## No verificado

- Criterios 11 y 12, la parte de la descripción del pedido de cambios (tiempo medido y filas sin regla): no hay pedido de cambios todavía. El contenido está en `## Implementation` del ticket; hay que verificarlo cuando se abra.
- Corrida completa de `interpret run` escribiendo en la base local: no la hice para no tocar la base principal. Medí solo la función pura (~194 ms); el ~1,1 s de la corrida completa lo reportó implement.

## Split-outs sugeridos (fuera del alcance)

- [privacidad] Normalizar la comparación de Tipo Mov «Sueldos» y extender la restricción de la base a cualquier fila con rubro o Tipo Mov de sueldos. Ver F1. Se puede resolver en este mismo ticket si implement lo prefiere.
- [datos] `value()` devuelve el JSON crudo de `effectiveValue` cuando el valor formateado está vacío. Ver F4; afecta a todos los intérpretes, no solo a Consolidado.
