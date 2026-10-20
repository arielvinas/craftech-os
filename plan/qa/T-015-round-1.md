# QA T-015 — Ronda 1

**Verdict: PASS**
**Branch:** arielvinas/t-015-cei-y-paridad-aws @ 2de0fa8
**Gates:** lint (`ruff check`) ✓ · formato (`ruff format --check`) ✓ · tests ✓ (310 passed, 0 skipped, con `TEST_DATABASE_URL` y los usuarios del servidor MCP) · typecheck y build: el proyecto no tiene esos gates
**Criteria:** 9/9 verificados
**Mutation:** 18 mutantes a mano sobre `fundings.py`, `pagos.py`, `interpret/__init__.py` y la migración `0012`. 16 mueren con los tests nuevos de T-015 y 2 sobreviven (F1 y F2, los dos `minor`). El harness está en `evidence/T-015-r1/mutate.py`: arranca con una corrida base en verde y corta con error si falta un archivo o un patrón.

## Cómo se verificó

- **Base local** (`craftech-os-postgres-1`, con la migración `0012` ya aplicada desde la rama): consultas de `mcp.fundings`, `v_issue`, `issue_resolution` y `mcp.paridad_fundings_aws`.
- **Antes y después contra la misma lectura.** Un worktree temporal de `main` y la rama corren `pagos.interpret` y `pagos.interpret_arg` sobre la última lectura de cada pestaña Pagos y Pagos ARG, y se comparan los hechos (script en `evidence/T-015-r1/compare.py`). En la revisión de CodeRabbit el script se corrigió para que también lea Pagos ARG con `pagos.interpret_arg` (antes leía solo Pagos) y no escriba dentro del repo; vuelto a correr el 20-oct-2026, mismo resultado: los hechos de Pagos ARG son idénticos y los de Pagos difieren solo en la fila CEI y en `funding_total`, que es nuevo.
- **Idempotencia sobre datos reales.** Tomé un hash de `mcp.fundings`, de `v_issue` (id, tipo, clave, estado, detalle) y de `mcp.paridad_fundings_aws`. Después corrí `uv run craftech-os interpret --all` dos veces y los tres hashes quedaron iguales.
- **Navegador:** no aplica. El ticket no toca pantallas (las pantallas nuevas están fuera de alcance) y `test_web.py` pasa.

## Criterios

1. ✓ `mcp.fundings` trae doce hitos de origen pagos con programa CEI. En Craftech son las celdas E96, H96, K96, N96, Q96, T96 y X96; en SleakOps, E102, H102, K102, Q102 y T102. Cada uno tiene su celda y su mes.
2. ✓ Los siete `fila_sin_interpretar` (E96, H96, K96, N96, E102, H102 y K102) están en `resuelto`, con la resolución de autor "T-015 (decisión de Ariel del 20-oct-2026)". Con los datos actuales no queda abierto ningún problema de la fila CEI. El único `General` abierto es `50:General:fila 82`, de la pestaña VENTAS, que está fuera de alcance y la migración no toca porque filtra por la pestaña Pagos.
3. ✓ Comparé `main` contra la rama sobre la misma lectura. Los hitos de Pagos que no son CEI son idénticos campo por campo: 91 en Craftech y 10 en SleakOps. También son idénticos `invoice`, `client_churn` y `payment_total` en Pagos, y todos los hechos de Pagos ARG, que comparte `_interpret`. La única diferencia en problemas son los siete `fila_sin_interpretar` de la fila CEI, que la rama ya no abre.
4. ✓ `test_the_cei_row_of_general_gives_milestones_up_to_september_2026`: el monto de octubre de 2026 (F4) abre un problema con su celda y el motivo, y no da hito. El mutante que cambia `>` por `>=` en `CEI_LAST_MONTH` muere.
5. ✓ El mismo test cubre los dos casos: la copia con `IMPORTRANGE` en la fila CEI da hito (D4) y la copia `'Otra planilla'!` en una fila de cliente no da nada.
6. ✓ El test reinterpreta y compara el estado. Además, sobre la base real, dos `interpret --all` seguidos dejan los mismos hashes.
7. ✓ La vista tiene 72 filas, 36 meses por planilla, sin total nulo. Septiembre de 2026 en Craftech da 0 (en SleakOps también). Hay 17 meses con diferencia distinta de 0, los mismos que la tabla de `## Implementation`, con el signo que anota.
8. ✓ La vista tiene comentario en el esquema `mcp`, y el catálogo lee ese esquema. `mcp_reader` puede leer `mcp.paridad_fundings_aws` y recibe "permission denied" sobre `funding_total`, o sea que el permiso es el mínimo. El glosario tiene **CEI** con "Declaración de Ariel del 20-oct-2026, pendiente de ratificar por Emi y Ro", según `test_mcp.py`.
9. ✓ El diff no llama a ninguna API de escritura de Google. Crucé las líneas agregadas contra los 192 textos de alias de la base local y el único que coincide es "general", que es la clave de la fila y no un cliente. Los tests usan montos inventados, y el ticket cita celdas y cantidades, nunca montos.

