# QA T-020 — Ronda 1

**Verdict: PASS**
**Branch:** arielvinas/t-020-paridad-cashflow @ 4d7a661
**Gates:** ruff check ✓ · ruff format --check ✓ · pytest ✓ (353 pasan, ninguno salteado, contra una base de prueba propia `qa_t020_r1_test`) · uv build ✓
**Criteria:** 4/4 verificados
**Mutation:** 13 mutantes sobre la migración 0016, corriendo solo los tests nuevos de paridad: 10 mueren; los 3 que sobreviven no cambian un criterio (ver F1 y F2). Revertir el filtro `recalculada`, la tolerancia, el `>`, el `coalesce`, el signo, el `abs`, el mes del join, las columnas de cobertura o el `GRANT` al lector → suite roja ✓.

No hay interfaz en este ticket (la pantalla es T-021): no corresponde navegador.

## Criterios

1. **Diferencia 0, diferencia correcta en la unidad de la fila y marca de fuera de tolerancia: cumple.** Además de los tests, sobre una copia de la base de desarrollo con la 0016 aplicada (borrada al terminar):
   - 507 celdas comparadas; `diferencia` = round(Resumen vacío→0 − recalculado, 2) y `fuera_de_tolerancia` = |diferencia| > tolerancia en las 507, sin excepción.
   - Borde en dólares, forzando el Resumen dentro de una transacción revertida: diferencia 1,00 → dentro; 1,01 → fuera. En pesos: −1.000,00 → dentro; −1.000,01 → fuera.
   - Ruido de coma flotante (0,0000001) da diferencia 0,00.
   - 30 celdas del Resumen vacías: `valor_resumen` nulo y diferencia igual a −recalculado en las 30.
   - Los puntos ciegos que anota implement (filas con `sign` −1, valores del Resumen con decimales) sí están en los datos reales: 156 celdas de filas con signo −1 y 409 con decimales, todas consistentes.
   - Sin claves duplicadas (bloque, fila, mes); ninguna celda sin planilla, pestaña, celda o lectura.
2. **Solo se comparan las `recalculada`; el resto se cuenta por mes: cumple.** En la copia: 0 celdas de periodo proyectado en la paridad, 0 celdas no `recalculada`; la cobertura tiene 53 meses (507 recalculadas, 882 sin regla, 42 de parámetro = 1.431, el total de `mcp.caja_mensual`), la suma por mes coincide con `count(*)` de cada mes, y los meses proyectados tienen 0 recalculadas y 3 de parámetro.
3. **`mcp_reader` lee las dos vistas; `mcp_writer` no: cumple.** Conectado con cada rol a la copia: el lector lee 507 y 53 filas; el escritor recibe «permission denied for schema mcp» en las dos. En el catálogo, el único `SELECT` concedido fuera del dueño es a `mcp_reader`. Todas las columnas de las dos vistas tienen `COMMENT ON` en castellano, y el de la vista y el de `tolerancia` dicen que es propuesta y que la ratifican Emi y Ro.
4. **Tests solo con datos sintéticos: cumple.** El Resumen de los tests (`PARITY_ROWS`) es inventado; los fixtures no leen nada real.

Tiempos en la copia: cada vista responde en unos 0,25 s.

## Findings

### F1 [minor] Una fila de la configuración que no está en el Resumen queda fuera de la paridad sin aviso, y la cobertura la cuenta como comparada
- **Repro:** en la copia, dentro de una transacción revertida, agregar a `cashflow_row` una fila con rubros que no existe en la pestaña («filas sin ubicar» de la proyección). `mcp.caja_mensual` le da 39 celdas `recalculada`; `mcp.paridad_cashflow` no muestra ninguna (el `JOIN` con `cashflow_sheet_cell` es interno); `mcp.cobertura_cashflow` suma 546 recalculadas contra 507 filas de paridad.
- **Expected:** que el comentario de la cobertura («las recalculada son las que compara mcp.paridad_cashflow») sea cierto, o que esas celdas aparezcan en la paridad con `valor_resumen` nulo y sin celda. **Actual:** se pierden en silencio. Hoy no pasa con los datos reales (0 filas sin ubicar; 507 = 507), y la proyección ya registra `filas_sin_ubicar` en el evento, por eso es minor.
- **Sugerencia simple:** ajustar el comentario de `mcp.cobertura_cashflow` («las recalculada con celda en el Resumen son las que compara…»), o un `LEFT JOIN`. Decide implement.

### F2 [nit] Tres mutantes sobreviven a los tests nuevos
- Sin el `round(…, 2)` de `diferencia`: los valores sintéticos son enteros. Lo verifiqué a mano en la copia (ruido de 1e-7 da 0,00), así que el comportamiento está bien; falta un valor con decimales en `PARITY_ROWS`.
- Sin `s.source_tab_id = c.pestaña_id` en el join: hay una sola pestaña Resumen y una sola lectura (también en la base real), así que es equivalente hoy.
- Con `GRANT SELECT … TO mcp_reader, mcp_writer`: el escritor sigue sin poder leer porque no tiene `USAGE` sobre el esquema `mcp`. La propiedad que pide el criterio se mantiene; el test prueba el efecto y no la línea del `GRANT` («ninguno a `mcp_writer`»). Un `has_table_privilege('mcp_writer', …)` = falso lo cubriría. Mismo patrón que los tests de T-019.

## Re-verificación de la ronda anterior

Primera ronda: no hay.

## No verificado

- Nada de los criterios. La tolerancia propuesta (1.000 pesos / 1 dólar) es pregunta abierta para Emi y Ro, fuera de alcance; con ella 488 de 507 celdas reales quedan fuera, como anota el ticket.

## Split-outs sugeridos (fuera del alcance)

- [docs-mcp] El glosario del servidor MCP (`app/craftech_os/mcp/server.py`, entrada **Paridad**) dice que «una diferencia distinta de 0 es un error de lectura» y lista solo las paridades de Pagos y fundings. En la paridad del cashflow una diferencia no es un error de lectura (puede ser una regla de fila sin ratificar o el mes en curso). Conviene sumar `mcp.paridad_cashflow`, `mcp.cobertura_cashflow` y las vistas de caja de T-019 al glosario con su propia lectura de la diferencia.
