# QA T-012 — Ronda 1

**Verdict: FAIL**
**Branch:** arielvinas/t-012-fundings @ 752f960
**Gates:** typecheck — (el repo no tiene) · lint ✓ (`ruff check`, `ruff format --check`: 45 archivos) · tests ✓ (286 passed con `TEST_DATABASE_URL`) · build — (no hay)
**Criteria:** 6/6 se cumplen tal como están escritos (2, 3 y 5 solo con el Google falso y la última lectura local; ver "No verificado"), pero F1 pierde fundings reales.
**Mutation:** 18 mutantes a mano (`plan/qa/evidence/T-012-r1-mutants.py`, corre solo `app/tests/test_fundings.py`): 12 muertos, 6 sobrevivientes (F2, F3). El cambio central muere: sacar el corte de meses de Pagos, el corte por fecha de carga, los 30 días, el registro de FUNDINGS o los hitos de Pagos pone la suite en rojo.

## Findings

### F1 [blocker] Los montos de CEI de la fila que abre el bloque "General" se pierden sin aviso
- **Repro:** en la base principal (solo lectura), la última lectura de "Facturación - Craftech Total", pestaña Pagos, fila 96 ("General | CEI | CEI"): `select celda, texto, formula from mcp.celdas where pestaña='Pagos' and planilla='Facturación - Craftech Total' and fila=96`. Después: `select * from mcp.fundings where celda in ('E96','H96','K96','N96')` y la misma búsqueda de esas celdas en `invoice`, `payment_total` y `accrual` de la pestaña Pagos.
- **Expected:** cada monto de funding anterior a marzo de 2026 en un bloque de funding da un hito de origen `pagos` o, si no se puede interpretar, un problema. Esa es la regla del ticket: "cada celda con monto de esas filas da un hito".
- **Actual:** la fila 96 tiene montos tipeados de CEI en meses de 2025, en las celdas E96, H96, K96 y N96 (dos de ellas con fórmulas de resta). No son subtotales: la columna E de las filas 97 a 140 suma otra cosa. `from_pagos` recorre `rows[1:]`, así que saltea la fila que abre el bloque. Esos montos no aparecen en `mcp.fundings` ni en ningún otro hecho (`accrual` tiene un N96, pero es de VENTAS), y tampoco abren un problema.
  En SleakOps pasa lo mismo y peor. "Facturación - SleakOps", pestaña Pagos, fila 102 ("General | CEI | CEI"): las celdas E102, H102 y K102 tienen montos, todos de 2025. El bloque "General" de SleakOps ni siquiera está en `funding_blocks`, y sus filas 103 a 105 son sumas en cero. Esos montos no son facturas ni fundings.
- **Por qué es blocker:** pierde datos. El ticket documenta que "la fila que abre el bloque" no da hito, pero lo decidió sin ver que en "General" esa fila trae los montos del programa CEI. En el bloque "Funding de AWS confirmados" esa fila solo tiene un `IMPORTRANGE`, y por eso se generalizó. La paridad no lo detecta porque compara el tracker con "Pagos confirmados", no con Pagos. Los tests no tienen ninguna fila de apertura con un monto tipeado.
- **Pregunta para Ariel/Ro (no la decide QA):** ¿la fila "General | CEI | CEI" es un hito por mes (programa CEI) en Craftech y en SleakOps? Y en SleakOps, ¿el bloque "General" es de funding? Hasta que se ratifique, la salida mínima es abrir un problema por cada monto de una fila de apertura, en vez de descartarlo en silencio.
- **Evidence:** consultas de arriba; las celdas T96 y X96 (de 2026) y Q96 (`IMPORTRANGE`) quedan fuera con razón, por el corte y por ser copias. Lo mismo vale para las celdas S77 y Y77 de la fila que abre "Fundings de AWS" en SleakOps: son de 2026-04 y 2026-10.

### F2 [major] La heurística de duplicados y el borde del corte no tienen test negativo
- **Repro:** `python -I plan/qa/evidence/T-012-r1-mutants.py <raíz>` con `TEST_DATABASE_URL`.
- **Expected:** cada condición de la regla R28 que el ticket enuncia hace caer un test si se rompe.
- **Actual:** sobreviven tres mutantes:
  - **"duplicate without amount":** se saca `k.amount_usd = p.amount_usd` de `DUPLICATES` y no cae ningún test. El único caso es un par con el mismo monto (H6/E6) y no hay ninguno del mismo cliente con distinto monto. Sin esa condición, cada hito del tracker se cruzaría con todos los hitos de Pagos del mismo cliente: en los datos reales serían decenas de `funding_duplicado` falsos.
  - **"duplicate without client alias":** se cambia `(k.alias_text = p.alias_text OR k.client_id = p.client_id)` por solo el texto, y tampoco cae ningún test. La mitad de la definición de "mismo cliente", la de alias distintos que apuntan al mismo cliente, no se prueba.
  - **"R28 cut date moved":** se mueve `CUT` del 25/2/2026 al 1/2/2026 y la suite sigue verde. El fixture tiene cargas del 10/1 y del 25/2, pero ninguna entre el 1/2 y el 24/2, así que el borde de "cargado antes del 25/2 va en Pagos" solo está probado de un lado.
