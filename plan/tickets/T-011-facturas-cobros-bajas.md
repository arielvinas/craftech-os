---
id: T-011
title: Facturas, cobros y bajas: interpretación de Pagos y Pagos ARG por color, cobros desde los cambios de celda y paridad con los totales
status: pr
priority: high
lane: core
depends_on: [T-010]
effort: M
milestone: B
branch: arielvinas/t-011-facturas-cobros-bajas
---

## Context

ADR-002, secciones 3 y 4 (estado por color, celda vaciada, factura ARG, cobro, baja de SleakOps, marketplace) y riesgos. `paridad_pagos` es el criterio de aceptación de la etapa: una diferencia distinta de cero delata una interpretación equivocada.

Decisiones de Ariel del 19-oct-2026: ADR-002 aprobado.

Verificado en el repo el 19-oct-2026:
- `issues/detect.py` ya tiene `KNOWN_COLORS = {None, "#ffffff", "#00ffff", "#4a86e8", "#ff9900", "#d9ead3", "#ff00ff"}`, que es el mapeo de la regla R29. El intérprete debe usar esa misma lista, no una copia.
- `cell_change` (`0004`) guarda el valor y el color anterior y el nuevo de cada celda, con la ventana de detección, `attribution_certainty` (`cierta`, `una_de`, `sin_datos` o nula si todavía no se procesó) y `attributed_editor_ids`. La atribución se completa después de la ventana; por eso la fecha del cobro no puede quedar copiada al insertar.
- Esquemas de Pagos en `config/sources.yaml`:
  - Craftech: bloques "General", "Funding de AWS confirmados" y "Total Ingresos", grilla D:AM.
  - SleakOps: bloques "Fundings de AWS", "General" y "Total Ingresos".

  Pagos ARG: encabezado "Mes", bloques "Total Ingresos" y "Mes", grilla B:AK. Los nombres de los bloques de funding difieren entre planillas; este ticket los ignora (son de T-012).
- T-009 ya conserva las celdas vacías con solo color, sin las cuales "magenta sin monto" y las bajas no se ven.

## Scope

**Dónde vive:**
- `app/migrations/0010_invoices.sql`
- `interpret/pagos.py` (o el nombre que siga el patrón de T-010)
- tests

1. **Migración 0010:**
   - Tabla `invoice`: pestaña, bloque, `row_key`, orden de la serie, mes, entidad legal, estado, monto en la moneda de la celda, moneda, neto y cotización para ARG, USD base inferido de la fórmula si lo hay, `snapshot_id`, `cell_ref` y `rules_version`.
   - Tabla `payment`: la clave de la factura (pestaña, bloque, `row_key`, mes y entidad legal), el `cell_change_id` que la puso verde (nulo si ya estaba verde en la importación inicial), `snapshot_id` y `rules_version`.
   - Tabla `client_churn`, la baja: planilla, `row_key`, mes, color y si el color está "a confirmar".
   - Vistas `mcp.facturas` (con la fecha de vencimiento calculada con el plazo de pago de la razón social), `mcp.cobros`, `mcp.bajas`, `mcp.cambios_de_estado_de_factura` y `mcp.paridad_pagos`, con cliente por alias, origen, `COMMENT ON` y `GRANT SELECT` a `mcp_reader`.
2. **Estado por color (regla R29):**

   | Color de la celda | Estado |
   |---|---|
   | cian | a confirmar |
   | azul | confirmada |
   | naranja | enviada |
   | verde `#d9ead3` | pagada |
   | magenta | retraso |
   | monto sin color | a facturar |
   | cualquier otro color | `color_desconocido` y sin hecho |

3. **Celdas vacías e ilegibles (regla R30).** Una celda vaciada, un 0 con color o un magenta sin monto significan que no hay factura. Un valor ilegible abre `valor_ilegible` y no genera hecho.
4. **Entidad legal (regla R25).** Pagos ARG es Craftech S.A.; todo lo demás es Craftech-io Inc.
5. **Factura ARG (regla R14).** El bruto está en ARS, neto = bruto / 1,21.
6. **Cotización de la factura ARG (regla R10).** Se toma de la fila que referencia la fórmula de la celda, buscada en las cotizaciones de T-010.
   - Si la fórmula referencia "Dólar oficial", la factura lleva la cotización marcada "tipo a confirmar".
   - Si el número está tipeado a mano en vez de referenciado, se guarda como cotización de esa factura y se abre `cotizacion_tipeada` (regla R38).
   - Un USD base que aparezca en la fórmula, como el `7200` de `7200*1.21*M1`, se guarda como monto inferido.
