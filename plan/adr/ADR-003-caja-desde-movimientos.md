# ADR-003 — La caja se recalcula desde los movimientos de Consolidado; lo que los movimientos no explican se importa del Resumen con su origen

**Estado:** aprobado por Ariel el 2026-10-25 · **Fecha:** 2026-10-25 · **Origen:** pedido de Ariel del 25-oct-2026 (vista Caja como la pestaña «Resumen mensual Cash Flow ARG-USA»), diseño de referencia (versión 8, vista 4 · Caja, del diseño estilo ERP), docs/03-proposal.md §3.7 (paridad) y el patrón de ADR-002

## Necesidad

Ver en la web, de solo lectura, el cashflow mensual con los mismos bloques y filas que «Resumen mensual Cash Flow ARG-USA», con los meses reales recalculados desde los movimientos bancarios y no copiados de la pestaña. Saber de qué origen sale cada celda: recalculada, importada o fijada a mano. Comprobar contra la pestaña que el recálculo coincide.

## Diseño

Mismo paquete, misma imagen, mismos tres procesos. Sin dependencias nuevas.

1. **Una sola fuente de movimientos: la pestaña Consolidado de «Base informe Craftech».** En la última lectura tiene 21.535 filas y 17 columnas (Mes Corriente, Origen, Bank, Tipo Erogacion, Frecuencia, Tipo Mov, Rubro, Agrupador, Equipo, Moneda, Amount, TC, Amount USD, Detalle, Subdetalle, Area, Tipo gasto). Su fórmula en A1 ya junta las pestañas de los bancos (Mercury, Galicia, Caja, Macro, Mesh, Caja Crypto, USDC, VETA ARG, VETA USD, Credicoop) y las de ajustes (crédito fiscal y cobros de clientes): en la práctica es una pestaña derivada. Leerla evita reimplementar esa unión y deja una sola forma de fila; las pestañas de cada banco no se interpretan. Las lecturas anteriores tenían otra forma (396 filas y 40 columnas): el intérprete valida los encabezados y, si no coinciden, registra un problema y no interpreta esa lectura.
2. **Tabla `cash_movement`, proyección que se borra y se rehace por lectura, igual que en ADR-002.** Guarda `snapshot_id`, `row_key`, `cell_ref` y `rules_version`, más mes, banco, entidad, moneda, monto, tipo de cambio, monto en dólares, tipo de movimiento, rubro y agrupador. La entidad sale del banco según la regla ratificada de cuentas: Craftech S.A. en pesos (Galicia, Macro, Credicoop, Caja Córdoba); Craftech Inc. en dólares (Mercury y Mesh; la transferencia de Mercury a Mesh es interna y el gasto se registra en Mesh); históricas (VETA y cripto). Un banco que no está en la lista es un problema, no una suposición. Las filas con banco CLIENTES o AFIP vienen de las pestañas de ajuste y se guardan marcadas como ajuste. El intercompany se reconoce por el rubro «CAJA. Intercompany» (regla ratificada). Las cargas sociales son rubro «01. Sueldos» con agrupador CCSS: solo del personal argentino o híbrido, y solo en el cashflow.
3. **Sueldos solo como total.** No se leen las pestañas de sueldos por persona. En las filas de rubro «01. Sueldos», Detalle, Subdetalle y Equipo se guardan vacíos, porque pueden contener nombres de personas.
4. **Qué rubro va a qué fila: `config/cashflow_rows.yaml`, versionado.** Lista los bloques y filas de la pestaña (Argentina en miles de pesos, saldo final en dólares, Craftech Inc. en dólares, Craftech Inc. con pagos proyectados, «Diferencia entre proyectado y real») y, para cada fila, qué rubros, agrupadores o bancos suman y en qué unidad se muestra. Solo etiquetas, ningún monto. Una fila sin regla clara queda «sin regla» y su valor se importa.
5. **Cada celda dice de dónde sale.** Una segunda tabla, `cashflow_sheet_cell`, proyecta las celdas del Resumen desde su última lectura (fila, mes, valor, celda, lectura, si tiene fórmula). Celda **fijada a mano** = celda del Resumen sin fórmula; la lectura ya trae ese dato. La vista `cashflow_cell` (bloque, fila, mes, valor, origen) combina ambas, con origen `recalculada` (mes real y fila con regla), `importada` (mes proyectado, fila sin regla o celda fijada a mano) o `parametro` (el valor que fija la planilla para «traer dólares para cerrar el mes con 4 millones de pesos», parámetro ratificado del cashflow proyectado, importado con ese origen). Mes real: hasta el último mes completo con movimientos; mes en curso: se recalcula con lo que hay y se tinta; proyectados: el resto. **Dicho claro:** mientras no se ratifiquen las reglas de proyección, todos los meses proyectados son importados; en la primera versión cerca de la mitad de la tabla viene copiada de la planilla, rayada y con su origen visible.
6. **Vistas MCP v1, columnas en castellano:** `mcp.caja_mensual` (bloque, fila, mes, valor, unidad, origen, planilla, pestaña, celda, lectura), `mcp.movimientos_de_caja` (sin detalle en las filas de sueldos) y `mcp.paridad_cashflow`. `consultar_sql` y el catálogo cubren el resto.
7. **Paridad.** Compara solo las celdas `recalculada` contra la misma fila y mes del Resumen, en la unidad de la fila. De las `importada` informa la cantidad: compararlas consigo mismas no prueba nada. Las diferencias se muestran, no se corrigen; las incoherencias propias de la planilla también se ven sin corregir.
8. **Indicadores de cabecera, propuestos y a ratificar por Emi y Ro; la pantalla muestra la fórmula junto al número.** Caja hoy = último saldo real. Salida mensual = promedio de egresos de los últimos tres meses reales. Meses de cobertura = caja hoy ÷ salida mensual. Cierre de marzo = saldo final de marzo-27 del bloque «Craftech Inc.» y del bloque «Craftech Inc. con pagos proyectados».
9. **Migración 0014.** `cash_movement` y `cashflow_sheet_cell` con `COMMENT ON` en castellano y enumeraciones con `CHECK`; tipos nuevos en el `CHECK` de `issue`: `cash_header_mismatch` (encabezados que no coinciden), `cash_unknown_bank` (banco desconocido) y `cash_unmapped_rubro` (rubro sin regla). `details` con cantidades y referencias, nunca montos.
10. **Web: `/caja`, solo lectura, sobre las mismas vistas y sin migraciones.** Columna de conceptos fija con desplazamiento horizontal de los meses, mes en curso y proyectados tintados, celdas fijadas a mano rayadas, negativos en rojo, y gráfico por mes en SVG armado en el servidor, sin JavaScript y sin cambiar la política de contenido.

