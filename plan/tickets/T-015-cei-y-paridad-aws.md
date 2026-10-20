---
id: T-015
title: "Fundings: el programa CEI como hito y paridad contra \"TOTAL PAGOS AWS\""
status: qa
priority: high
lane: core
depends_on: []
effort: M
milestone: B
branch: arielvinas/t-015-cei-y-paridad-aws
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

- [x] 1. Después de `uv run craftech-os interpret --all` en la base local, `mcp.fundings` tiene hitos con programa CEI de origen Pagos en las dos planillas, uno por cada celda con monto de la fila CEI: en Craftech las columnas E, H, K, N, Q, T y X de la fila 96; en SleakOps las columnas E, H, K, Q y T de la fila 102 (cada uno con su `cell_ref`).
- [x] 2. Los siete problemas `fila_sin_interpretar` de las celdas E96, H96, K96, N96, E102, H102 y K102 quedan cerrados, y no se abre ningún problema nuevo para la fila CEI con los datos actuales.
- [x] 3. Los hitos de Pagos que no son CEI no cambian: misma cantidad y mismos montos que antes del cambio (contar antes y después, por planilla).
- [x] 4. Un test con una fila CEI que tiene un monto en octubre de 2026 da un problema con esa celda y ningún hito para ese mes.
- [x] 5. Un test con una copia de otra planilla en la fila CEI da hito; la misma copia en una fila de cliente del bloque sigue sin dar nada.
- [x] 6. Reinterpretar dos veces no duplica hitos CEI ni reabre problemas.
- [x] 7. `select * from mcp.paridad_fundings_aws` devuelve una fila por planilla y mes con total, suma interpretada y diferencia. En septiembre de 2026 en Craftech la diferencia es 0. Cada mes con diferencia distinta de 0 queda listado en `## Implementation` con la causa encontrada (celda o hito), sin montos.
- [x] 8. El servidor MCP lista la vista nueva en su catálogo y el glosario explica CEI con la marca de "declaración de Ariel del 20-oct-2026, pendiente de ratificar por Emi y Ro".
- [x] 9. Ninguna escritura en Google Sheets ni en Drive; el diff no tiene nombres de clientes ni montos reales (tests con datos inventados).

## Out of scope

- La fila 82 "General | CEI" de la pestaña VENTAS de SleakOps, con montos de 2025 distintos a los de Pagos: queda para Emi y Ro.
- Las pestañas "Ventas con CEI" y "listado-ventas-CEI" de la planilla de Craftech.
- Montos tipeados después del corte en otras filas de "General" (por ejemplo la fila 48 de Craftech): siguen saliendo del log, sin cambios.
- Ratificar con Emi y Ro que "General" es bloque de funding o la ventana de la detección de duplicados (preguntas abiertas de T-012).
- Pantallas web nuevas: la vista de paridad se consulta por el servidor MCP.


## Implementation

**Piezas.**
- `config/sources.yaml` y `sources.py`: clave opcional nueva `funding_total` en las pestañas Pagos ("TOTAL PAGOS AWS" en las dos planillas), validada por texto como las otras filas.
- `interpret/pagos.py`: el mismo recorrido que arma `payment_total` arma `funding_total` (clave de fila, mes, monto, celda). Si la planilla no tiene la fila configurada, abre `fila_sin_interpretar` con clave `falta:funding_total`.
- `interpret/fundings.py`: una fila es CEI cuando abre el bloque "General" y su programa (columna B) es "CEI". En esa fila cuentan las copias de otra planilla y los meses posteriores al corte de la regla R28, hasta `CEI_LAST_MONTH` (septiembre de 2026). Un monto posterior abre `fila_sin_interpretar` con la celda y el motivo "el programa CEI terminó en septiembre de 2026", y no da hito. El hito CEI lleva `program_row` en su detalle (sin columnas nuevas) y la clave estable de siempre (bloque + fila + mes).
- `interpret/__init__.py`: registra la tabla `funding_total`. Los hitos CEI no piden alias, porque CEI no tiene cliente, así que no abren `alias_sin_cliente`.
- Migración `0012_cei_aws_parity.sql`:
  - tabla `funding_total`;
  - vista `mcp.paridad_fundings_aws`, con permiso para `mcp_reader`;
  - comentarios nuevos en `funding_milestone` y `mcp.fundings` que marcan CEI como declaración de Ariel del 20-oct-2026, pendiente de ratificar por Emi y Ro;
  - la resolución de los siete problemas.
