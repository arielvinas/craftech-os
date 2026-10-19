# ADR-002 — Los ingresos se interpretan como proyección determinística de las lecturas, con el cliente resuelto por alias al consultar

**Estado:** aprobado por Ariel el 2026-10-19 · **Fecha:** 2026-10-19 · **Origen:** `docs/03-proposal.md` §6 (etapa B) y §3.3–3.4, ajustado por ADR-001

## Necesidad

Convertir las lecturas crudas de las pestañas de ingresos (VENTAS, Pagos y Pagos ARG de las dos planillas de Facturación, y el tracker FUNDINGS) en hechos de negocio: devengado por cliente y mes, factura con estado por color, cobro, baja de SleakOps, hito de funding y cotización. Atarlos a clientes canónicos con razones sociales y aliases, sin adivinar nada: lo que no se puede interpretar se reporta como problema. Hacerlos consultables desde Claude Desktop con referencia al origen y visibles en tres pantallas de solo lectura. Con esto la etapa "ya sirve".

## Diseño

Mismo paquete, misma imagen, mismos tres procesos. Lo nuevo es un módulo `interpret` en el worker y cuatro migraciones de `core`.

**1. Interpretación = proyección por pestaña, borrable y repetible (ADR-001).** Cuando el worker guarda una lectura nueva de una pestaña con esquema, reinterpreta esa pestaña entera desde esa lectura: borra sus hechos e inserta los nuevos en una transacción, con `snapshot_id` y `rules_version`. También corre a mano con `craftech-os interpret [--all]`. No se interpretan diferencias: la pestaña completa cada vez (son cientos de filas; medir, no optimizar).

**2. Los hechos guardan la clave cruda de la fila; el cliente se resuelve al consultar.** Ningún hecho tiene `client_id`. Cada hecho lleva pestaña, bloque, `row_key` (el texto normalizado que la etapa A ya usa), columna de mes, `snapshot_id`, `cell_ref` y `rules_version`. El cliente aparece en las vistas por join con `client_alias`. Así una decisión de alias nueva no exige reinterpretar, y una fila sin alias sigue siendo un hecho anclado a su texto, con problema `alias_sin_cliente`, en vez de una adivinanza. Esto es "lo no ratificado se guarda, no se interpreta".

**3. Claves estables por hecho** (para problemas y anotaciones):
- Devengado: pestaña + `row_key` + mes.
- Factura: pestaña + bloque + `row_key` + mes + entidad legal. Es la regla R26 en palabras: dos contratos del mismo cliente son dos filas, y el mismo texto repetido en un bloque son dos series con sufijo de orden, marcadas "identidad en revisión".
- Hito de funding: fund claim ID cuando existe; si no, programa + orden dentro del programa, marcado provisional.
- Cotización: tipo + mes + pestaña.

**4. Reglas que aplica el intérprete, enunciadas:**
- Entidad legal determinística por pestaña: Pagos ARG es Craftech S.A.; todo lo demás, Craftech-io Inc (R25). Las dos filas de `legal_entity` se siembran en la migración: son de Craftech, no datos de clientes.
- Devengado desde VENTAS: USD neto de IVA tal como está en la celda; el prorrateo por días lo hizo Ro, no se recalcula (R1, R14). "Ventas Argentina 2025" no se lee (R37). Unidad de negocio y POD viajan como texto de la planilla.
- Estado de factura por color, mapeo único: cian "a confirmar", azul "confirmada", naranja "enviada", verde `#d9ead3` "pagada", magenta "retraso"; monto sin color = "a facturar"; color fuera de la lista = problema `color_desconocido` (R29).
- Celda vaciada = la factura deja de existir; 0 con color o magenta sin monto = igual que vaciada; ilegible = problema, nunca se adivina (R30).
- Factura ARG: bruto en ARS, neto = bruto / 1,21, IVA 21% (R14). La cotización se toma de la fila que referencia la fórmula de la celda (R10). Las filas de cotización se ubican por su texto en la columna A, no por número de fila (el anexo del v0.9 advierte inserciones). Fila 27 es la MEP operativa; si la 23 difiere, problema `cotizacion_discrepante`. Fórmula que referencia la fila 1 "Dólar oficial" (pregunta F-01 abierta): se guarda esa cotización marcada "tipo a confirmar". Cotización tipeada a mano: se guarda como cotización de esa factura y problema `cotizacion_tipeada` (R38). El USD base que aparece en fórmulas como `7200*1.21*M1` se guarda en la factura como monto inferido, sin crear contrato.
- Cobro y cambios de estado salen de `cell_change`, no de una tabla nueva: el cobro es el cambio de color que puso verde esa celda, unido por pestaña + bloque + `row_key` + columna de mes (nunca por `cell_ref` solo, porque las filas se mueven); fecha = la del editor atribuido por Drive, si no la ventana de detección (R4). Celda ya verde en la importación inicial: cobro con "fecha desconocida", no inventada.
- Baja de SleakOps: celda pintada sin monto en esa planilla (R31). Hasta que Emi responda F-05, cualquier color sin monto ahí es baja, marcada "color a confirmar".
- Funding: bloque AWS de Pagos para columnas de mes hasta feb-2026; tracker FUNDINGS para hitos cargados desde el 25/2/2026 (R28). La misma oportunidad en ambos = problema `funding_duplicado`, no se deduplica. Cobro estimado = sign-off estimado + 30 días (R22). Funding siempre separado de las facturas (R15); el devengamiento en dos vistas (R24) es de la etapa C.
- Marketplace = una factura más del cliente (R16).

