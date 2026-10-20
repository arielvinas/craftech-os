# QA T-010 — Ronda 2

**Verdict: PASS**
**Branch:** arielvinas/t-010-devengados-y-cotizaciones @ 5488f1a
**Gates:** typecheck — (el repo no tiene) · lint ✓ (`ruff check`) · formato ✓ (`ruff format --check`, 50 archivos; ahora excluye `plan/`) · tests ✓ (253 passed, con `TEST_DATABASE_URL` y las claves de los roles del servidor MCP) · build — (no corrido: la rama no toca `infra/Dockerfile` ni las dependencias)
**Criteria:** 7/7 sin incumplir; los criterios 1 y 2 siguen verificados solo con el Google falso (ver "No verificado"), igual que en la ronda 1.
**Mutation:** harness de la ronda 1 (`plan/qa/evidence/T-010-r1-mutants.py`): 16/16 muertos (antes 13/16). Harness nuevo sobre los arreglos (`plan/qa/evidence/T-010-r2-mutants.py`, corre **solo** los cinco tests nuevos, para atribuir): 9/9 muertos.

Alcance: el commit de arreglos `98dd12b` y todo `git diff main...HEAD` de nuevo. Entorno: base de prueba `craftech_os_test` y, en modo solo lectura (`read_only = True`), la base principal con las lecturas reales. Nada se escribió en Google Sheets, en Drive ni en la base principal. No hay pantallas en este ticket: la superficie es la base, las vistas `mcp` y el comando `craftech-os interpret`.

## Findings

### F1 [minor] Un número fuera del rango de fechas en una celda de mes del encabezado sigue tumbando la lectura
- **Repro:** en el fixture de `test_interpret.py`, poner en el encabezado de VENTAS (o en el "Mes" de Pagos ARG) una celda con formato `mmmm yyyy` y valor `99999999` (o `-800000`), y correr `craftech-os import`.
- **Expected:** que la columna no sea un mes (como un `2025` sin año en el formato) y que sus montos abran `fila_sin_interpretar`.
- **Actual:** `OverflowError: date value out of range` en `cells.month` (`app/craftech_os/interpret/cells.py:20`). No es `psycopg.DataError`, así que el importer no la atrapa: misma salida que F1 de la ronda 1 (no se guarda la lectura y el worker queda en ciclo de caídas).
- **Por qué es minor:** hace falta un valor mayor que 2.958.465 (año 9999) o negativo enorme en una celda de mes. Lo más parecido a algo real sería pegar solo valores de una fila de montos en pesos sobre el encabezado "Mes" de Pagos ARG. Es la clase ya registrada en `plan/improvements.md` (QA T-010 r1, `[robustez]`); el arreglo de una línea sería pedir que el serial esté en el rango de `date` antes de convertirlo.
- **Evidencia:** sonda descartable (borrada) sobre el fixture; traza terminada en `cells.py:20 OverflowError`.

## Re-verificación de la ronda anterior

- **F1 (r1) [major] mes repetido / sufijo literal → `UniqueViolation`:** ✓ resuelto. `cells.grid` deja cada mes solo en su primera columna; los montos de la columna repetida abren `fila_sin_interpretar` y la lectura se guarda (4 lecturas en el test). La unicidad de `accrual` pasó a `(source_tab_id, block, alias_text, series_order, month)`; leyendo `compare.blocks`, el orden de la serie se cuenta por clave dentro de cada bloque y los bloques repetidos llevan sufijo, así que la unicidad ya no depende de que el sufijo no choque con un texto. Sondas extra sin caída: los tres meses del encabezado iguales en VENTAS y Pagos ARG, y una fila "Cliente" (mismo texto que el encabezado) con montos, que queda como `cliente (2)`, serie 2. Muta: sacar el `m not in months.values()` o volver a la restricción por `row_key` → los tests nuevos se ponen rojos.
- **F2 (r1) [minor] mes repetido en Pagos ARG pisa la cotización:** ✓ resuelto. La columna sin mes propio abre `fila_sin_interpretar` por celda (`Mes:mep:D`, `(antes del encabezado):dolar oficial:D`). Muta (`for c in months`) → rojo.
- **F3 (r1) [minor] la rama `valor_ilegible` del intérprete no tenía test:** ✓ resuelto con una celda `#REF!` en VENTAS y en Pagos ARG; mutar cualquiera de las dos ramas → rojo.
- **F4 (r1) [minor] resguardo de pestaña sin esquema o no CARGA sin test:** ✓ resuelto; mutar cada mitad de la condición por separado → rojo.
- **F5 (r1) [nit] número sin formato de fecha tomado como mes; `.replace(day=1)` sin test:** ✓ resuelto. Un número es mes solo si su formato muestra el año (`yy`). En datos reales, los cuatro encabezados tienen las 36 celdas de mes con `mmmm yyyy`, así que el cambio no pierde ningún mes. Un mes con formato sin año (`mmmm`) deja de ser mes y sus montos abren `fila_sin_interpretar`: se ve, no se pierde nada sin aviso. El caso del serial fuera de rango queda como F1 de esta ronda.

## Criterios, uno por uno

1. **Lectura nueva de VENTAS → `mcp.devengados` con origen.** ✓ con el Google falso (sin cambios desde la ronda 1).
2. **Editar un monto → cambia el devengado y no quedan filas viejas.** ✓ con el Google falso.
3. **Fila sin alias → `alias_sin_cliente`; con el alias cargado, el cliente aparece sin reinterpretar.** ✓
4. **`interpret --all` dos veces → mismas filas, sin duplicar problemas.** ✓, y repetido en una sonda con la fila literal "Cliente Uno (2)" junto a la serie repetida: mismas filas y mismos problemas.
5. **Cotizaciones con filas corridas iguales; MEP de control distinta → `cotizacion_discrepante`.** ✓
6. **Segundos por pestaña en `system_event`, ninguna por encima de 10 s.** ✓ por el test. En datos reales, interpretando en memoria (sin escribir) la última lectura de cada pestaña: 72, 860, 72 y 1057 hechos, iguales a los que tiene la base principal; los tiempos de implement son de 4 a 53 ms.
7. **Ningún log ni `details` contiene montos.** ✓ Los `details` nuevos de los arreglos llevan bloque y celda, nunca el valor.

Otros chequeos sobre la base principal (solo lectura): la `sha256` de la 0009 coincide con la del archivo y la restricción única de `accrual` es la nueva, como dice el post-merge.

## No verificado

- Criterios 1 y 2 contra la planilla de prueba real con el worker: QA no escribe en Sheets. Siguen en el post-merge, como anota el ticket.

## Split-outs sugeridos (fuera del alcance)

- Ninguno nuevo. F1 es un caso más de la clase `[robustez]` que ya está en `plan/improvements.md` (QA T-010 r1).