- **Por qué es major:** son las condiciones que definen el criterio 4 y la regla R28 de la fuente por período. Hoy pasan los datos reales, pero un cambio que las rompa no lo detecta nadie.

### F3 [minor] Tres caminos de problemas sin test, uno de ellos tapado por F1
- **Actual:** sobreviven los mutantes:
  - **"tracker missing column issue":** sin el `if missing`, una columna requerida que falta en el encabezado no abre `fila_sin_interpretar` `falta:<texto>`. Además el código sigue con `at[role] = None`, así que el problema no se ve.
  - **"tracker unreadable amount":** un monto ilegible en el tracker no abre `valor_ilegible`.
  - **"copied amounts are milestones":** sin el salto de las fórmulas con `!` o `IMPORTRANGE`, la suite sigue verde. El test que dice cubrirlo pone el `IMPORTRANGE` en la fila que abre el bloque (líneas 89 y 97 de `test_fundings.py`), y esa fila ya se saltea entera (F1). Ningún test tiene una copia en una fila de cliente.
- **Expected:** un test por cada problema que el ticket promete.

### F4 [minor] El único `funding_duplicado` real parece un falso positivo
- **Repro:** `select stable_key, details from issue where issue_type='funding_duplicado'`.
- **Actual:** cruza la celda I4 de FUNDINGS (cargado en febrero de 2026) con la celda K110 de Pagos de Craftech (el mismo cliente con otro texto de alias, agosto de 2025). Un funding cargado en febrero de 2026 difícilmente es el mismo que figura en Pagos seis meses antes. La heurística (mismo monto y mismo cliente, sin mirar fechas) es la documentada en el ticket, así que no es un error de implementación, pero en el único caso real da ruido.
- **Sugerencia:** llevarlo a Ro, o acotar el cruce, por ejemplo con el mes de Pagos no anterior a unos meses antes de la carga en el tracker. Lo ratifican Emi y Ro.

### F5 [minor] "General" de Craftech como bloque de funding es un supuesto de implement
- **Actual:** el Contexto del ticket nombra solo "Funding de AWS confirmados" y "Fundings de AWS". Implement agregó "General" de Craftech: 89 de los 91 hitos de Pagos de Craftech salen de ahí. La evidencia lo apoya (las filas son MAP 2.0, POC CASH y CEI) y está escrito en `## Implementation`, pero es una regla financiera no ratificada. Junto con F1 (el "General" de SleakOps queda afuera), las dos planillas quedan tratadas de forma distinta para el mismo bloque.
- **Sugerencia:** confirmarlo con Emi y Ro en la misma pregunta de F1.

## No verificado
- **Criterios 2, 3 y 5 en la planilla de prueba de Ariel:** QA no escribe en Google Sheets. Se verificaron con el Google falso de los tests y con la última lectura local real:
  - `mcp.fundings`: 91 hitos de Pagos en Craftech, 10 en SleakOps y 94 del tracker (15 sin fecha de carga);
  - `mcp.paridad_fundings` coincide exactamente con la tabla del ticket (un solo mes de Craftech con diferencia, el resto en 0).

  Falta el paso humano: cargar un hito en la planilla de prueba y ver la fila y la celda en `mcp.fundings`.
- **Hitos del tracker sin fecha de carga:** son 15 (4 "Cargado en FP", 10 "Faltan datos para cargar" y 1 "Listo para cargar"). Se guardan como del tracker por decisión del ticket. Los 4 "Cargado en FP" sin fecha podrían ser anteriores al corte y estar también en Pagos; no se pudo saber.
- **Navegador:** no aplica, no hay interfaz en esta etapa.

## Split-outs sugeridos (fuera del alcance)
- [data-loss] Revisar las demás filas de apertura de bloques en las pestañas que leen `pagos.py` y `ventas.py`, por si alguna trae montos que hoy también se descartan. F1 muestra que "la fila que abre el bloque no tiene datos" no siempre vale.