**Nota del 2026-10-26 (decisiones de Ariel en T-019).** Ningún valor del Resumen se muestra: todas las celdas se calculan desde los movimientos y el Resumen queda solo para ubicar filas y meses y para la paridad. El origen `importada` desaparece. Una fila sin regla ratificada y los meses proyectados quedan sin valor, con origen `sin_regla` y su motivo. Las filas «$ recibidos de la INC» y «USD enviados a la S.A.» de los dos bloques de Craftech Inc. quedan como `parametro`, sin valor, en los meses proyectados. Tampoco hay celdas fijadas a mano que rayar. Los indicadores son solo de Craftech Inc., en dólares:
- caja hoy = saldo final del último mes real cerrado;
- salida = promedio de Sueldos + Gastos + USD enviados de los últimos tres meses reales cerrados;
- cobertura = caja ÷ salida;
- cierres de marzo-27 = saldo final de cada bloque de Craftech Inc.

## Lo que NO se construye ahora

- **Motor de proyección:** cuando Emi y Ro ratifiquen cómo se proyectan los pagos y el parámetro de los 4 millones. Hasta entonces, los meses proyectados se importan.
- **Escenarios:** cuando Emi responda la pregunta abierta sobre los bloques de escenarios.
- **«Pagos en disputa»:** cuando Emi responda su pregunta abierta.
- **Facturas argentinas en el cashflow (dólares al tipo de cambio MEP con IVA, neto, o ambos):** cuando se ratifique.
- **Budget y resultado:** el resto de la etapa C.
- **API de Mercury:** etapa E (2027).
- **Interpretación incremental:** solo si rehacer Consolidado supera 10 segundos medidos.

