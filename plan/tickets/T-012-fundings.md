---
id: T-012
title: Fundings: esquema del tracker FUNDINGS e interpretación del bloque de AWS de Pagos y del tracker, con corte al 25/2/2026 y paridad
status: done
priority: high
lane: core
depends_on: [T-011]
effort: M
milestone: B
branch: arielvinas/t-012-fundings
---

## Context

ADR-002, sección 4, reglas de funding (R28, R22 y R15) y riesgos ("FUNDINGS sin esquema de bloques ni grilla").

Decisiones de Ariel del 19-oct-2026: ADR-002 aprobado.

Pregunta abierta a Ro, que no bloquea: para el corte, ¿decide la columna de mes o la fecha de carga del hito? El supuesto del ADR, que se implementa así hasta que Ro conteste, es la columna de mes en Pagos y la fecha de carga en el tracker. **Actualización del 22-oct-2026:** Ariel decidió cortar por mes de cobro en las dos fuentes (pendiente de ratificar por Ro); se implementa en T-016.

Verificado en el repo el 19-oct-2026:
- En `config/sources.yaml`, la planilla "FUNDINGS - Log de status [OFICIAL]" tiene:
  - FUNDINGS como pestaña CARGA, con encabezado "EMPRESA", clave A y sin bloques ni grilla;
  - "Pagos confirmados", "DB" y "SUMA" como pestañas DERIVADAS;
  - "2025" como HISTÓRICA.
- Los bloques de funding de Pagos se llaman distinto: "Funding de AWS confirmados" en Craftech y "Fundings de AWS" en SleakOps.
- Una regla de `plan/milestones.md`: un esquema nuevo en `sources.yaml` es un commit directo a main. Acá va dentro del ticket porque el intérprete depende de él, y en el mismo PR.

## Scope

**Dónde vive:**
- `config/sources.yaml`, la entrada de FUNDINGS
- `app/migrations/0011_fundings.sql`
- `interpret/fundings.py`
- tests

1. **Descubrir la estructura.** Leer la estructura del tracker en la planilla de prueba de Ariel y en la última lectura local (`mcp.celdas`): columnas de programa, oportunidad, fund claim ID, estado, monto, fechas de sign-off estimado y de carga. Escribir el esquema en `sources.yaml` y anotar en `## Implementation` qué columnas se usaron y por qué. Si la estructura no permite ubicar las columnas por encabezado, parar con `QUESTIONS:`.
2. **Migración 0011:**
   - Tabla `funding_milestone`, el hito de funding: origen (`pagos` o `tracker`), planilla, pestaña, `row_key`, programa y oportunidad como texto, fund claim ID, orden dentro del programa, si la clave es provisional, mes, monto en USD, estado, sign-off estimado, cobro estimado, fecha de carga, `snapshot_id`, `cell_ref` y `rules_version`.
   - Vistas `mcp.fundings` (cliente por alias) y `mcp.paridad_fundings`: por mes, la suma interpretada contra la pestaña "Pagos confirmados", con la diferencia.
   - `COMMENT ON` y `GRANT SELECT` a `mcp_reader`.
3. **Corte (regla R28).**
   - El bloque de AWS de Pagos de las dos planillas da hitos para las columnas de mes hasta febrero de 2026.
   - El tracker da hitos con fecha de carga desde el 25/2/2026.
   - La misma oportunidad en los dos lados abre `funding_duplicado` y se guardan los dos, sin deduplicar.
4. **Clave del hito.** Es el fund claim ID cuando existe; si no, programa + orden dentro del programa, marcada provisional.
5. **Cobro estimado (regla R22).** Es el sign-off estimado + 30 días.
6. **Funding separado (regla R15).** Ninguna vista suma fundings con facturas.
7. **Tests sintéticos:**
   - bloque de AWS con los dos nombres;
   - el corte en febrero y marzo de 2026;
   - un duplicado;
   - una clave provisional;
   - el cobro estimado;
   - la paridad en cero y distinta de cero.

**Descartado:**
- Deduplicar automáticamente: el ADR dice que el duplicado es un problema.
- Tabla `aws_program`: el programa va como texto hasta la etapa C.

## Acceptance criteria

