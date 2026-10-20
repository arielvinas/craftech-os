---
id: T-015
title: "Fundings: el programa CEI como hito y paridad contra \"TOTAL PAGOS AWS\""
status: todo
priority: high
lane: core
depends_on: []
effort: M
milestone: B
---

## Context

Pedido de Ariel del 20-oct-2026, a partir de una consulta: los montos de la fila "General | CEI | CEI" de la pestaña Pagos no aparecen como fundings, mientras que la fila "TOTAL PAGOS AWS" de la misma pestaña sí los suma.

Hechos dichos por Ariel el 20-oct-2026, **pendientes de ratificar por Emi y Ro** (se guardan como declaración de Ariel, no como regla ratificada):
- CEI es un programa de AWS que se pagaba al cierre de cada trimestre; por eso la fila tiene montos en meses salteados.
- El programa dejó de existir en el segundo trimestre de 2026. El pago de septiembre de 2026 fue el último.
- La fila es la misma en las dos planillas de facturación: fila 96 en "Facturación - Craftech Total" y fila 102 en "Facturación - SleakOps Total".

Decisiones de Ariel del 20-oct-2026:
- Febrero de 2026 en la fila CEI (celda Q96 en Craftech, Q102 en SleakOps) es una copia de otra planilla (`IMPORTRANGE`) que no está entre las fuentes. Para la fila CEI **se toma el valor de Pagos igual**: el monto copiado cuenta como hito, porque su planilla de origen no se lee.
- La paridad contra "TOTAL PAGOS AWS" se agrega en este ticket.

Verificado en el repo y en la base local el 20-oct-2026:
- `app/craftech_os/interpret/fundings.py`, `from_pagos`: la fila CEI es la primera fila del bloque "General" (`row is rows[0]`), así que cada monto tipeado hasta febrero de 2026 abre `fila_sin_interpretar` en vez de dar hito (decisión de T-012, ver `plan/tickets/T-012-fundings.md`, sección Implementation). Las copias de otra planilla (fórmulas con `!` o `IMPORTRANGE`) se saltean sin abrir nada, y los meses posteriores a `LAST_PAGOS_MONTH` (febrero de 2026, por el corte de la regla R28) también.
- Problemas `fila_sin_interpretar` abiertos de esa fila: siete. En Craftech las celdas E96, H96, K96 y N96; en SleakOps las celdas E102, H102 y K102 (todas meses de 2025).
- Montos que hoy se pierden sin aviso: los meses posteriores al corte (Craftech T96 y X96, mayo y septiembre de 2026; SleakOps T102, mayo de 2026), porque el log "FUNDINGS - Log de status [OFICIAL]" no trae CEI, y febrero de 2026 (Q96 y Q102) por ser copia.
- La celda E96 es una fórmula aritmética de constantes; el resto de los montos de la fila son tipeados.
- "TOTAL PAGOS AWS": en Craftech es la fila 3 (`=SUM(E96:E204)` por mes); en SleakOps es la fila 2 (`=SUM(E76:E105)` por mes). Hoy ninguna se lee como hecho ni tiene paridad.
- `app/craftech_os/interpret/pagos.py` ya arma hechos `payment_total` desde la fila "Total pagos USA" y los compara en la vista `mcp.paridad_pagos` (migración `0010_invoices.sql`). `mcp.paridad_fundings` (migración `0011_fundings.sql`) solo compara el log contra su pestaña "Pagos confirmados". La próxima migración es `0012`.
- En `mcp.fundings` hoy hay 91 hitos de Pagos en Craftech y 10 en SleakOps (sin unidad de negocio), y 90 y 4 del log (unidades Craftech y SleakOps).

## Scope

1. **Fila CEI como hito.** En `fundings.from_pagos`, la fila de apertura del bloque "General" cuyo programa (columna B) es "CEI" deja de abrir `fila_sin_interpretar`: cada monto de esa fila es un hito de funding con programa CEI, cobrado en el mes de la columna, en las dos planillas. Reglas propias de esa fila:
   - Vale para todos los meses hasta septiembre de 2026 inclusive, **también después del corte de la regla R28** (para CEI la fuente es siempre Pagos, porque el log no lo trae).
   - Una copia de otra planilla en esa fila cuenta como monto (decisión de Ariel); en el resto de las filas las copias siguen salteándose igual que hoy.
   - Un monto en un mes posterior a septiembre de 2026 no da hito: abre un problema (por ejemplo `fila_sin_interpretar` con un detalle que diga que el programa CEI terminó, o un tipo nuevo si el patrón de `issue` lo pide), con la celda.
   - La clave estable del hito sigue el patrón de los hitos de Pagos (bloque + clave de fila + mes), así una relectura no duplica.
   - El hito lleva una marca de procedencia que deje claro que la regla es una declaración de Ariel del 20-oct-2026 sin ratificar (por ejemplo en el detalle del hito o en el glosario del servidor MCP), sin inventar columnas que el resto de los hitos no tenga.
