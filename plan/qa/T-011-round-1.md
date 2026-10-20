# QA T-011 — Ronda 1

**Verdict: FAIL**
**Branch:** arielvinas/t-011-facturas-cobros-bajas @ fc435ad
**Gates:** typecheck — (el repo no tiene) · lint ✓ (`ruff check`) · formato ✓ (`ruff format --check`, 52 archivos) · tests ✓ (266 passed, con `TEST_DATABASE_URL`) · build — (no corrido: la rama no toca `infra/Dockerfile` ni las dependencias)
**Criteria:** 7/7 sin incumplir con la evidencia disponible; los criterios 1, 2, 3, 5 y 6 (primera mitad) están verificados solo con el Google falso y piden un paso humano en la planilla de prueba real (ver "No verificado").
**Mutation:** harness `plan/qa/evidence/T-011-r1-mutants.py`, que corre **solo** `app/tests/test_invoices.py` para atribuir: 22/23 muertos. El sobreviviente sigue verde también con la suite completa (266 passed): ver F4.

Alcance: todo `git diff main...HEAD` (migración `0010_invoices.sql`, `interpret/pagos.py`, `interpret/__init__.py`, `diff/compare.py` y los tests). Entorno: base de prueba `craftech_os_test` y, en modo solo lectura (`default_transaction_read_only = on`), la base principal con las lecturas reales. Nada se escribió en Google Sheets, en Drive ni en la base principal. No hay pantallas en este ticket: la superficie es la base, las cinco vistas `mcp` nuevas y el comando `craftech-os import`. Las sondas fueron un archivo de test descartable, ya borrado.

## Findings

### F1 [major] Una fila cuyo texto ya termina en "(2)" choca con la serie repetida y tumba la lectura
- **Repro:** en el fixture de Pagos de `test_invoices.py`, dentro del bloque del encabezado, dos filas "Cliente Uno" con montos y una tercera fila con el texto literal "Cliente Uno (2)" con montos en el mismo mes; correr `craftech-os import`.
- **Expected:** tres facturas (serie 1 y 2 de "cliente uno", y la fila literal), y la lectura guardada.
- **Actual:** `psycopg.errors.UniqueViolation: duplicate key value violates unique constraint "invoice_source_tab_id_block_row_key_month_key"`, con la clave `(…, Cliente, cliente uno (2), 2025-01-01)`. No es `psycopg.DataError`, así que el importer (`app/craftech_os/ingest/importer.py:198`) no la atrapa: la lectura no se guarda y el worker queda en ciclo de caídas, igual que F1 de la ronda 1 de T-010.
- **Causa:** `pagos._interpret` arma `row_key = key if ordinal == 1 else f"{key} ({ordinal})"`, y `invoice`, `payment` y `client_churn` tienen `UNIQUE (source_tab_id, block, row_key, month)`. El texto con sufijo puede coincidir con un texto real. El diccionario de `pagos.link` usa la misma clave formateada, así que además los cobros de la fila literal y de la segunda de la serie se mezclarían.
- **Por qué es major:** no es un dato imposible (dos clientes con el mismo nombre más una fila que alguien numeró a mano), y la consecuencia es dejar de leer la planilla entera. En datos reales hoy ningún texto de factura termina en "(n)", así que no está pasando. T-010 ya resolvió la misma clase pasando la unicidad a `(source_tab_id, block, alias_text, series_order, month)`; acá alcanzaría con lo mismo en las tres tablas y una tupla `(texto, orden)` como clave en `link`.

### F2 [minor] Tipear 0 o un texto sobre un monto hace desaparecer la factura sin dejar rastro en la historia
- **Repro:** con una factura pintada y con monto, en la lectura siguiente reemplazar el monto por `0` (o por un texto que no es número) manteniendo el color.
- **Expected:** la factura deja de aparecer en `mcp.facturas` (regla R30: un 0 o una celda sin monto no es factura) y la historia lo muestra, como cuando se vacía la celda.
- **Actual:** la factura desaparece, pero `mcp.cambios_de_estado_de_factura` no muestra nada: la vista solo incluye cambios de valor con `old_value IS NULL`, y este cambio tiene valor viejo. En la sonda, la historia de la celda quedó vacía mientras la factura ya no estaba.
- **Por qué es minor:** el criterio 2 habla de vaciar la celda, y eso funciona (el cambio `emptied` aparece como "sin factura"). Este es el caso vecino.

### F3 [minor] Una fórmula de Pagos ARG que no es un producto simple deja la cotización vacía sin abrir problema
- **Repro:** en el fixture de Pagos ARG, una factura con fórmula `=ROUND(50*1.21*C7)` o `=50*1.21*B7+0`.
- **Expected:** la cotización de la fila referenciada, o un problema (`cotizacion_tipo_a_confirmar` u otro) que diga que no se pudo leer.
- **Actual:** `fx_rate` vacío, `inferred_usd` vacío y ningún problema abierto. En la base principal hay 11 facturas de Pagos ARG sin cotización; no revisé una por una si alguna es este caso.
- **Por qué es minor:** la factura existe con su bruto y su neto; lo que se pierde en silencio es la cotización y el USD inferido.

