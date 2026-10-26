# QA T-020 — Ronda 2

**Verdict: PASS**
**Branch:** arielvinas/t-020-paridad-cashflow @ 5ecb48e
**Gates:** ruff check ✓ · ruff format --check ✓ · pytest ✓ (353 pasan, ninguno salteado, contra una base de prueba propia `qa_t020_r2_test`, borrada al terminar) · uv build ✓
**Criteria:** 4/4 verificados
**Mutation:** revertí el cambio central de esta ronda (`LEFT JOIN` → `JOIN`) → suite roja ✓. Arnés de 11 mutantes sobre la migración 0016, corriendo solo los tres tests de paridad: mueren los 11 (ver abajo).

No hay interfaz en este ticket (la pantalla es T-021): no corresponde navegador.

## Qué cambió desde la ronda 1

Dos commits de CodeRabbit (`0bb705f`, `5ecb48e`):
- `mcp.paridad_cashflow` cruza con `cashflow_sheet_cell` por `LEFT JOIN` y suma la columna `en_resumen` (`s.id IS NOT NULL`). Comentarios de la vista, `valor_resumen`, `diferencia`, `celda` y `en_resumen` actualizados.
- Tests: el Resumen sintético tiene un valor con decimales (`498.996`), un caso de fila configurada que no está en el Resumen (`Saldo Final`: `valor_resumen` nulo, diferencia −400, `en_resumen` falso), `bool_and(en_resumen)` verdadero en una fila que sí está (incluida su celda vacía del mes en curso), y la comparación de conjuntos pasó de `<=` a `==` contra las `recalculada` de `mcp.caja_mensual`.

## Criterios

1. **Diferencia 0, diferencia correcta en la unidad de la fila y marca de fuera de tolerancia: cumple.** Sobre una copia de la base de desarrollo con la 0016 aplicada por `craftech-os migrate` (borrada al terminar): 507 celdas comparadas, las 507 con `en_resumen` verdadero; `diferencia` = round(Resumen vacío→0 − recalculado, 2) y `fuera_de_tolerancia` = |diferencia| > tolerancia en las 507 sin excepción; 19 con diferencia 0, 30 con el Resumen vacío, 488 fuera de tolerancia. Mismos números que en la ronda 1 y que la prueba de humo del ticket: el `LEFT JOIN` no cambia nada con los datos reales. El test nuevo cubre el redondeo antes de la tolerancia (−1,004 → −1,00 → dentro).
2. **Solo se comparan las `recalculada`; el resto se cuenta por mes: cumple.** En la copia: 0 celdas proyectadas y 0 no `recalculada` en la paridad; sin claves (bloque, fila, mes) repetidas; `sum(recalculadas)` de `mcp.cobertura_cashflow` = 507 = filas de la paridad = `recalculada` de `mcp.caja_mensual`.
   - **Foco de esta ronda (F1 de la ronda 1):** dentro de una transacción revertida, agregué a `cashflow_row` una fila con rubros que no existe en la pestaña. `mcp.caja_mensual` le da 39 celdas `recalculada`; ahora `mcp.paridad_cashflow` muestra las 39 con `en_resumen` falso, `valor_resumen`/`celda`/`lectura_id` nulos, diferencia = −recalculado y la tolerancia en pesos bien aplicada. Totales: caja 546 = cobertura 546 = paridad 546. El comentario de la cobertura («las recalculada son las que compara mcp.paridad_cashflow») ahora es cierto.
   - Una celda del Resumen presente pero vacía sigue con `en_resumen` verdadero (se distingue de una fila ausente): 30 en la copia, y lo cubre el `bool_and` del test.
3. **`mcp_reader` puede leer las dos vistas; `mcp_writer` no: cumple.** Conectado con cada rol a la copia: el lector lee 507 y 53 filas; el escritor recibe «permission denied for schema mcp» en las dos. `has_table_privilege`: lector verdadero, escritor falso en las dos; el único `SELECT` concedido fuera del dueño es a `mcp_reader`. Todas las columnas de la paridad (incluida `en_resumen`) tienen `COMMENT ON` en castellano; la vista y `tolerancia` dicen que la tolerancia es propuesta y sigue pendiente de ratificación por Emi y Ro.
4. **Tests solo con datos sintéticos: cumple.** `PARITY_ROWS` y los fixtures siguen siendo inventados.

Tiempo de la paridad en la copia: 0,32 s.

## Mutación

Arnés en el scratchpad (`/tmp/qa-t020-r2/mutants.py`, falla si un patrón no está en el archivo y sale con error si un mutante sobrevive), solo con los tres tests de paridad:

| Mutante | Resultado |
|---|---|
| `LEFT JOIN` → `JOIN` (revierte el cambio de esta ronda) | muere |
| `en_resumen` desde `s.value` en lugar de `s.id` | muere |
| `en_resumen` constante verdadera | muere |
| sin `round` en la marca de tolerancia | muere (nuevo: antes no había decimales) |
| sin `round` en `diferencia` | muere (sobrevivía en la ronda 1) |
| sin `coalesce` | muere |
| sin el filtro `recalculada` | muere |
| tolerancia en pesos de 1 | muere |
| `>=` en lugar de `>` | muere |
| sin el mes en el cruce | muere |
| `GRANT` sin la vista de paridad | muere |

Atribución: los tres primeros y los dos del `round` los matan aserciones agregadas en esta ronda (`Saldo Final` con `en_resumen` falso, el `bool_and`, el `==` de conjuntos y el valor `498.996`).

## Findings

### F1 [nit] El comentario de `en_resumen` no nombra todas las columnas que quedan nulas
- **Repro:** en la copia, con la fila sin ubicar del criterio 2: además de `valor_resumen`, `celda` y `lectura_id`, también son nulas `planilla`, `pestaña` y `pestaña_id` (vienen de `mcp.caja_mensual`, que no ubica la fila).
- **Expected:** que el comentario de `en_resumen` («entonces valor_resumen, celda y lectura_id son nulos») y el de `planilla` («CASH FLOW MENSUAL») lo digan. **Actual:** lo omiten. No cambia ningún valor ni criterio; con los datos reales no hay filas sin ubicar.

## Re-verificación de la ronda anterior

- F1 (r1) [minor] fila de la configuración fuera del Resumen se perdía en silencio: ✓ resuelto con el `LEFT JOIN` y `en_resumen`, verificado sobre la copia (546 = 546 = 546) y cubierto por tests que mueren si se revierte.
- F2 (r1) [nit] mutantes sobrevivientes: ✓ el del `round` ahora muere. Siguen como en la ronda 1, sin cambio en los tests de esa parte: el cruce sin `s.source_tab_id = c.pestaña_id` (equivalente hoy, hay una sola pestaña) y `GRANT … TO mcp_reader, mcp_writer` (lo probé de nuevo: el test de permisos sigue verde porque el escritor no tiene `USAGE` sobre `mcp`; la propiedad del criterio se mantiene).

## No verificado

- Nada de los criterios. La tolerancia propuesta sigue siendo pregunta abierta para Emi y Ro (fuera de alcance).

## Split-outs sugeridos (fuera del alcance)

- Ninguno nuevo. El de la ronda 1 (glosario del servidor MCP sin las vistas de caja ni de paridad del cashflow) sigue vigente.
