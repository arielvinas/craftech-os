# QA T-010 — Ronda 1

**Verdict: FAIL**
**Branch:** arielvinas/t-010-devengados-y-cotizaciones @ b97a037
**Gates:** typecheck — (el repo no tiene) · lint ✓ (`ruff check`) · formato ✓ (`ruff format --check`, 82 archivos) · tests ✓ (248 passed, con `TEST_DATABASE_URL` y las claves de los roles del servidor MCP) · build — (no corrido: la rama no toca `infra/Dockerfile` ni las dependencias)
**Criteria:** 5/7 verificados; los criterios 1 y 2 verificados solo con el Google falso (ver "No verificado"). Ninguno incumplido en el camino feliz, pero F1 rompe la lectura entera ante una edición plausible.
**Mutation:** 16 mutantes a mano (`plan/qa/evidence/T-010-r1-mutants.py`): 13 muertos, 3 sobrevivientes (F3, F4, F5)

Alcance: `git diff main...HEAD`. Entorno: base de prueba `craftech_os_test` del postgres local y, solo para leer, la base principal con las lecturas reales (sin escribir nada). Nada se escribió en Google Sheets ni en Drive. Esta entrega no tiene pantallas, así que no hubo prueba en navegador: la superficie es la base, las vistas del esquema `mcp` y el comando `craftech-os interpret`.

## Findings

### F1 [major] Una columna de mes repetida en VENTAS tumba la importación entera y el worker queda en un ciclo de caídas
- **Repro:** en el fixture de `test_interpret.py`, cambiar el encabezado de VENTAS para que dos columnas de la grilla tengan el mismo mes (por ejemplo, copiar la columna de febrero al lado) y correr `craftech-os import --file <sources>`.
- **Expected:** según el propio ticket, lo que no se puede ubicar en un mes abre `fila_sin_interpretar` (o al menos la pestaña falla con `tab_failed` y se sigue con las demás), y la lectura de la planilla se guarda.
- **Actual:** `psycopg.errors.UniqueViolation: duplicate key value violates unique constraint "accrual_source_tab_id_block_row_key_month_key"`. Esa excepción no es `psycopg.DataError`, así que `importer.read_tab` no la atrapa (`app/craftech_os/ingest/importer.py:197`): el comando termina con la excepción, no queda ninguna lectura guardada (ni de esa pestaña ni de las siguientes de la planilla) y no hay evento `tab_failed`. En el worker, `worker.run` deja que el error termine el proceso; Docker lo reinicia (`restart: unless-stopped`), la versión de la planilla no quedó registrada y vuelve a caer en el mismo punto. Mientras la columna siga repetida, no se lee ninguna planilla que venga después en el orden.
- **Por qué importa:** antes de T-010 esa misma edición se guardaba como una lectura más. Ahora una persona que copia una columna de mes para armar la del año siguiente frena toda la ingesta. Es una regresión del enganche del intérprete dentro de la transacción de la lectura.
- **Misma clase, mismo arreglo:** una fila cuyo texto ya termina en " (2)" (por ejemplo "Cliente Uno (2)") junto a dos filas "Cliente Uno" en el mismo bloque produce la misma `UniqueViolation` sobre `row_key`, porque el sufijo de la serie repetida coincide con el texto literal. Menos probable, mismo efecto.
- **Evidencia:** sonda descartable (borrada) sobre el fixture de `test_interpret.py`; salida: `UniqueViolation(... Key (source_tab_id, block, row_key, month)=(1, Cliente, cliente uno, 2025-02-01) already exists.)`, eventos `tab_failed`/`tab_interpreted` = `[]`, lecturas guardadas = `[]`. Para la colisión de sufijo: `Key (...)=(1, Cliente, cliente uno (2), 2025-01-01) already exists.`
- **Falta un test** que cubra el mes repetido (y la colisión de sufijo) y pruebe que la importación sigue.

### F2 [minor] Un mes repetido en Pagos ARG pisa la primera cotización sin avisar
- **Repro:** mismo fixture, encabezado de Pagos ARG con enero dos veces. La importación termina bien (`tab_interpreted` con 4 cotizaciones), pero `_rates` (`app/craftech_os/interpret/pagos_arg.py:156`) guarda por mes en un diccionario y la segunda columna reemplaza a la primera.
- **Expected:** que la columna sobrante abra `fila_sin_interpretar` (como hace VENTAS con una columna sin mes), para que alguien mire cuál vale.
- **Actual:** se pierde una de las dos cotizaciones sin ningún problema abierto. No rompe un criterio; queda como mejora junto con el arreglo de F1.

### F3 [minor] El `valor_ilegible` que abre `ventas.py` duplica lo que ya abre `detect.find`
- **Mutación:** cambiar `elif unreadable(cell) and i > 0:` por `elif False:` en `app/craftech_os/interpret/ventas.py:264` → la suite sigue verde.
- **Por qué:** `store.record` ya corre `detect.find`, que abre `valor_ilegible` para los textos de la grilla con la misma clave (`detect.unreadable`), así que el test de montos ilegibles pasa por el camino viejo. Lo único que agrega el intérprete es marcar también celdas con error o booleanas, y eso no tiene test. Hay que elegir: o se borra la rama de `ventas.py` (y la de `pagos_arg.py`, que en VENTAS/Pagos ARG con esquema también queda cubierta), o se agrega un test con una celda `#REF!` que solo el intérprete detecte.