## Adversarial

- **`payment_total` y la clave `falta:`.** Ahora la clave se normaliza. Como `total_key` ya venía normalizado ("total pagos usa" y "total ingresos"), ni la clave estable del problema ni `row_key` cambian. Lo confirma la comparación de `payment_total`.
- **Filas "TOTAL PAGOS AWS" arriba del encabezado.** En la base real se encuentran: fila 3 en Craftech y fila 2 en SleakOps, 36 meses cada una.
- **Tracker en la paridad.** Unidades: 90 hitos de Craftech y 4 de SleakOps, ninguna unidad fuera de esas dos. 12 hitos de Craftech no tienen ninguna fecha y no se suman, como dice `## Implementation`. Ninguno tiene fecha anterior a marzo de 2026.
- **Copia con error en la fila CEI** (por ejemplo `#REF!`): se ve leyendo el código. Pasa por `unreadable` y abre un problema, así que no se pierde sin aviso.
- **Complejidad:** el diff es chico y sigue el patrón de `payment_total`. No agrega dependencias ni capas.

## Findings

### F1 [minor] La detección de "fila de apertura del bloque General" no tiene test que fije el bloque
- **Repro:** cambiar en `fundings.py` `cei = row is rows[0] and block.split(" (")[0] == "General"` por `cei = row is rows[0]` y correr `test_fundings.py`, `test_mcp.py` y `test_invoices.py`: siguen verdes.
- **Expected:** una fila de apertura de otro bloque de funding (por ejemplo "Funding de AWS confirmados") con programa "CEI" sigue siendo problema. **Actual:** el código lo hace bien, pero ningún test lo fija. Con el mutante, esa fila daría hitos después del corte de la regla R28 sin que nada se ponga rojo. Hoy no pasa en los datos reales.
- **Evidence:** `evidence/T-015-r1/mutate.py`, mutante "any block opener with CEI".

### F2 [minor] La resolución de los siete problemas en la migración `0012` no tiene test
- **Repro:** en la migración, sacar `AND NOT v.details ? 'reason'` o vaciar el `INSERT` y correr los mismos tests: siguen verdes, porque los tests aplican las migraciones sobre una base vacía.
- **Expected/Actual:** es una corrección de datos de una sola vez y en la base local hizo lo correcto: siete resueltos y ninguno de más (ver el criterio 2). Pero el filtro (`stable_key LIKE '%:General:general:%'`, solo la pestaña Pagos, sin `reason`) no tiene red. Alcanza con dejarlo así si se acepta que las migraciones de datos se verifican a mano. La alternativa simple es un test que inserte un problema abierto con y sin `reason` y vuelva a ejecutar el `INSERT`.
- **Evidence:** `evidence/T-015-r1/mutate.py`, mutantes "migration resolves CEI-after-end too" y "migration resolves nothing".

## No verificado

- Los hechos de negocio (CEI se cobraba al cierre de cada trimestre y el último pago fue en septiembre de 2026) son una declaración de Ariel pendiente de Emi y Ro. No se pueden verificar desde el código.
- No verifiqué una por una las causas de cada mes de la tabla de paridad (las celdas R145, S170, etc.): solo que los meses y los signos coinciden. Qué lado manda después del corte sigue siendo la pregunta abierta de T-012.

## Split-outs sugeridos (fuera del alcance)

- Ninguno.
