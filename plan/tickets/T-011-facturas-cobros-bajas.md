---
id: T-011
title: Facturas, cobros y bajas: interpretación de Pagos y Pagos ARG por color, cobros desde los cambios de celda y paridad con los totales
status: todo
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
- [ ] Una factura de Pagos ARG muestra bruto en ARS, neto = bruto / 1,21 y la cotización de la fila que referencia su fórmula. Con la cotización tipeada se abre `cotizacion_tipeada`.
- [ ] Mover una fila de cliente (insertar una fila arriba) en la planilla de prueba no duplica ni pierde su cobro.
- [ ] En la planilla de prueba con datos consistentes, `mcp.paridad_pagos` da diferencia 0 en todos los meses. En la base local con las lecturas reales, la diferencia de cada mes queda registrada en `## Implementation`, y cada mes distinto de 0 tiene un problema abierto que lo explica o una nota.
- [ ] Una celda pintada sin monto en Pagos de SleakOps aparece en `mcp.bajas` marcada "color a confirmar".

## Out of scope

- Los bloques de funding de AWS de Pagos (T-012).
- Alertas de cobro y vencimientos vencidos (etapa D); facturas desde Zoho.
- Herramientas MCP (T-013) y pantallas (T-014).