- [ ] `config/sources.yaml` tiene el esquema de FUNDINGS y `craftech-os sources load` lo acepta.
- [ ] En la planilla de prueba, un hito cargado en el tracker aparece en `mcp.fundings` con origen `tracker`, cobro estimado = sign-off + 30 días y la celda de origen.
- [ ] Un funding en una columna de mes de enero de 2026 del bloque de AWS de Pagos aparece con origen `pagos`; uno en marzo de 2026 en ese bloque no genera hito por esa vía.
- [ ] La misma oportunidad en los dos lados abre `funding_duplicado` y las dos filas siguen en `mcp.fundings`.
- [ ] Con la planilla de prueba consistente, `mcp.paridad_fundings` da diferencia 0. Con las lecturas reales locales, la diferencia por mes queda en `## Implementation`.
- [ ] Ninguna vista de facturas incluye montos de funding.

## Out of scope

- Devengamiento del funding en dos vistas (regla R24, etapa C).
- Cargar el fund claim ID en la planilla: es de Ro, y el sistema nunca escribe en Sheets.
- Herramientas MCP (T-013) y pantallas (T-014).

## Implementation

**Estructura del tracker.** Se leyó la última lectura local de "FUNDINGS - Log de status [OFICIAL]". El encabezado está en la fila 1, de A a U: EMPRESA, TIPO DE FUNDING, STATUS, Unidad Comercial, Fecha De Carga En Fp, Fecha Estimada De Firmado De Sign-Off, Fecha Estimada De Cobro, CASH / CREDIT, MONTO A PEDIR, OPP ID, AWS ID, LINK HUBSPOT, CALCULADORA?, SOW, Fund request ID, RESPONSABLE AM, RESPONSABLE SA, Sign Off, Invoice cargada, Fecha de pago, Nota. Las columnas se ubican por el texto del encabezado, no por la letra: el esquema nuevo `columns` de `config/sources.yaml` dice qué encabezado cumple cada papel, y si falta uno obligatorio se abre `fila_sin_interpretar` con clave `falta:<encabezado>` y la pestaña no da hitos.

Columnas usadas y por qué:
- EMPRESA: la clave de fila y el texto del alias del cliente.
- TIPO DE FUNDING: el programa, como texto (no hay tabla de programas hasta la etapa C).
- STATUS y Unidad Comercial: se guardan como texto.
- Fecha De Carga En Fp: el corte de la regla R28. Desde el 25/2/2026 da hito; antes no, porque ese hito está en Pagos. **Las filas sin fecha de carga (todavía no cargadas) sí dan hito**. Reemplazado por T-016 (decisión de Ariel del 22-oct-2026, pendiente de Ro): el corte pasa a ser el mes de cobro.
- Fecha Estimada De Firmado De Sign-Off: el sign-off estimado. El cobro estimado se calcula como sign-off + 30 días (regla R22). La columna "Fecha Estimada De Cobro" de la planilla **no se lee**.
- MONTO A PEDIR: el monto en dólares. Una fila sin monto o en cero no es un hito.
- OPP ID: la oportunidad.
- Invoice cargada y Fecha de pago: para la paridad con "Pagos confirmados".
- Fund claim ID: está en el esquema como opcional, pero **la planilla no tiene esa columna**. Hay una "Fund request ID" (columna O), que es otro dato y no se usa. Mientras no exista la columna, todos los hitos tienen clave provisional: programa + " #" + orden dentro del programa del mismo cliente.

**Pagos.** El esquema de Pagos tiene una lista nueva, `funding_blocks`, que se valida contra `blocks`:
- en Craftech, "General" y "Funding de AWS confirmados";
- en SleakOps, "Fundings de AWS" y "General" (agregado en la ronda 1 de QA, para tratar igual el mismo bloque en las dos planillas; sus filas de cliente están vacías y hoy no da hitos).

Cada celda con monto de esas filas, en una columna de mes hasta febrero de 2026, da un hito de origen `pagos`. Lo demás no da hito:
- los montos traídos de otra planilla (fórmulas con `!` o `IMPORTRANGE`);
- los meses desde marzo de 2026.

La fila CEI de "General" es la excepción desde T-015 (ver el párrafo siguiente).

**Fila que abre un bloque de funding (ronda 1 de QA).** En "General" esa fila trae montos tipeados del programa CEI ("General | CEI | CEI"): en Craftech las celdas E96, H96, K96 y N96 (meses de 2025); en SleakOps las celdas E102, H102 y K102 (meses de 2025).
- **Comportamiento de T-012 (reemplazado).** Que fueran hitos del programa CEI era una regla financiera no ratificada, así que no se interpretaban como hito, pero tampoco se descartaban: cada monto tipeado de esa fila, en un mes hasta febrero de 2026, abría `fila_sin_interpretar` con clave bloque + clave de la fila + columna (por ejemplo `General:general:E`) y la celda. Las copias de otra planilla y los meses desde marzo de 2026 no daban nada. Verificado en la base local el 20-oct-2026: se abrían los siete problemas, y los hitos eran 91 en Craftech y 10 en SleakOps.
- **Comportamiento desde T-015 (vigente).** Por declaración de Ariel del 20-oct-2026, pendiente de ratificar por Emi y Ro, cada monto de esa fila, copias de otra planilla incluidas, es un hito del programa CEI hasta septiembre de 2026, también después del corte del 25/2/2026; un monto posterior abre `fila_sin_interpretar` con el motivo. Los siete problemas quedaron resueltos. En el resto de las filas que abren un bloque de funding, un monto tipeado sigue abriendo `fila_sin_interpretar`.