- `mcp/server.py`: el glosario suma CEI (con la marca de declaración sin ratificar) y la paridad nueva. El catálogo la lista sin cambios, porque lee el esquema `mcp`.
- `plan/tickets/T-012-fundings.md`: la pregunta de la fila CEI queda respondida (secciones Implementation y Post-merge).

**Cierre de los siete problemas.** El ticket suponía un cierre automático de los problemas que dejan de reproducirse. No existe: un problema solo se resuelve con una fila en `issue_resolution`. Por eso la migración `0012` inserta la resolución `resuelto` de los `fila_sin_interpretar` abiertos de la fila de apertura de "General" en Pagos, con autor "T-015 (decisión de Ariel del 20-oct-2026)". Deja afuera los que tienen motivo (CEI posterior a septiembre de 2026), que deben quedar abiertos. Verificado en la base local: los siete quedan resueltos y reinterpretar no abre ninguno.

**Fecha del tracker en la paridad.** El log no tiene fecha de cobro para todos los hitos. Se usa el mes de `fecha_pago` y, si falta, el de `cobro_estimado`, porque el total de la planilla suma lo cobrado o por cobrar. En la base local:

| Unidad | Con fecha de pago | Solo con cobro estimado | Sin ninguna fecha |
|---|---|---|---|
| Craftech | 52 | 26 | 12 |
| SleakOps | 3 | 1 | 0 |

Los hitos sin ninguna fecha no se suman. Del tracker solo se suman los que tienen fecha desde marzo de 2026, porque hasta febrero de 2026 la fuente es Pagos. La unidad comercial se cruza con la planilla por el título: "sleakops" en el título va a SleakOps, el resto a Craftech.

**Rangos de "TOTAL PAGOS AWS".**
- Craftech: fila 3, `=SUM(96:204)` por columna.
- SleakOps: fila 2, `=SUM(76:105)` por columna.

Ninguna de las dos filas tiene texto en la columna A. Se ubican por el texto configurado y se encontraron en las dos planillas.

**Paridad en la base local (20-oct-2026).** Hay 72 meses con total. Septiembre de 2026 en Craftech cierra en 0, igual que todos los meses hasta febrero de 2026, salvo mayo de 2025 en SleakOps. Diecisiete meses tienen diferencia distinta de 0. En la tabla:
- "celdas de Pagos" son celdas que el total suma y que no se interpretan, porque están después del corte de la regla R28 en filas que no son CEI;
- "tracker" son las celdas de la pestaña FUNDINGS con hitos de ese mes.

| Planilla | Mes | Signo | Causa |
|---|---|---|---|
| Craftech | 2026-03 | + | celdas de Pagos R145, R173, R174, R176, R182; ningún hito del tracker en ese mes |
| Craftech | 2026-04 | + | celdas de Pagos S170, S177, S178, S181; tracker I4 (pago) |
| Craftech | 2026-05 | + | celdas de Pagos T174, T175, T178 (además de CEI T96, interpretada); tracker I3, I6 a I11 (pago) |
| Craftech | 2026-06 | + | celda de Pagos U178; tracker I12, I13, I15 a I18, I20 |
| Craftech | 2026-07 | + | celdas de Pagos V111, V178; tracker I21 a I31 |
| Craftech | 2026-08 | + | celdas de Pagos W97, W178; tracker I32 a I35 |
| Craftech | 2026-10 | − | celda de Pagos Y178; tracker I40 a I51, I55 (pago), I76 (cobro estimado) |
| Craftech | 2026-11 | − | celda de Pagos Z178; tracker I52, I54, I56, I58, I71 (pago) e I60 a I63, I78, I80, I81, I87, I88, I90 (cobro estimado) |
| Craftech | 2026-12 | − | ninguna celda de Pagos; tracker I57, I64, I65, I72, I75, I85 (cobro estimado) |
| Craftech | 2027-01 | − | tracker I66, I67, I73, I83, I89 (cobro estimado) |
| Craftech | 2027-02 | − | tracker I86, I91, I98 (cobro estimado) |
| Craftech | 2027-03 | − | tracker I68 (cobro estimado) |
| SleakOps | 2025-05 | + | antes del corte: la celda H76 la suma el total y no da hito; H80 y H102 sí se interpretan |
| SleakOps | 2026-03 | + | celdas de Pagos R78, R89; ningún hito del tracker en ese mes |
| SleakOps | 2026-04 | + | celdas de Pagos S77, S94; tracker I2, I5 (pago) |
| SleakOps | 2026-05 | + | celda de Pagos T92 (además de CEI T102, interpretada); ningún hito del tracker |
| SleakOps | 2026-11 | − | tracker I59 (cobro estimado); ninguna celda de Pagos |

