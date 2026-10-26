# QA T-019, ronda 2

**Veredicto: PASS.** Los dos hallazgos major de la ronda 1 están resueltos, y los dos cambios centrales los atrapa la suite si se revierten. Quedan tres minor:
- una pregunta de producto sobre sueldos que son el único pago de su grupo;
- dos huecos de test en partes secundarias del arreglo, que verifiqué a mano sobre una copia de la base.

**Rama:** `arielvinas/t-019-cashflow-mensual` @ `112a5c9`.

## Gates

- `uv run ruff check`: ok.
- `uv run ruff format --check`: ok.
- `uv run pytest -q`: 350 pasan contra una base de prueba propia (`qa_t019_r2_test`), ninguno salteado.
- `uv build`: ok.

## Criterios (8/8)

1. Migración 0015 con tablas, vistas, vistas MCP y `COMMENT ON`: **cumple**. Sobre la copia de la base, ninguna columna de las siete tablas y vistas queda sin comentario.
2. Proyección del Resumen aunque sea DERIVADA, reemplazo entero, `interpret`: **cumple**. En la copia, `interpret --all` ubicó 27 filas y 1.431 celdas, en unos 10 s para las 8 pestañas.
3. Meses reales recalculados sin valores de la planilla, meses proyectados y filas sin regla sin valor y con motivo, filas de parámetro: **cumple**. En la copia:
   - 494 celdas `recalculada` reales y 13 en curso, todas con valor;
   - 882 `sin_regla` y 42 `parametro`, todas sin valor.
4. Mes en curso marcado y meses reales hasta el último mes cerrado con movimientos: **cumple**. En la copia hay 38 meses reales (ago-23 a sep-26), octubre en curso y 14 meses proyectados. Si se borran los movimientos de septiembre (en una transacción que después se deshizo):
   - septiembre pasa a `proyectado` con su motivo;
   - caja hoy toma agosto y su valor es igual al Saldo Final de agosto;
   - salida mensual es igual al promedio de junio a agosto.
5. Indicadores de Craftech Inc. en dólares, con fórmula y marca de propuesto: **cumple**. En la copia, caja hoy, salida mensual y cobertura tienen valor. Salida mensual es igual al promedio de julio a septiembre, y los dos cierres de marzo-27 son nulos, como está documentado.
6. `mcp_reader` lee las tres vistas y `mcp_writer` no: **cumple**. En la copia, `GRANT SELECT` es solo para `mcp_reader`.
7. Sueldos solo como totales en `mcp.movimientos_de_caja` y `mcp.caja_mensual`: **cumple** con el agrupamiento que escribe el criterio (mes, banco, moneda, tipo de movimiento, rubro y agrupador). En la copia:
   - ninguna fila de sueldos tiene detalle, subdetalle, equipo, celda ni tipo de cambio;
   - la suma de `monto` y `monto_usd` por mes y rubro de la vista es igual a la de `cash_movement` (0 diferencias): no se pierde plata;
   - la vista tiene 17.072 filas, contra 21.534 movimientos.

   Ver el hallazgo 1 sobre los grupos que tienen un solo pago.
8. Datos sintéticos en los tests y eventos con cantidades: **cumple**.

## Mutación

Usé un arnés descartable que reescribe la migración, corre `test_cashflow.py`, `test_mcp.py` y `test_db.py`, y la restaura. El arnés falla si no encuentra el texto a mutar.

| Mutación | Resultado |
|---|---|
| Mes real por calendario (el cambio central del hallazgo 2 de la ronda 1) | rojo ✓ |
| Caja hoy toma el mes calendario anterior | rojo ✓ |
| El último mes real incluye el mes en curso | rojo ✓ |
| Sueldos sin agrupar, uno por pago (el cambio central del hallazgo 1 de la ronda 1) | rojo ✓ |
| Los totales de sueldos exponen la celda | rojo ✓ |
| Se sacan los sueldos de la vista | rojo ✓ |
| Salida mensual con ventana por calendario | **verde** (hallazgo 2) |
| Salida mensual con los últimos 4 meses reales en vez de 3 | **verde** (hallazgo 2) |
| Sueldos identificados solo por rubro, sin mirar el tipo de movimiento | **verde** (hallazgo 3) |

Los dos cambios centrales hacen fallar la suite. Los tres sobrevivientes están en partes secundarias, y verifiqué su comportamiento a mano sobre la copia.

## Hallazgos

### 1. [minor] Un tercio de los «totales» de sueldos son un solo pago

- **Repro:** en la copia, agrupé `cash_movement` de sueldos con las mismas claves que la vista. De 435 filas de sueldos en `mcp.movimientos_de_caja`, 123 salen de un único pago. Dentro del rubro «01. Sueldos» y sin contar las cargas sociales (CCSS), 35 lo son. Por ejemplo:
  - agrupador «Sueldos» en Mercury, en 9 meses;
  - «Comisiones» en Mercury, en 7 meses;
  - «Bono» en Mercury, en 4 meses.