El programa sale de la columna B. **"General" se toma como bloque de funding** porque sus filas son programas de AWS (MAP, POC CASH, CEI). En Craftech de ahí salen 89 de los 91 hitos de Pagos. Esos montos nunca fueron facturas: solo el bloque del encabezado da facturas. Es un supuesto de implementación, no ratificado: está en las preguntas pendientes de abajo.

**Piezas.**
- Migración `0011_fundings.sql`:
  - tabla `funding_milestone`;
  - vista `mcp.fundings`, con el cliente por alias y `clave_hito`;
  - vista `mcp.paridad_fundings`;
  - nuevos comentarios en `issue.issue_type`, `issue.stable_key` y `mcp.issues.tipo`, con la definición de `funding_duplicado`.
- `interpret/fundings.py`: `interpret` lee el tracker y `from_pagos` lee los bloques de Pagos.
- `interpret/__init__.py`: registra FUNDINGS y detecta duplicados.
- `cli.py`: `interpret` informa "N fundings".

**Duplicados (regla R28).** Pagos no tiene columna de oportunidad, así que "la misma oportunidad" se aproxima: un hito del tracker y uno de Pagos son el mismo funding si tienen **el mismo monto y el mismo cliente**, es decir el mismo texto o textos cuyos alias apuntan al mismo cliente. Se guardan los dos y se abre `funding_duplicado`, con:
- clave: pestaña del tracker + fila, más pestaña de Pagos + bloque + fila + mes;
- detalle: planilla, pestaña y celda de cada lado, sin montos.

Es una heurística: dos fundings distintos del mismo cliente por el mismo monto también se marcan, y un mismo funding con montos distintos en cada lado no se detecta. El único caso real parece un falso positivo (hallazgo F4 de QA): cruza la celda I4 de FUNDINGS (cargado en febrero de 2026) con la celda K110 de Pagos de Craftech (el mismo cliente con otro texto de alias, agosto de 2025). No se acotó por fecha porque la ventana sería una regla nueva sin ratificar; el problema solo avisa, no borra ni junta nada.

**Preguntas pendientes para Emi y Ro (no bloquean; mientras tanto nada se pierde):**
1. La fila "General | CEI | CEI" de Pagos, en Craftech y en SleakOps, ¿es un hito por mes del programa CEI? **Respondida por Ariel y ratificada por Emi y Ro el 20-oct-2026 (regla R40), ver T-015**: sí, hasta septiembre de 2026; desde T-015 da hito y los siete problemas quedaron resueltos.
2. ¿"General" es un bloque de funding en las dos planillas? Hoy se toma así en las dos.
3. Para `funding_duplicado`, ¿alcanza con mismo cliente y mismo monto, o hay que acotar por fecha (por ejemplo, el mes de Pagos no más de N meses antes de la carga en el tracker)?

**Lecturas reales locales (20-oct-2026).**
- Hitos de Pagos: 91 en Craftech y 10 en SleakOps, de enero de 2025 a febrero de 2026.
- Hitos del tracker: 94, cargados del 25/2/2026 al 16/10/2026; 15 de ellos sin fecha de carga.
- Ningún hito tiene cliente todavía: no hay alias cargados para estas fuentes, así que se abren `alias_sin_cliente`.
- Hay 1 `funding_duplicado`, con un hito de Pagos de agosto de 2025.

Paridad real por mes: todos los meses dan 0 salvo uno, Craftech en 2026-06 (los montos están en `mcp.paridad_fundings` de la base local, no en el repo).

**Por qué hay diferencia en junio de 2026.** "Pagos confirmados" suma todas las filas del tracker con invoice cargada, también las cargadas antes del corte. En junio de 2026 se pagó una fila de Craftech cargada en el portal en enero de 2026. Por la regla R28 esa fila no da hito en el tracker. Tampoco lo da en Pagos, porque su cobro cae después de febrero de 2026. Con el supuesto vigente, **un hito cargado antes del corte y cobrado después no queda en ningún lado**. Esto alimenta la pregunta abierta a Ro: ¿el corte lo decide la columna de mes o la fecha de carga? Ariel decidió el 22-oct-2026 cortar por mes de cobro (pendiente de Ro), lo que cierra este caso; ver T-016.