### F4 [minor] El resguardo "pestaña que no es CARGA o sin esquema" no tiene test
- **Mutación:** `if interpret is None or tab_class != "CARGA" or not schema:` → `if interpret is None:` en `app/craftech_os/interpret/__init__.py:52` → suite verde.
- `test_a_tab_without_interpreter_is_not_touched` solo prueba una pestaña con otro nombre ("Cobros"). Una pestaña llamada "VENTAS" sin esquema (otra planilla, o una reclasificada como HISTORICA) llegaría a `blocks(doc, None)` y fallaría con `TypeError`, que tampoco atrapa el importer (misma salida que F1). Falta un test con una pestaña "VENTAS" sin esquema.

### F5 [nit] Un número que no es fecha en el encabezado se toma como mes, y `.replace(day=1)` no tiene test
- Con una celda `2025` (número) en el encabezado de la grilla, `cells.month` la lee como julio de 1905 y salen devengados de ese mes. En los datos reales no pasa (las cuatro pestañas tienen 36 meses, de enero 2025 a diciembre 2027, ninguno fuera de rango), así que es un nit. La mutación que saca `.replace(day=1)` sobrevive porque los seriales del fixture ya son día 1; el CHECK de la tabla lo atraparía con una excepción, que vuelve a ser la salida de F1.

## Criterios, uno por uno

1. **Lectura nueva de VENTAS → `mcp.devengados` con planilla, pestaña, celda y `lectura_id`.** ✓ con el Google falso por el mismo camino del importer (`test_ventas_with_a_cliente_header...`). En la base principal con lecturas reales: 860 devengados en Craftech y 1057 en SleakOps, cada uno con celda y lectura. Con el usuario `mcp_reader`: `mcp.devengados` y `mcp.cotizaciones` se leen (13 y 6 filas en el fixture, todas con celda y lectura) y la tabla `accrual` da `InsufficientPrivilege`, como corresponde. Sin la planilla de prueba real: ver "No verificado".
2. **Editar un monto → cambia el devengado y no quedan filas de la lectura anterior.** ✓ con el Google falso (`test_a_new_read_replaces...`; la mutación que saca el `DELETE` muere).
3. **Fila sin alias → `alias_sin_cliente`; cargado el alias, el devengado muestra el cliente sin reinterpretar.** ✓ (`test_a_client_without_alias...`; la mutación que saca la normalización de la fuente en `aliases load` muere).
4. **`interpret --all` dos veces → mismas filas, sin duplicar problemas.** ✓ (`test_interpret_twice...`).
5. **Filas de cotización corridas → mismas cotizaciones; MEP de control distinta → `cotizacion_discrepante`.** ✓. En datos reales, Craftech Pagos ARG tiene la MEP de control en la fila 23 y la operativa en la 27, como dice el ticket; "Dólar oficial" está arriba del encabezado y se encuentra.
6. **`system_event` registra el tiempo por pestaña; ninguna supera 10 segundos.** ✓ (`duration_ms` en `tab_interpreted`; la mutación que lo saca muere). Tiempos medidos por implement: 3 a 53 ms por pestaña.
7. **Ningún log ni `details` contiene montos.** ✓ por lectura del código (los `details` llevan bloque, fila, celda, mes, tipo y texto) y por `test_events_count_facts_and_time_and_nothing_carries_amounts`.

Otras reglas del alcance revisadas sobre datos reales: "Ventas ARG (2025)" está clasificada IGNORAR y el intérprete solo mira pestañas llamadas exactamente "VENTAS" y "Pagos ARG", así que la regla de no leer "Ventas Argentina 2025" se cumple. Las filas salteadas con montos (las de arriba del encabezado y el bloque "Total Ingresos") son totales, tipos de cambio e indicadores, no clientes.

## Mutación

Harness: `plan/qa/evidence/T-010-r1-mutants.py <raíz del repo>` (falla si un archivo o un patrón no está; corre `test_interpret.py` y `test_clients.py`; sale distinto de cero si sobrevive alguno).

Muertos (13): sacar `interpret.run` del importer; sacar el `DELETE`; tomar la primera MEP como operativa; no comparar control contra operativa; oficial sin "tipo a confirmar"; no abrir `cotizacion_tipo_a_confirmar`; no abrir `identidad_en_revision`; sin sufijo de serie; no saltear "Total Ingresos"; no abrir `fila_sin_interpretar` en filas sin cliente; no abrir `alias_sin_cliente`; no normalizar la fuente del alias; sacar `duration_ms` del evento. Sobrevivientes (3): F3, F4, F5.

## No verificado

- Criterios 1 y 2 contra la planilla de prueba real con el worker: no hay acceso a escribir en Sheets desde QA (y no se debe). Quedan para el post-merge, como ya anota el ticket.

## Split-outs sugeridos (fuera del alcance)

- [robustez] Cualquier excepción que no sea `psycopg.DataError` dentro de la transacción de la lectura (en `store.record` o en el intérprete) termina el worker y lo deja en un ciclo de caídas sobre la misma planilla. F1 es el caso de T-010; la clase es más amplia y conviene que el importer registre `tab_failed` y siga con la pestaña siguiente.