**5. Cambio deliberado a la etapa A:** la lectura pasa a conservar las celdas vacías con solo color en pestañas CARGA con esquema. Sin eso las bajas y el "magenta sin monto" son invisibles (ya anotado en `plan/improvements.md`). Cambia una vez el hash de cada pestaña: una lectura extra, inofensiva.

**6. Clientes canónicos:** `client` (nombre de fantasía, id de HubSpot), `client_legal_entity` (1:n: razón social, país, tipo y número de tax ID, sistema de origen Bejerman/Zoho, plazo de pago; default 10 días), `client_alias` (texto normalizado por fuente → cliente, quién decidió, cuándo, motivo; solo se agregan filas, la última manda). Los datos entran por dos caminos, ambos fuera del repo: `craftech-os clients load-zoho <Contacts.csv>` y `craftech-os aliases load <csv>` leyendo de `~/repos/craftech-os-data/`, y la herramienta MCP `vincular_alias` para decisiones nuevas desde Claude Desktop. Las 51 decisiones del artefacto de Aliases se exportan a ese CSV; el worker nunca busca el artefacto.

**7. Tablas nuevas** (inglés, con `COMMENT ON` en español, enumeraciones por CHECK): `legal_entity`, `client`, `client_legal_entity`, `client_alias`, `accrual`, `invoice`, `payment`, `client_churn`, `funding_milestone`, `fx_rate`, más los tipos de problema nuevos en el CHECK de `issue`: `alias_sin_cliente`, `cotizacion_tipeada`, `cotizacion_discrepante`, `cotizacion_tipo_a_confirmar`, `funding_duplicado`, `identidad_en_revision`, `fila_sin_interpretar`. `details` sigue sin montos.

**8. Servidor MCP v1:** cada migración de `core` crea sus vistas en el esquema `mcp` con columnas en español y origen (planilla, pestaña, celda, lectura): `devengados`, `facturas`, `cobros`, `bajas`, `fundings`, `cotizaciones`, `clientes`, `razones_sociales`, `aliases`, `cambios_de_estado_de_factura` y dos de paridad: `paridad_pagos` (total mensual de las filas "TOTAL" de la planilla contra la suma de facturas interpretadas) y `paridad_fundings` (contra la pestaña "Pagos confirmados"). `consultar_sql` y el catálogo ya cubren la consulta libre; la única herramienta nueva es `vincular_alias`.

**9. Web:** pantallas Facturas y cobros, Fundings y Clientes, de solo lectura, sobre las mismas vistas. Sin migraciones.

## Lo que NO se construye ahora

- **`contract`:** la factura guarda el USD base inferido de la fórmula. Tabla recién cuando Emi y Ro revisen los contratos inferidos o cuando la etapa C necesite comisiones.
- **`aws_program` y `dimension` con vigencia:** programa, unidad de negocio y POD van como texto. Tablas cuando el P&L de la etapa C necesite vigencias.
- **Objetivo de venta (F-23):** cuando Ro diga si es meta y quién la carga; mientras tanto se ve en `mcp.celdas`.
- **Vencimiento y alertas de cobro:** plazo de pago se guarda; la fecha de vencimiento se calcula en una vista; las alertas son de la etapa D.
- **Devengamiento del funding en dos vistas (R24):** etapa C.
- **Interpretación incremental por diferencias:** solo si reinterpretar una pestaña supera 10 segundos medidos.
- **Zoho como fuente de facturas:** solo semilla de razones sociales y plazos; cruce con la planilla cuando se entienda la diferencia de totales que anota `docs/fuentes-zoho.md`.

## Seguridad en los límites