## Test plan

Hay tests sintéticos en `app/tests/test_fundings.py`, con nombres y montos inventados y contra la base de prueba. Pagos usa los dos nombres de bloque y el tracker tiene sus columnas reales.

- **Bloque de AWS de Pagos con los dos nombres:**
  - un monto de enero de 2026 da hito `pagos`;
  - uno de marzo de 2026 no lo da;
  - un `IMPORTRANGE` en la fila que abre el bloque no da hito;
  - el orden dentro del programa da "MAP #2".
- **Fila de apertura y copias (ronda 1):** un monto tipeado de enero de 2026 en la fila "General | CEI" abre `fila_sin_interpretar` `General:general:D` con la celda D4 y no da hito; el de marzo de 2026 no abre nada; una fila de cliente con `='Otra planilla'!D5` no da hito ni problema.
- **Duplicados (ronda 1):** el mismo texto con otro monto no es duplicado; dos textos distintos con el mismo monto no lo son hasta que sus alias apuntan al mismo cliente, y después de `aliases load` + `interpret --all` sí (celdas H3 y D5). Una fila cargada el 24/2/2026 no da hito en el tracker.
- **Problemas del tracker (ronda 1):** sin la columna "MONTO A PEDIR" no hay hitos y se abre `falta:MONTO A PEDIR`; un monto "a definir" abre `valor_ilegible` en H2 y las otras filas siguen dando hito.
- **Tracker:**
  - las filas cargadas desde el 25/2/2026 dan hito, y también las que no tienen fecha de carga;
  - una fila cargada el 10/1/2026 no da hito;
  - el cobro estimado es sign-off + 30 días, aunque la planilla diga otra cosa;
  - una clave repetida lleva sufijo y orden 2;
  - una fila `[VACIO]` no da hito.
- **Fund claim ID:** con esa columna, es la clave y deja de ser provisional.
- **Duplicado:** el mismo cliente y monto en los dos lados abre `funding_duplicado` (celdas H6 y E6) y quedan las dos filas.
- **Paridad:** da 0 con datos consistentes. Al editar "Pagos confirmados" la diferencia es 1000; al sacar "Invoice cargada", es 1500.
- **Facturas sin fundings:** `mcp.facturas` y `mcp.paridad_pagos` no tienen montos de funding.
- **Reinterpretación:** reinterpretar no cambia nada. El evento y el CLI informan "4 fundings", y ni los eventos, ni los problemas, ni la salida tienen montos.
- **Esquema:** el esquema real tiene `columns` y `funding_blocks`, y los esquemas inválidos se rechazan con su mensaje.

Gates:
- `uv run pytest`: 289 pasan (ronda 1).
- `uv run ruff check` y `uv run ruff format --check`: limpios.

Ronda 1: el arnés de QA (`plan/qa/evidence/T-012-r1-mutants.py`, con el patrón del corte de Pagos ajustado al código nuevo) mata 18 de 18, y también muere volver a descartar la fila de apertura (restaurar `fundings.py` anterior deja rojo el test de la fila de apertura).

Mutaciones de la ronda 0, cada una deja `test_fundings.py` en rojo:
- sacar el corte de febrero de 2026 en Pagos;
- sacar los 30 días del cobro estimado;
- anular la condición de monto en la detección de duplicados.

## Post-merge

- En la máquina local, correr `uv run craftech-os migrate`, `uv run craftech-os sources load` y `uv run craftech-os interpret --all`. Esto lo hice el 20-oct-2026 desde la rama; con `main` es idempotente.
- Ariel o Ro: cargar alias para "FUNDINGS - Log de status [OFICIAL] / FUNDINGS" y para los bloques de funding de Pagos. Hasta entonces `mcp.fundings` no tiene cliente y la detección de duplicados solo compara textos iguales.
- Pendiente con Emi y Ro: las preguntas de `## Implementation` sobre "General" como bloque de funding y la ventana del duplicado. La de la fila CEI de "General" quedó ratificada por Emi y Ro el 20-oct-2026 (regla R40), ver T-015 (los siete problemas de esa fila quedaron resueltos ahí).
- Pendiente con Ro: ratificar el criterio de corte por mes de cobro que decidió Ariel el 22-oct-2026 (ver T-016), por la fila cargada en enero y cobrada en junio que con el criterio anterior no estaba en ningún lado.