- **Esperado según el criterio escrito:** un total por mes, banco, moneda, tipo de movimiento, rubro y agrupador. Es lo que hace la vista.
- **Lo que queda abierto:** en esos grupos, el «total» es el monto de una sola persona en ese mes (una comisión o un bono, por ejemplo). No lleva nombre, detalle ni celda. El caso de prueba de la sección Post-merge, «una fila por agrupador y moneda, nunca una por pago», es falso con los datos reales.
- **Por qué es minor y no major:** el criterio define el agrupamiento con todas sus claves, y el punto 4 del alcance ya aceptaba montos de sueldos sin nombre. Si un monto sin nombre cuenta como «sueldo individual» es una pregunta para Ariel. Sugerencia: aceptarlo, porque la vista solo la lee `mcp_reader` y no hay forma de saber de quién es el pago. Si no se acepta, hay que agrupar más grueso (mes, moneda y rubro) o esconder los grupos de un solo pago.

### 2. [minor] El arreglo de salida mensual no tiene test que lo distinga

- **Repro:** reemplacé «los últimos tres meses reales» por la ventana de calendario de la ronda 1, o por los últimos cuatro meses. La suite queda verde.
- **Por qué:** el test nuevo, `test_a_closed_month_without_movements_is_not_real_yet`, deja solo dos meses reales. Con la ventana vieja también da nulo, por la guarda de tres meses.
- **Comportamiento real:** es correcto. En la copia, con septiembre borrado, salida mensual sale igual al promedio de junio a agosto. Con la ventana de calendario habría salido nula durante los primeros días de cada mes.
- **Falta:** un caso con al menos tres meses reales más un mes cerrado sin movimientos.

### 3. [minor] No hay test de sueldos marcados solo por el tipo de movimiento

- **Repro:** si la vista mira solo el rubro y deja de mirar `movement_type = 'Sueldos'`, la suite queda verde.
- **Datos reales:** en la copia hay 85 movimientos de tipo Sueldos con otro rubro, repartidos en 7 rubros (Impuestos, Capacitación, Comercial y otros). Con esa mutación saldrían uno por uno, con su celda y su tipo de cambio.
- **Hoy:** el código los agrupa bien. Lo verifiqué en la copia: 0 filas de sueldos con celda o tipo de cambio.
- **Falta:** sembrar en `test_no_salary_of_a_person_reaches_the_cash_views` un movimiento de tipo Sueldos con otro rubro.

## Re-verificación de la ronda anterior

- Hallazgo 1 de la ronda 1 (major, sueldos por pago en `mcp.movimientos_de_caja`): ✓ resuelto. Los sueldos se agrupan como dice el criterio y la mutación que los desagrupa da rojo. El residuo es el hallazgo 1 de esta ronda.
- Hallazgo 2 de la ronda 1 (major, mes real por calendario): ✓ resuelto. Se verificó con la mutación y sobre la copia, borrando septiembre. Hay un hueco de test, en el hallazgo 2 de esta ronda.
- Hallazgo 3 de la ronda 1 (minor, una lectura rota vacía el cashflow): registrado como split-out en `plan/improvements.md`. ✓
- Hallazgo 4 de la ronda 1 (nit, unidad del bloque Argentina): ✓ resuelto. El comentario de `mcp.caja_mensual.unidad` aclara que los montos no hay que multiplicarlos por mil.
- Hallazgo 5 de la ronda 1 (nit, guarda de tres meses): ✓. Ahora actúa cuando hay menos de tres meses reales.

## Observaciones que no son hallazgos

- **Ajustes:** el último mes real se calcula sobre todos los movimientos, incluidos los ajustes (CLIENTES y AFIP). En la copia, borré los movimientos de septiembre salvo los 5 de ajuste. Septiembre quedó `real`, con Sueldos y Gastos en 0, y la cobertura se infló. No lo cuento como hallazgo por dos razones:
  - los ajustes vienen de la misma pestaña Consolidado y en la misma lectura;
  - en la historia no hay ningún mes con solo ajustes.

  Es la misma limitación de fondo: «mes completo» no se puede saber desde los datos.
- **Rendimiento:** en la copia, `mcp.caja_mensual` tarda 0,41 s, `mcp.indicadores_de_caja` 1,4 s y `mcp.movimientos_de_caja` 5 ms.

## No verificado

- No hay pantalla en este ticket (la `/caja` es T-021), así que no hubo prueba en navegador.
- No probé las vistas desde Claude Desktop con el servidor MCP real.

## Split-outs sugeridos

- Ninguno nuevo. La pregunta del hallazgo 1 es para Ariel; los hallazgos 2 y 3 son tests que se pueden sumar dentro del ticket.

Borré las dos bases que usé (`qa_t019_r2_test` y la copia `qa_t019_r2_copy_test`) y también el arnés de mutación.