- **Planillas → intérprete:** el contenido sigue siendo entrada no confiable: parseo estricto de montos, fechas, colores y fórmulas; lo que no parsea es problema. El intérprete corre como `craftech_app`; su DELETE alcanza solo tablas de hechos, nunca `snapshot` ni `cell_change`.
- **Archivos de Zoho y aliases → CLI:** fuera del repo, en `~/repos/craftech-os-data/` (ignorado por git igual que la clave). Los loaders registran cantidades, nunca nombres. Nada de eso en tests ni fixtures: pruebas con nombres inventados sobre la planilla de prueba de Ariel.
- **Claude Desktop → MCP:** `mcp_reader` ve ahora razones sociales, tax IDs y montos a través de vistas; es el mismo nivel de confianza que `mcp.celdas` ya otorga y lo mismo que expone una contraseña filtrada de ese rol (local, 127.0.0.1, FileVault). `mcp_writer` suma INSERT en `client` y `client_alias`, auditado por el trigger `record_mcp_write`. Sin UPDATE ni DELETE en ningún rol MCP.
- **Web:** sigue en 127.0.0.1, sin login, autoescape; muestra nombres y montos, nunca los registra en logs.
- **Logs y `system_event`:** ids y cantidades (hechos insertados, problemas abiertos), nunca valores.

## Riesgos

- **Deriva de estructura de pestañas** (filas insertadas sobre bloques, encabezados pisados). Síntoma: salto de problemas `fila_sin_interpretar` en una corrida. Prueba: fixture con filas corridas. Métrica: problemas abiertos por pestaña por corrida.
- **Interpretación equivocada sin que nadie lo note.** Síntoma: `paridad_pagos` o `paridad_fundings` con diferencia ≠ 0 en algún mes. Es el criterio de aceptación de la etapa.
- **FUNDINGS sin esquema de bloques ni grilla** en `config/sources.yaml`: el ticket de fundings empieza descubriendo la estructura en la planilla de prueba. Hasta que Ro cargue el fund claim ID, las claves son provisionales.
- **Fecha de cobro imprecisa** por atribución "una de" o "sin datos". Se guarda la certeza junto al cobro; métrica: porcentaje de cobros con fecha cierta.
- **Reinterpretación lenta** al crecer las lecturas. Métrica: segundos por pestaña en `system_event`; umbral 10 s.

## Alternativas descartadas

- **Tablas de eventos por hecho (`InvoiceIssued`, `InvoiceStatusChanged`, `PaymentReceived`):** `cell_change` ya es ese registro con autor y ventana; duplicarlo en otra tabla viola la decisión de ADR-001 de no versionar hechos.
- **Escribir `client_id` en los hechos:** obliga a reinterpretar en cada alias nuevo y mezcla decisión humana con proyección.
- **Interpretar desde las diferencias:** más código, mismo resultado; la pestaña entera es determinística y chica.
- **Aliases en YAML en el repo:** son datos de clientes.
- **Zoho como fuente primaria de facturas:** las planillas son la verdad en esta etapa; los totales no coinciden y nadie explicó por qué.
- **Servicio de interpretación aparte o dbt:** una caja más para cientos de filas.

## Preguntas abiertas

- F-01 (Emi): ¿"Dólar oficial" fila 1 es cotización pactada? Hasta entonces: tipo a confirmar.
- F-05 (Emi): color exacto de la baja de SleakOps.
- Corte de fundings (Ro): ¿la columna de mes decide el lado del 24/2/2026, o la fecha de carga del hito? Supuesto: columna de mes en Pagos, fecha de carga en el tracker.
- Plazos (Emi): Zoho dice Net 10 o Due on Receipt y ningún cliente a 30 días; el v0.9 habla de excepciones de 30.
- R32 (Emi): confirmación de razones sociales múltiples por cliente; se modela 1:n igual.
- Ariel: exportar las 51 decisiones de aliases al CSV fuera del repo.

## Corte sugerido en tickets

| # | Unidad | Carril | Depende de |
|---|---|---|---|
| T-009 | Clientes canónicos: migración 0008 (`legal_entity`, `client`, `client_legal_entity`, `client_alias`, vistas `clientes`/`razones_sociales`/`aliases`), loaders de Zoho y aliases, lectura que conserva celdas con solo color | core | T-008 |
| T-010 | Devengados y cotizaciones: migración 0009 (`accrual`, `fx_rate`, tipos de problema), módulo `interpret` con VENTAS y filas de cotización de Pagos ARG, hook en worker y `craftech-os interpret` | core | T-009 |
| T-011 | Facturas, cobros y bajas: migración 0010 (`invoice`, `payment`, `client_churn`, vistas incl. `cambios_de_estado_de_factura` y `paridad_pagos`), intérprete de Pagos y Pagos ARG | core | T-010 |
| T-012 | Fundings: esquema de FUNDINGS, migración 0011 (`funding_milestone`, vista `fundings`, `paridad_fundings`), intérprete del bloque AWS y del tracker | core | T-011 |
| T-013 | MCP v1: herramienta `vincular_alias`, catálogo y glosario con los hechos nuevos, pruebas de solo lectura | api | T-012 |
| T-014 | Pantallas Facturas y cobros, Fundings y Clientes | ui | T-012 |