2. **Los siete problemas abiertos se resuelven** al reinterpretar, por el mecanismo normal de cierre de problemas que ya no se reproducen.
3. **Paridad contra "TOTAL PAGOS AWS".** `pagos.py` lee la fila "TOTAL PAGOS AWS" de cada planilla como un hecho nuevo (mismo patrón que `payment_total`: clave de fila, mes, monto, celda). Una migración `0012` crea una vista `mcp.paridad_fundings_aws` con, por planilla y mes: el total de la planilla, la suma de hitos interpretados y la diferencia redondeada a 2 decimales, a la manera de `mcp.paridad_pagos`. La suma interpretada es:
   - hasta febrero de 2026: los hitos de Pagos de esa planilla (incluido CEI);
   - desde marzo de 2026: los hitos CEI de esa planilla más los hitos del log cuya unidad de negocio corresponde a la planilla (Craftech → "Facturación - Craftech Total", SleakOps → "Facturación - SleakOps Total"), por mes de cobro. Si el log no tiene una fecha de cobro usable para algún hito, anotar en `## Implementation` qué fecha se usó y por qué.
   - La ubicación de la fila se toma por su texto ("TOTAL PAGOS AWS") en `sources.yaml`, no por número de fila.
4. **Servidor MCP.** La nueva vista se expone igual que `mcp.paridad_pagos` (catálogo y glosario del servidor MCP), con una línea en el glosario sobre CEI y su fin en septiembre de 2026, marcada como declaración de Ariel sin ratificar.
5. Actualizar `plan/tickets/T-012-fundings.md` en la sección Implementation y en Post-merge: la pregunta pendiente sobre la fila CEI pasa a "respondida por Ariel el 20-oct-2026, pendiente de ratificar por Emi y Ro, ver T-015".

Descartado: leer la planilla de origen del `IMPORTRANGE` de febrero de 2026 como fuente nueva. Agrega una fuente para un único monto de un programa que ya no existe.

## Acceptance criteria

1. Después de `uv run craftech-os interpret --all` en la base local, `mcp.fundings` tiene hitos con programa CEI de origen Pagos en las dos planillas, uno por cada celda con monto de la fila CEI: en Craftech las columnas E, H, K, N, Q, T y X de la fila 96; en SleakOps las columnas E, H, K, Q y T de la fila 102 (cada uno con su `cell_ref`).
2. Los siete problemas `fila_sin_interpretar` de las celdas E96, H96, K96, N96, E102, H102 y K102 quedan cerrados, y no se abre ningún problema nuevo para la fila CEI con los datos actuales.
3. Los hitos de Pagos que no son CEI no cambian: misma cantidad y mismos montos que antes del cambio (contar antes y después, por planilla).
4. Un test con una fila CEI que tiene un monto en octubre de 2026 da un problema con esa celda y ningún hito para ese mes.
5. Un test con una copia de otra planilla en la fila CEI da hito; la misma copia en una fila de cliente del bloque sigue sin dar nada.
6. Reinterpretar dos veces no duplica hitos CEI ni reabre problemas.
7. `select * from mcp.paridad_fundings_aws` devuelve una fila por planilla y mes con total, suma interpretada y diferencia. En septiembre de 2026 en Craftech la diferencia es 0. Cada mes con diferencia distinta de 0 queda listado en `## Implementation` con la causa encontrada (celda o hito), sin montos.
8. El servidor MCP lista la vista nueva en su catálogo y el glosario explica CEI con la marca de "declaración de Ariel del 20-oct-2026, pendiente de ratificar por Emi y Ro".
9. Ninguna escritura en Google Sheets ni en Drive; el diff no tiene nombres de clientes ni montos reales (tests con datos inventados).

## Out of scope

- La fila 82 "General | CEI" de la pestaña VENTAS de SleakOps, con montos de 2025 distintos a los de Pagos: queda para Emi y Ro.
- Las pestañas "Ventas con CEI" y "listado-ventas-CEI" de la planilla de Craftech.
- Montos tipeados después del corte en otras filas de "General" (por ejemplo la fila 48 de Craftech): siguen saliendo del log, sin cambios.
- Ratificar con Emi y Ro que "General" es bloque de funding o la ventana de la detección de duplicados (preguntas abiertas de T-012).
- Pantallas web nuevas: la vista de paridad se consulta por el servidor MCP.

## Implementation

## Test plan

- Unitarios en `app/tests/test_fundings.py` (y en el test de `pagos.py` para el total AWS), con bloques inventados: fila CEI con montos antes y después del corte, con copia de otra planilla, con un monto posterior a septiembre de 2026; fila de cliente con copia (sigue sin dar nada).
- Migración `0012` aplicada sobre una base vacía y sobre la local.
- Contra la base local: los conteos de los criterios 1 a 3 y la consulta del criterio 7.

## Post-merge

- En la máquina local, correr `uv run craftech-os migrate`, `uv run craftech-os sources load` y `uv run craftech-os interpret --all`, y verificar los criterios 1, 2 y 7 contra la base.
- Pendiente con Emi y Ro: ratificar que CEI se pagaba al cierre de cada trimestre y que septiembre de 2026 fue el último pago.