## Seguridad en los límites

- **Planillas → intérprete:** entrada no confiable, análisis estricto de celdas y validación de encabezados. El intérprete corre como `craftech_app`, que puede borrar en las tablas de hechos y nunca en `snapshot` ni en `cell_change`.
- **Sueldos:** ninguna fila por persona en tablas ni vistas. Un test verifica que las vistas MCP no exponen Detalle, Subdetalle ni Equipo en filas de sueldos.
- **Claude Desktop → MCP:** `mcp_reader` solo lee; las vistas nuevas no se otorgan a `mcp_writer`.
- **Web:** solo en 127.0.0.1, sin login, con escape automático de HTML; nunca registra valores en los logs.
- **Logs y `system_event`:** solo identificadores y cantidades.
- **Datos de prueba:** ningún dato real en tests, fixtures ni capturas de QA; el diseño de referencia no aporta números al repo.

## Riesgos

- **La forma de Consolidado cambia otra vez.** Síntoma: problema `cash_header_mismatch` y la caja queda en la lectura anterior. Test: una lectura con encabezados viejos.
- **Rehacer 21.500 filas por lectura es lento.** Se mide en T-018 y se registra en `system_event`; más de 10 segundos abre la interpretación incremental.
- **Una regla de rubro a fila está mal.** Síntoma: la paridad muestra diferencias en esa fila; se ven, no se tapan.
- **«Mes Corriente» no es la fecha de lo percibido.** El cashflow va por lo percibido. Síntoma: la paridad falla en todas las filas a la vez, no en una.
- **Se filtran sueldos individuales.** Lo detecta el test de la sección de seguridad.

## Alternativas descartadas

- **Leer cada pestaña de banco:** duplica la fórmula de Consolidado y multiplica los puntos de falla.
- **Copiar el Resumen entero:** más simple, pero Ariel eligió recalcular y la paridad no probaría nada.
- **Proyectar los meses futuros ya:** sería inventar reglas no ratificadas.
- **Librería de gráficos en JavaScript:** una dependencia y un cambio de política de contenido para un gráfico de barras.
- **Un servicio aparte para la caja:** sin necesidad medida.

## Preguntas abiertas

- Filas del Resumen cuyo mapeo no sale de los rubros: las lista T-018; las dudosas van a Emi o Ro.
- Fórmulas de los indicadores, incluido el promedio de tres meses: a ratificar por Emi y Ro.
- Tolerancia de la paridad: se propone una unidad de la fila (mil pesos o un dólar).
- Si «Mes Corriente» es la fecha de lo percibido.
- Siguen abiertas: escenarios, «Pagos en disputa» e IVA en las facturas argentinas.

## Corte sugerido en tickets

| # | Unidad | Carril | Depende de |
|---|---|---|---|
| T-018 | Migración 0014, `cash_movement`, intérprete de Consolidado, esquema de pestaña en `sources.yaml`, `config/cashflow_rows.yaml`, medición del tiempo de reinterpretación | core | — |
| T-019 | `cashflow_sheet_cell` desde el Resumen, vista `cashflow_cell` con origen, indicadores, `mcp.caja_mensual` y `mcp.movimientos_de_caja` | core | T-018 |
| T-020 | `mcp.paridad_cashflow` | core | T-019 |
| T-021 | Pantalla `/caja`: tabla, indicadores y gráfico SVG | ui | T-019 |

Orden: T-018 → T-019 → (T-020 ∥ T-021). Etapa C.