Lectura:
- Después del corte, la planilla sigue teniendo montos tipeados en Pagos fuera de la fila CEI. El tracker los cubre con otras fechas, o no los cubre.
- El total usa el mes de la columna de Pagos y la vista usa la fecha del tracker.
- Desde diciembre de 2026 solo hay cobros estimados, que la planilla todavía no tiene.
- No se verificó si las diferencias de marzo a noviembre de 2026 se compensan entre meses.

La paridad muestra esto pero no lo corrige. Cuál de los dos lados manda después del corte es la pregunta abierta de T-012 sobre el criterio de corte.

**Cómo probarlo rápido.** Desde `app/`: `uv run pytest tests/test_fundings.py -k "cei or aws"`.

**Sin verificar.** Que CEI se pagara al cierre de cada trimestre y que septiembre de 2026 fuera el último pago. Es declaración de Ariel, pendiente de Emi y Ro.

## Test plan

1. Fila CEI con montos antes y después del corte (por ejemplo febrero y septiembre de 2026): da un hito por mes, con programa CEI, origen `pagos` y su celda.
2. Fila CEI con un monto en octubre de 2026: abre `fila_sin_interpretar` con esa celda y el motivo del fin del programa. No da hito para ese mes.
3. Copia de otra planilla (`IMPORTRANGE` o `!`) en la fila CEI: da hito. La misma copia en una fila de cliente del bloque: ni hito ni problema.
4. Fila de "General" que no es la primera, o cuyo programa no es CEI: sigue igual que antes, con hitos solo hasta febrero de 2026.
5. Reinterpretar dos veces: mismos hitos y mismos problemas (tipo, estado, celda, detalle).
6. `mcp.paridad_fundings_aws` con datos inventados:
   - hasta febrero de 2026, suma los hitos de Pagos;
   - desde marzo de 2026, suma CEI más el tracker de la unidad, por mes de pago o, si falta, de cobro estimado;
   - la diferencia es 0 cuando cierra.
7. Planilla sin la fila "TOTAL PAGOS AWS": abre `fila_sin_interpretar` `falta:funding_total`.
8. Base local: los conteos de los criterios 1 a 3, y la tabla de arriba con `select * from mcp.paridad_fundings_aws where diferencia <> 0 order by planilla, mes`.
9. Servidor MCP: el catálogo trae la vista y el glosario trae la entrada CEI con "pendiente de ratificar por Emi y Ro".

**Radio de impacto.**
- `interpret/pagos.py`: lo usan la interpretación de facturas y `payment_total` (`mcp.paridad_pagos`). El recorrido de totales cambió de forma.
- `interpret/fundings.py`: todos los hitos de Pagos. Verificado: los que no son CEI no cambiaron (misma cantidad y mismo hash de montos en las dos planillas).
- `interpret/__init__.py`: textos de alias de todas las pestañas (los hitos CEI se saltean).
- `sources.py`: validación de `sources.yaml`. Una clave mal escrita falla al cargar.
- `mcp/server.py`: el glosario que ve Claude Desktop.

## Post-merge

1. En la máquina local, desde `app/`, con `DATABASE_URL` apuntando a la base, correr en orden:
   - `uv run craftech-os migrate`: aplica `0012`;
   - `uv run craftech-os sources load`: carga `funding_total` desde `sources.yaml`;
   - `uv run craftech-os interpret --all`.

   Ya lo hice el 20-oct-2026 desde la rama. Con `main` es idempotente, porque la resolución de la migración solo toca problemas abiertos.
2. Verificar con estas consultas:
   - `select planilla, celda from mcp.fundings where origen = 'pagos' and programa ilike 'cei' order by 1, 2`: siete celdas en Craftech (fila 96) y cinco en SleakOps (fila 102).
   - `select count(*) from v_issue where issue_type = 'fila_sin_interpretar' and stable_key like '%:General:general:%' and status in ('abierto', 'reabierto')`: 0.
   - `select * from mcp.paridad_fundings_aws where diferencia <> 0 order by planilla, mes`: los diecisiete meses de la tabla de Implementation.
3. Pendiente:
   - con Emi y Ro: ratificar que CEI se pagaba al cierre de cada trimestre y que septiembre de 2026 fue el último pago;
   - con Ro: qué lado manda después del corte (las diferencias de la paridad desde marzo de 2026).