### F4 [minor] La rama "monto tipeado en una celda ya pintada de verde cuenta como cobro" no tiene test
- **Repro:** en `pagos.link`, cambiar `AND (c.change_type = 'color' OR (c.change_type = 'value' AND c.old_value IS NULL))` por `AND c.change_type = 'color'` y correr la suite.
- **Expected:** algún test en rojo: el docstring de `link` dice que un monto tipeado en una celda vacía de ese color es un cambio que cuenta.
- **Actual:** `test_invoices.py` y la suite completa siguen verdes (266 passed). Si la rama se rompe, el cobro de una factura cargada sobre una celda ya verde quedaría apuntando a otro cambio o sin fecha.
- **Por qué es minor:** la regla central (el último cambio a verde, no el primero) sí está cubierta y su mutante muere. Este es un caso secundario de la misma regla. El harness sale con código distinto de cero hasta que haya un test para esto.

### Nits
- `mcp.cambios_de_estado_de_factura` puede listar cambios de celdas que nunca fueron factura: un 0 tipeado en una celda vacía pintada, o una celda vacía que se pinta.
- Una factura de Pagos ARG cuya fórmula referencia otra pestaña (contiene `!`) se descarta como copia. En los datos reales las únicas fórmulas con `!` son las copias de la fila 15 de Pagos de SleakOps, que no son facturas; vale anotarlo en el código.
- El redondeo al centavo de `mcp.paridad_pagos` (commit `f53c1fa`) no tiene test propio: el mutante que anula la diferencia muere, pero quitar solo el `round` no se probó. Los datos reales lo cubren hoy.

## Criterios, uno por uno

1. **Pintar una celda de cada color → estado en `mcp.facturas`; un color fuera de la lista abre `color_desconocido` sin factura.** ✓ con el Google falso, por el mismo camino de importación y diff que usa el worker. La lista de colores del intérprete está atada por `assert` a `detect.KNOWN_COLORS`, y mutar el estado del verde o dejar pasar un color desconocido pone rojo el test. En datos reales hay 8 claves `color_desconocido` abiertas. Falta la prueba en la planilla real.
2. **Vaciar una celda → la factura desaparece y la historia sigue visible.** ✓ con el Google falso: el diff produce `emptied` aunque el color se mantenga, y la vista lo muestra como "sin factura" (mutar esa rama pone rojo el test). Caso vecino en F2. Falta la prueba en la planilla real.
3. **Pintar de verde → `mcp.cobros` con la fecha del editor cuando Drive la atribuye, y la ventana de detección mientras no.** ✓ con el Google falso; los dos mutantes de la vista (siempre la ventana, o nunca "editor") mueren. La fecha se lee de `cell_change` al consultar, así que la atribución que llega después se ve sin reinterpretar. Falta la prueba con Drive real.
4. **Pagos ARG: bruto, neto = bruto / 1,21, cotización de la fila referenciada; con cotización tipeada, `cotizacion_tipeada`.** ✓ por test y en datos reales (15 `cotizacion_tipeada` y 5 `cotizacion_tipo_a_confirmar` abiertos). Caso vecino en F3.
5. **Insertar una fila arriba no duplica ni pierde el cobro.** ✓ con el Google falso, incluida una sonda que pinta de verde e inserta la fila en la misma lectura: el cobro se conserva y apunta al cambio correcto. Mutar el cruce para que sea por celda en vez de por fila pone rojo el test. Falta la prueba en la planilla real.
6. **Paridad 0 con datos consistentes; en la base real, cada mes distinto de 0 explicado.** Segunda mitad ✓: en la base principal hay 36 meses por cada una de las 4 pestañas, y el único distinto de 0 es mayo de 2025 en Pagos de SleakOps, con la suma de facturas por encima del total de la planilla. Eso coincide con la nota de `## Implementation` (la fórmula del total de la planilla saltea una fila). Primera mitad ✓ con el Google falso; falta la planilla de prueba real.
7. **Celda pintada sin monto en Pagos de SleakOps → `mcp.bajas` con "color a confirmar".** ✓ por test (los mutantes de "color a confirmar" y de "bajas solo en SleakOps" mueren) y en datos reales: 4 bajas en `mcp.bajas`.

Otros chequeos: ningún `details` ni log nuevo lleva montos; `fx_rate_type` solo puede recibir los tipos que admite su `CHECK`; las cinco vistas nuevas tienen `GRANT SELECT` a `mcp_reader`.

## No verificado

- **Criterios 1, 2, 3 y 5, y la primera mitad del 6, en la planilla de prueba real de Ariel con el worker y Drive reales.** El texto de estos criterios dice "en la planilla de prueba", y QA no escribe en Sheets ni en Drive. Hace falta que Ariel lo pruebe a mano: pintar un color de cada uno y uno desconocido, vaciar una celda, pintar de verde y esperar la atribución de Drive, insertar una fila arriba de un cliente con cobro, y mirar `mcp.paridad_pagos` con datos consistentes. Ya está como paso 4 del post-merge del ticket, igual que en T-009 y T-010.

## Split-outs sugeridos (fuera del alcance)

- Ninguno nuevo. F1 es la misma clase `[robustez]` que ya está en `plan/improvements.md` (QA T-010): una excepción que no es `DataError` tumba la lectura entera.