7. **Series repetidas (regla R26).** Dos series con el mismo texto en un bloque llevan sufijo de orden y abren `identidad_en_revision`, igual que en T-010.
8. **Marketplace (regla R16).** Es una factura más del cliente.
9. **Cobro (regla R4).**
   - Hay un `payment` por cada factura en estado pagada.
   - Se une con el último `cell_change` de esa celda que pasó a verde. La unión es por pestaña + bloque + `row_key` + columna de mes, nunca por `cell_ref` solo, porque las filas se mueven.
   - En la vista `mcp.cobros`, la fecha y la certeza salen del `cell_change`: la del editor atribuido por Drive si la certeza es `cierta` o `una_de`, si no la ventana de detección. Así la atribución que llega después se ve sin reinterpretar.
   - Una celda que ya estaba verde en la importación inicial da un cobro con "fecha desconocida".
10. **Cambios de estado.** `mcp.cambios_de_estado_de_factura` es una vista sobre `cell_change` de las celdas de factura (color anterior y nuevo traducidos a estado, con fecha y autor), no una tabla.
11. **Bajas de SleakOps (regla R31).** Una celda pintada sin monto en la pestaña Pagos de SleakOps es una baja, marcada "color a confirmar" mientras siga abierta la pregunta F-05 a Emi.
12. **Paridad.** `mcp.paridad_pagos` muestra, por planilla, pestaña y mes, el total de la fila "TOTAL" de la planilla, la suma de facturas interpretadas y la diferencia.
13. **Tests sintéticos:**
    - cada color;
    - celda vaciada, 0 con color y magenta sin monto;
    - un monto ilegible;
    - una factura ARG con fórmula a la MEP, con fórmula a "Dólar oficial" y tipeada;
    - una fila movida entre lecturas que conserva su cobro;
    - un cobro de la importación inicial;
    - una baja;
    - la paridad en cero con datos consistentes y distinta de cero si falta una factura.

**Descartado:**
- Tablas de eventos `InvoiceIssued` o `PaymentReceived`: `cell_change` ya es ese registro (ADR-002).
- Copiar fecha y autor en `payment`: se quedarían viejos cuando llega la atribución.
- Tabla `contract`.

## Acceptance criteria

- [ ] En la planilla de prueba, pintar una celda de factura de cada color de la lista hace que, después de la lectura siguiente, `mcp.facturas` muestre el estado correspondiente. Un color fuera de la lista abre `color_desconocido` y no genera factura.
- [ ] Vaciar una celda de factura en la planilla de prueba hace que la factura deje de aparecer en `mcp.facturas`, y su historia sigue visible en `mcp.cambios_de_estado_de_factura`.
- [ ] Pintar de verde una celda de factura hace que `mcp.cobros` muestre el cobro con la fecha del editor una vez que Drive atribuye el cambio, y con la ventana de detección mientras no.
- [x] Una factura de Pagos ARG muestra bruto en ARS, neto = bruto / 1,21 y la cotización de la fila que referencia su fórmula. Con la cotización tipeada se abre `cotizacion_tipeada`.
- [ ] Mover una fila de cliente (insertar una fila arriba) en la planilla de prueba no duplica ni pierde su cobro.
- [ ] En la planilla de prueba con datos consistentes, `mcp.paridad_pagos` da diferencia 0 en todos los meses. En la base local con las lecturas reales, la diferencia de cada mes queda registrada en `## Implementation`, y cada mes distinto de 0 tiene un problema abierto que lo explica o una nota.
- [x] Una celda pintada sin monto en Pagos de SleakOps aparece en `mcp.bajas` marcada "color a confirmar".

## Out of scope

- Los bloques de funding de AWS de Pagos (T-012).
- Alertas de cobro y vencimientos vencidos (etapa D); facturas desde Zoho.
- Herramientas MCP (T-013) y pantallas (T-014).

## Implementation

- `app/migrations/0010_invoices.sql`:
  - Tablas `invoice`, `payment` (con el `cell_change_id` que la pintó de verde, nulo si ya estaba verde en la primera lectura), `client_churn` y `payment_total` (la fila del total de la planilla por mes, para la paridad). `invoice` guarda también `sent_change_id`, el cambio que la pintó de naranja.
  - Funciones `a1_column` (columna de una referencia A1) e `invoice_state` (color → estado según la regla R29; otro color da "color desconocido").
  - Vistas `mcp.facturas` (con vencimiento = fecha del pase a naranja + plazo de pago de la razón social, 10 días si no hay), `mcp.cobros` (fecha y certeza leídas del `cell_change` en el momento de la consulta: editor si Drive lo atribuyó, si no la ventana de detección, si no "fecha desconocida"), `mcp.bajas`, `mcp.cambios_de_estado_de_factura` (sobre `cell_change`, sin tabla) y `mcp.paridad_pagos`. Comentarios en todas las columnas y `GRANT SELECT` a `mcp_reader`.
