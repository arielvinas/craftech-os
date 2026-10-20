# QA T-011 — Ronda 2

**Verdict: PASS**
**Branch:** arielvinas/t-011-facturas-cobros-bajas @ b26e8c4
**Gates:** typecheck — (el repo no tiene) · lint ✓ (`ruff check`) · formato ✓ (`ruff format --check`, 52 archivos) · tests ✓ (272 passed, con `TEST_DATABASE_URL`) · build — (no corrido: la rama no toca `infra/Dockerfile` ni las dependencias)
**Criteria:** 7/7 sin incumplir con la evidencia disponible; los criterios 1, 2, 3, 5 y 6 (primera mitad) siguen verificados solo con el Google falso y piden un paso humano en la planilla de prueba real (ver "No verificado").
**Mutation:** harness `plan/qa/evidence/T-011-r2-mutants.py` (el de la ronda 1 actualizado para el código nuevo, más mutantes de cada arreglo), que corre **solo** `app/tests/test_invoices.py`: 36/38 muertos. Los dos sobrevivientes son F1 y F2; los dos son casos vecinos de arreglos cuyo caso central sí está cubierto.

Alcance: los cambios de la ronda de arreglos (`b875562`, `3e90052`) sobre `0010_invoices.sql`, `interpret/pagos.py` y `test_invoices.py`, y una nueva pasada por todo `git diff main...HEAD`. Entorno: base de prueba `craftech_os_test` y, en modo solo lectura (`default_transaction_read_only = on`), la base principal con las lecturas reales. Nada se escribió en Google Sheets, en Drive ni en la base principal. Las sondas fueron un archivo de test descartable, ya borrado.

## Re-verificación de la ronda 1

- **F1 [major] de la ronda 1 — una fila con el texto literal "Cliente Uno (2)" chocaba con la segunda de la serie "Cliente Uno" y tumbaba la lectura: resuelto.** La unicidad de `invoice` y `client_churn` pasó a `(pestaña, bloque, texto, orden en la serie, mes)` y la de `payment` suma el orden en la serie; `pagos.link` y `mcp.cobros` cruzan por texto y orden, no por el texto formateado. El test 10 cubre el caso de la ronda 1 y los mutantes que vuelven a la clave formateada mueren. Sonda adicional con el mismo caso en bajas de Pagos de SleakOps: sin error, dos bajas en enero con orden 1 y 2.
- **F2 [minor] de la ronda 1 — tipear 0 o un texto sobre un monto hacía desaparecer la factura sin rastro: resuelto.** La función SQL `shows_amount` decide si un valor mostrado es un monto, y `mcp.cambios_de_estado_de_factura` ahora incluye los cambios de valor que pasan de monto a no monto (o al revés), con "sin factura" del lado sin monto. Test 11 lo cubre con "0" y con "pendiente". Sondas: "pagado 2/3" tipeado sobre un monto azul da "confirmada → sin factura"; un monto reemplazado por otro monto en una celda verde no aparece en la historia y no mueve la fecha del cobro.
- **F3 [minor] de la ronda 1 — una fórmula de Pagos ARG que no es un producto simple dejaba la cotización vacía sin problema: resuelto.** Las referencias se buscan en toda la fórmula: con una sola referencia se toma la cotización de esa fila (el USD inferido solo para el producto simple), con dos o más se abre `cotizacion_tipo_a_confirmar`. Tests 13 y 14. Sondas: `=50*1.21*$B$7` da cotización 900 y USD 50; `=ROUND(50*1.21*B7, 0)` da cotización 900 y USD vacío. En la base principal (solo lectura, intérprete de esta rama sobre la última lectura): Craftech Pagos ARG tiene 4 facturas sin cotización, como dice el ticket (antes 11); SleakOps Pagos ARG, ninguna. Las claves de factura son únicas en las cuatro pestañas.
- **F4 [minor] de la ronda 1 — "monto tipeado en una celda ya verde cuenta como cobro" no tenía test: resuelto.** Test 12; el mutante que solo cuenta cambios de color muere.
- **Nits de la ronda 1.** El comentario sobre las fórmulas con `!` está en el código ✓. El redondeo de `mcp.paridad_pagos` tiene test propio y el mutante que quita el redondeo muere ✓. Que la historia liste una celda vacía que se pinta sigue igual; no se pidió arreglarlo.
- **Migración 0010 cambiada después de aplicada.** La base principal tiene registrada la 0010 de `fc435ad` (sha distinto del de HEAD), así que el post-merge necesita el deshacer manual que anota el ticket. Lo ensayé en la base de prueba: con la 0010 vieja aplicada, `migrate` falla con "changed after it was applied"; tras el SQL de deshacer del ticket la última migración queda en 0009, `migrate` aplica la 0010 nueva, `shows_amount` da falso para "USD $0" y verdadero para "USD $1,200", `payment.series_order` existe y `mcp_reader` puede leer `mcp.cobros`. Los pasos 1 y 2 del post-merge funcionan tal como están escritos.

## Findings