- `app/craftech_os/interpret/pagos.py`: intérprete de Pagos y Pagos ARG.
  - Solo el bloque del encabezado tiene facturas; los bloques de funding quedan para T-012.
  - La entidad legal es Craftech S.A. en Pagos ARG y Craftech-io Inc. en Pagos.
  - Una celda con fórmula que copia otra pestaña (contiene `!`) no es factura: se factura en la pestaña de origen.
  - Factura ARG: neto = bruto / 1,21 redondeado al centavo. La cotización sale de la fila que referencia la fórmula: "MEP" es firme; "Dólar oficial" y cualquier otra fila referenciada (en los datos reales: "Dolar Divisa VTA" y "CCL") quedan "tipo a confirmar" y abren `cotizacion_tipo_a_confirmar`. Un monto sin referencia abre `cotizacion_tipeada`; si la fórmula tiene dos números además del 1,21, el segundo se guarda como cotización tipeada.
  - `link` une cada factura con el último cambio que la pintó de naranja o de verde, por pestaña, bloque, fila con su orden de serie y mes (la columna se traduce a mes con el encabezado de la lectura de ese cambio), nunca por celda.
- `interpret/__init__.py`: registra los intérpretes de Pagos y Pagos ARG (el de Pagos ARG suma las cotizaciones de T-010), llama a `link` dentro de la misma transacción y cuenta facturas, cobros y bajas en `tab_interpreted`. `cli.py` muestra esas cantidades.
- `diff/compare.py`: un cambio de valor guarda también el color anterior y el nuevo, para ver un monto tipeado en una celda ya pintada.
- El fixture de Pagos ARG de `test_interpret.py` pasó al orden real de las filas (las MEP debajo de "Total Ingresos").
- `mcp.paridad_pagos` redondea la diferencia al centavo: Sheets suma en punto flotante binario y dejaba restos de millonésimas en 24 meses de Pagos ARG.
- Medido en la base local (20-oct-2026, `interpret --all` sobre las lecturas actuales):
  - Craftech Pagos: 392 facturas, 331 cobros, 48 ms. Craftech Pagos ARG: 193 facturas, 150 cobros, 27 ms. SleakOps Pagos: 976 facturas, 567 cobros, 4 bajas (todas "color a confirmar"), 70 ms. SleakOps Pagos ARG: 38 facturas, 21 cobros, 8 ms.
  - Cobros: 30 con fecha del editor, 1039 con "fecha desconocida" (ya estaban verdes en la primera lectura). 110 filas en `mcp.cambios_de_estado_de_factura`. De 12 facturas enviadas, 2 tienen vencimiento (las otras 10 ya estaban naranjas en la primera lectura).
  - Facturas ARG: 231, 11 sin cotización legible y 218 con USD inferido. Problemas: 15 `cotizacion_tipeada`, 5 `cotizacion_tipo_a_confirmar`, 1 `color_desconocido` (#ea9999, 22 celdas de SleakOps Pagos).
- Paridad en la base local, por mes:
  - Craftech Pagos: 36 meses, todos con diferencia 0.
  - Craftech Pagos ARG: 36 meses, todos con diferencia 0.
  - SleakOps Pagos ARG: 36 meses, todos con diferencia 0.
  - SleakOps Pagos: 35 meses con diferencia 0 y uno distinto de 0, mayo de 2025.
- Nota sobre mayo de 2025: la fórmula del total de la planilla para ese mes es `=SUM(H13:H…)+H…` y no incluye la fila 76, que es una factura verde. La diferencia es exactamente el monto de esa celda. Es un error de la planilla y no de la interpretación; hay que avisarle a Finanzas (ver post-merge).
- Los criterios 1, 2, 3, 5 y 6 (planilla de prueba) están probados con el Google falso por el mismo camino del importer y del diff. Falta verlos contra la planilla de prueba real de Ariel, así que quedan sin tildar. Los criterios 4 y 7 están probados con tests y vistos en la base local.

### Ronda de correcciones 1 (`plan/qa/T-011-round-1.md`)

- Hallazgo 1 (una fila cuyo texto termina en "(2)" chocaba con la segunda fila de una serie y tumbaba la lectura):
  - `invoice` y `client_churn` pasan a ser únicas por `(pestaña, bloque, alias_text, series_order, mes)`, igual que `accrual` en T-010.
  - `payment` gana la columna `series_order` y es única por `(pestaña, bloque, row_key, series_order, mes)`. El par clave con sufijo más orden no se repite: si el orden es 1, la clave es el texto mismo.
  - `mcp.cobros` cruza también por la serie.
  - `link` busca los cambios por texto sin sufijo más orden, no por la clave con sufijo, así que los cobros de la fila literal y de la serie no se mezclan.
- Hallazgo 2 (un 0 o un texto tipeado sobre un monto hacía desaparecer la factura sin rastro):
  - Nueva función SQL `shows_amount`: el valor mostrado tiene un dígito distinto de 0 y ninguna letra aparte de USD o ARS. Los formatos reales de las celdas de Pagos son `USD $1,234`, `-USD $9`, `USD $0` y porcentajes.
  - `mcp.cambios_de_estado_de_factura` incluye todo cambio de valor que pasa de no mostrar monto a mostrarlo o al revés, y del lado sin monto pone "sin factura". Esto también resuelve la primera mitad del nit: un 0 tipeado en una celda vacía pintada ya no aparece.
  - `link` usa la misma regla para decidir cuándo un monto tipeado en una celda de color cuenta como el cambio.
- Hallazgo 3 (una fórmula de Pagos ARG que no era un producto simple dejaba la cotización vacía sin avisar): las referencias se buscan en la fórmula tal cual está escrita, no en los factores del producto.
  - Con una sola referencia, la cotización sale de esa fila aunque la fórmula sea `=ROUND(50*1.21*B7)` o `=50*1.21*B7+0`. El USD inferido se guarda solo si la fórmula es un producto simple.
  - Con dos o más referencias, se abre `cotizacion_tipo_a_confirmar` con la celda.
  - En la base local (solo lectura, intérprete nuevo contra el anterior sobre la última lectura): en Craftech Pagos ARG, 7 de las 11 facturas sin cotización ahora la tienen; 3 de ellas referencian una fila de tipo desconocido y abren `cotizacion_tipo_a_confirmar`. Las 4 que siguen sin cotización tienen fórmulas solo con números (por ejemplo `=(a*b+c*d*e)*f`) y ya abrían `cotizacion_tipeada`. El USD inferido no cambia en ninguna factura.
- Hallazgo 4 (faltaba un test para "un monto tipeado en una celda ya verde cuenta como cobro"): hay un test nuevo, y el mutante que deja solo los cambios de color ahora muere.
- Nits:
  - Hay un comentario junto a la regla del `!`: en las planillas reales, las únicas fórmulas que copian otra pestaña son las de la fila 15 de Pagos de SleakOps.
  - El redondeo al centavo de la paridad tiene su propio caso dentro del test de paridad: un total que difiere en una millonésima.
  - Sin resolver: una celda vacía que se pinta sigue apareciendo en la historia. Los cambios de color no guardan el valor de la celda, así que la vista no los puede filtrar sin leer la lectura.

## Test plan

1. `test_each_color_is_a_state_and_cells_without_invoice_give_none`: los seis estados, un color fuera de la lista (`color_desconocido` y ninguna factura), un monto ilegible (`valor_ilegible`), un 0 con color, un magenta sin monto, una copia de Pagos ARG que no es factura, Marketplace como factura más y la serie repetida (`identidad_en_revision`).
2. `test_an_emptied_invoice_disappears_and_its_history_stays`: la factura vaciada deja `mcp.facturas` y queda en `mcp.cambios_de_estado_de_factura`, igual que un monto tipeado en una celda vacía.
3. `test_a_payment_gets_the_editor_date_once_drive_attributes_it`: un cobro de la primera lectura con "fecha desconocida"; uno nuevo con la ventana de detección y, después de la atribución, con la fecha del editor sin reinterpretar.
4. `test_a_payment_repainted_green_points_at_the_last_change`: verde, azul y verde otra vez dan el último cambio.
5. `test_a_row_inserted_above_keeps_its_payment`.
6. `test_an_arg_invoice_has_gross_net_rate_and_inferred_usd`: fórmula a la MEP, a "Dólar oficial", a una fila desconocida, tipeada y un monto sin fórmula.
7. `test_parity_is_zero_with_consistent_data_and_shows_a_missing_invoice`.
8. `test_a_painted_cell_without_amount_in_sleakops_is_a_churn_to_be_confirmed`.
9. `test_interpret_twice_leaves_the_same_facts_and_nothing_logs_amounts`.

Mutaciones: cambiar el estado del verde a "enviada" deja 6 tests en rojo; tomar el primer cambio a verde en vez del último deja en rojo el test 4.

Blast radius: toda lectura de Pagos y Pagos ARG pasa ahora por el intérprete dentro de su transacción (un error frena la lectura de esa pestaña). `cell_change` de tipo valor guarda los colores (el diff de todas las pestañas). Los tests de Pagos ARG de T-010 usan el orden real de filas.

Ronda de correcciones 1:

10. `test_a_row_whose_text_ends_in_a_number_is_not_mixed_with_a_series`: dos filas "Cliente Uno" y una tercera con el texto literal "Cliente Uno (2)" dan tres facturas. Al pintar de verde la segunda fila de la serie, su cobro apunta a ese cambio y el de la fila literal queda sin cambio.
11. `test_a_zero_or_a_text_over_an_amount_shows_in_the_history`: un texto sobre un monto azul y un 0 sobre un monto naranja dan "confirmada → sin factura" y "enviada → sin factura". Un 0 tipeado en una celda vacía no aparece.
12. `test_an_amount_typed_into_a_green_cell_is_the_payment_change`: celda vacía y verde en la primera lectura, monto tipeado en la segunda. El cobro apunta al cambio de valor.
13. `test_an_arg_formula_that_is_not_a_plain_product_still_reads_its_rate` (con `=ROUND(50*1.21*B7)` y con `=50*1.21*B7+0`): la cotización sale de la fila 7 y no hay USD inferido.
14. `test_an_arg_formula_with_two_references_opens_a_problem`: no hay cotización y se abre `cotizacion_tipo_a_confirmar` con la celda.
15. Test 7 ampliado: un total que difiere en una millonésima da diferencia 0.

Mutaciones de la ronda: corrí 10 mutantes, uno por cada corrección (la unicidad, la clave de `link`, el cruce por serie de `mcp.cobros`, el filtro y el estado de la historia, `shows_amount` con el 0, la búsqueda de referencias, el problema por dos referencias, el monto tipeado en verde y el redondeo de la paridad). Los 10 mueren. El harness de QA `plan/qa/evidence/T-011-r1-mutants.py` busca el texto anterior en algunas líneas y hay que actualizarlo para la ronda 2.

Blast radius de la ronda: solo 0010, `pagos.py` y la lista de columnas de `payment`. Ninguna vista ni tabla anterior a T-011 cambia.

## Post-merge

1. En la base local principal, 0010 ya está aplicada con el texto anterior a la ronda de correcciones 1, y `craftech-os migrate` se niega a seguir porque la migración cambió después de aplicarse. Hay que deshacerla a mano, en una sola transacción:
   ```sql
   BEGIN;
   DROP VIEW mcp.paridad_pagos, mcp.cambios_de_estado_de_factura, mcp.bajas, mcp.cobros, mcp.facturas;
   DROP TABLE payment, payment_total, client_churn, invoice;
   DROP FUNCTION a1_column(text), invoice_state(text);
   DROP FUNCTION IF EXISTS shows_amount(text);
   DELETE FROM schema_migration WHERE name = '0010_invoices.sql';
   COMMIT;
   ```
   Los comentarios que 0010 cambia en `issue.issue_type`, `mcp.issues.tipo` y `cell_change.new_color` se vuelven a escribir solos en el paso 2. Para verificar: `SELECT name FROM schema_migration ORDER BY name` termina en `0009`. En una base donde 0010 nunca se aplicó, este paso no hace falta.
2. `craftech-os migrate` (aplica 0010). Para verificar: `\d payment` muestra `series_order`, y `SELECT shows_amount('USD $0'), shows_amount('USD $1,200')` da `f, t`.
3. `craftech-os interpret --all` y revisar `mcp.paridad_pagos`, `cotizacion_tipeada` y `cotizacion_tipo_a_confirmar`. En Craftech Pagos ARG deberían quedar 4 facturas sin cotización, no 11.
4. Avisarle a Finanzas que el total de mayo de 2025 en Pagos de SleakOps no suma la fila 76.
5. Probar en la planilla de prueba de Ariel los criterios 1, 2, 3, 5 y 6 (colores, vaciado, cobro con atribución, fila insertada, paridad). Agregar un caso: tipear un 0 sobre una factura pintada y verlo en `mcp.cambios_de_estado_de_factura` como "sin factura".