### F1 [minor] La parte de `shows_amount` que descarta textos con dígitos no tiene test
- **Repro:** en `0010_invoices.sql`, quitar de `shows_amount` la condición `AND regexp_replace(shown, 'USD|ARS', '', 'g') !~ '[[:alpha:]]'` y correr `app/tests/test_invoices.py`.
- **Expected:** algún test en rojo: un texto como "pagado 2/3" tipeado sobre un monto no es un monto (regla de celdas ilegibles: no hay factura).
- **Actual:** todo verde. El test 11 usa "pendiente", que no tiene dígitos y ya cae por la primera condición. Con el mutante, "pagado 2/3" se tomaría como monto y el paso de factura a "sin factura" no aparecería en la historia. La sonda confirma que el código actual lo hace bien.
- **Por qué es minor:** el comportamiento es correcto hoy; falta el test que lo fije. Alcanza con un texto con dígitos en el test 11.

### F2 [minor] "Un 0 en una celda verde que después recibe un monto" cuenta bien como cobro, pero no tiene test
- **Repro:** en `pagos.link`, volver la condición del cambio de valor a `c.old_value IS NULL` (en lugar de `NOT shows_amount(c.old_value) AND shows_amount(c.new_value)`) y correr `app/tests/test_invoices.py`.
- **Expected:** algún test en rojo: el arreglo de F2 de la ronda 1 dice que pasar de no monto a monto en una celda verde o naranja es el cambio que cuenta.
- **Actual:** todo verde. El test 12 parte de una celda verde vacía, no de una con "0". Sonda: celda verde con "0", después "2200" → el cobro apunta a ese cambio de valor y la historia muestra "sin factura → pagada". El código actual lo hace bien.
- **Por qué es minor:** mismo caso que F1: comportamiento correcto sin test. El harness sale con código distinto de cero hasta que haya tests para F1 y F2.

### Nits
- **Una fila nueva con el mismo texto, insertada arriba, corre la serie y pierde el cobro.** Sonda: dos filas "Cliente Uno", la segunda pagada; se inserta otra "Cliente Uno" arriba de las dos. El cobro pasa a ser de "cliente uno (3)", con el cambio vacío y "fecha desconocida". Es inherente a la regla de identificar la serie repetida por orden, que ya abre `identidad_en_revision`; lo dejo anotado para cuando Emi y Ro ratifiquen esa identidad.
- **`shows_amount` mira el valor formateado y el intérprete en Python mira el número.** Un 0,4 mostrado como "USD $0" es factura para el intérprete pero la historia lo trata como "sin factura". No aparece en los datos reales.
- **La búsqueda de referencias en fórmulas de Pagos ARG puede tomar nombres de funciones con dígitos** (por ejemplo `LOG10` o `ATAN2`) como referencias de celda. No hay ninguna en los datos reales.

## Criterios, uno por uno

1. **Pintar una celda de cada color → estado en `mcp.facturas`; un color fuera de la lista abre `color_desconocido` sin factura.** ✓ con el Google falso (sin cambios desde la ronda 1; sus mutantes siguen muriendo). Falta la prueba en la planilla real.
2. **Vaciar una celda → la factura desaparece y la historia sigue visible.** ✓ con el Google falso, ahora también con 0 o texto tipeado sobre el monto (test 11). Falta la prueba en la planilla real.
3. **Pintar de verde → `mcp.cobros` con la fecha del editor cuando Drive la atribuye, y la ventana de detección mientras no.** ✓ con el Google falso; los mutantes de la vista siguen muriendo con el cruce nuevo por texto y orden. Falta la prueba con Drive real.
4. **Pagos ARG: bruto, neto = bruto / 1,21, cotización de la fila referenciada; con cotización tipeada, `cotizacion_tipeada`.** ✓ por test y en datos reales: Craftech Pagos ARG, 193 facturas, 4 sin cotización, 182 con USD inferido, 17 `cotizacion_tipeada`, 17 `cotizacion_tipo_a_confirmar` y 1 `cotizacion_discrepante`; SleakOps Pagos ARG, 38 facturas, todas con cotización, 3 `cotizacion_tipo_a_confirmar`.
5. **Insertar una fila arriba no duplica ni pierde el cobro.** ✓ con el Google falso para una fila de otro cliente; con una fila del mismo texto ver el primer nit. Falta la prueba en la planilla real.
6. **Paridad 0 con datos consistentes; en la base real, cada mes distinto de 0 explicado.** Primera mitad ✓ con el Google falso, ahora con test del redondeo al centavo. Segunda mitad verificada en la ronda 1 (36 meses por pestaña, solo mayo de 2025 en Pagos de SleakOps distinto de 0, explicado); los arreglos de esta ronda no tocan montos ni la suma. Falta la planilla de prueba real.
7. **Celda pintada sin monto en Pagos de SleakOps → `mcp.bajas` con "color a confirmar".** ✓ por test, y la sonda con texto literal "(2)" en bajas no rompe.

Otros chequeos: ningún `details` ni log nuevo lleva montos; `cotizacion_tipo_a_confirmar` con dos referencias guarda la celda como clave, igual que `valor_ilegible`; las vistas nuevas siguen con `GRANT SELECT` a `mcp_reader`.

## No verificado

- **Criterios 1, 2, 3 y 5, y la primera mitad del 6, en la planilla de prueba real de Ariel con el worker y Drive reales.** QA no escribe en Sheets ni en Drive. Hace falta que Ariel lo pruebe a mano; ya está como paso 4 del post-merge del ticket.

## Split-outs sugeridos (fuera del alcance)

- Ninguno nuevo.
