# QA T-019, ronda 1

**Veredicto: FAIL.** Hay dos hallazgos major. El primero: un criterio de aceptación no se cumple, porque la vista MCP de movimientos expone el monto de cada pago de sueldo. El segundo: el «mes real» se define por calendario y no como «hasta el último mes completo con movimientos». Lo demás anda: las reglas, el origen de cada celda, los indicadores con fórmula, los permisos MCP y la mutación.

**Rama:** `arielvinas/t-019-cashflow-mensual` @ `6159367`.

## Gates

- `uv run ruff check`: ok.
- `uv run ruff format --check`: ok.
- `uv run pytest -q`: 349 pasan, ninguno salteado.
- `uv build`: ok.

## Criterios (7/8)

1. Migración 0015 con tablas, vistas, vistas MCP y `COMMENT ON`: **cumple**. Se aplicó sobre una copia de la base de desarrollo y todas las tablas, vistas y columnas tienen comentario.
2. Proyección del Resumen aunque la pestaña sea DERIVADA, reemplazo entero, otras pestañas intactas, `interpret`: **cumple**. Lo verifiqué con tests y con la copia: `interpret --all` ubicó 27 filas y 1.431 celdas en unos 9 s.
3. Mes real recalculado sin valor de la planilla, proyectados y filas sin regla sin valor con motivo, filas de parámetro: **cumple**. Si se muta la vista para mostrar el valor del Resumen cuando falta el calculado, la suite da 2 rojos. En la copia, ninguna celda `recalculada` toma su valor del Resumen.
4. Mes en curso recalculado y distinguido como `en_curso`: **cumple** en lo que dice el criterio. Sobre el borde entre real y en curso, ver el hallazgo 2.
5. Indicadores solo de Craftech Inc., en dólares, con fórmula y marca de propuesto: **cumple** sobre los datos sintéticos. En la copia, caja hoy, salida mensual y cobertura tienen valor, y los dos cierres de marzo-27 quedan nulos, como está documentado.
6. `mcp_reader` lee las tres vistas y `mcp_writer` no: **cumple**.
7. Ningún sueldo individual se filtra por `mcp.movimientos_de_caja` ni por `mcp.caja_mensual`, solo totales por fila y mes: **no cumple**. Ver el hallazgo 1.
8. Los tests usan solo datos sintéticos y los eventos llevan cantidades: **cumple**.

## Mutación

Revertí a mano el cambio central en cuatro variantes. Todas pusieron la suite en rojo, y después restauré con `git checkout`:

| Mutación | Resultado en `test_cashflow.py` |
|---|---|
| El importador no llama a `cashflow.project` | 1 rojo con `-x` |
| Ni el importador ni `interpret` llaman a `cashflow.project` | 10 rojos |
| La vista muestra el valor del Resumen cuando no hay calculado (`coalesce(..., s.value)`) | 2 rojos |
| El mes en curso cuenta como real (`<=` en lugar de `<`) | 1 rojo |

## Hallazgos

### 1. [major] `mcp.movimientos_de_caja` expone el monto de cada pago de sueldo

- **Qué dice el ticket:** el Contexto dice «Sueldos solo como total también en las vistas MCP». El criterio 7 pide que ningún sueldo individual se filtre por `mcp.movimientos_de_caja` y que haya solo totales por fila y mes.
- **Qué hace el código:** la vista (`app/migrations/0015_cashflow_cell.sql:220`) publica `monto` y `monto_usd` de cada fila de `cash_movement`, también en las de «01. Sueldos». Lo único que oculta es detalle, subdetalle y equipo, que ya vienen nulos desde T-018.
- **El test lo da por bueno:** `test_no_salary_of_a_person_reaches_the_cash_views` lo acepta explícitamente, con el comentario «Per person amounts stay in the movements».
- **Repro:** sobre la copia de la base de desarrollo, `SELECT mes, banco, monto FROM mcp.movimientos_de_caja WHERE rubro = '01. Sueldos'` devuelve una fila por pago, en promedio 63,3 por mes. Ninguna lleva nombre, pero cada monto es el sueldo de una persona en un mes y un banco. Con equipos chicos o sueldos distintivos, se reidentifica cruzándolo con otras fuentes que lee Claude Desktop.
- **Esperado:** en las filas de sueldos, la vista MCP da solo el total por mes, banco y moneda (o por mes y fila), y no el pago individual.
- **Real:** da un monto por pago.
- **Nota:** el alcance (punto 4) solo pide vaciar Detalle, Subdetalle y Equipo, así que el ticket se contradice a sí mismo. El criterio y el Contexto son más estrictos y son los que valen para QA. Si Ariel decide que el monto sin nombre es aceptable, hay que corregir el criterio y no el código. Es una pregunta para Ariel antes de la ronda 2.

### 2. [major] El mes real se cuenta por calendario y no hasta el último mes completo con movimientos

- **Qué dicen el ticket y el ADR:** el Contexto del ticket y el punto 5 del ADR-003 dicen «Mes real: hasta el último mes completo con movimientos».
- **Qué hace el código:** la vista (`app/migrations/0015_cashflow_cell.sql:95`) marca como `real` todo mes anterior al mes de `current_date`. El indicador caja hoy toma siempre el mes calendario anterior (`:133`), y salida mensual promedia los tres meses calendario anteriores.
- **Repro:** con un test descartable armé los mismos movimientos sintéticos de `test_cashflow.py`, pero sin ninguno en el último mes cerrado (como pasa a principio de mes, antes de que Emi cargue el Consolidado). Resultado:
  - ese mes sale `real`/`recalculada` con Sueldos en 0;
  - salida mensual baja a 316,67 (promediando un mes en cero), cuando el promedio de los meses con datos es 475;
  - cobertura sube a 1,74 meses, contra 1,16 si se toma el último mes con movimientos.
- **Esperado:** el mes sin movimientos todavía no es real cerrado. Los indicadores se calculan sobre los meses reales que sí tienen movimientos.
- **Real:** la caja muestra un mes cerrado lleno de ceros, la salida mensual queda subestimada en un tercio y la cobertura inflada, sin ninguna marca. Pasa todos los meses, desde el día 1 hasta que se carga el Consolidado.
- **Evidencia en datos reales:** hoy no se nota, porque el último mes con movimientos (2026-09) coincide con el mes calendario anterior. El 1-nov-2026 octubre pasaría a «real» aunque el Consolidado no lo tenga completo.

### 3. [minor] Una lectura del Resumen con forma rota vacía el cashflow sin abrir un problema

- **Repro:** con un test descartable, una segunda lectura del Resumen sin filas reconocibles (una sola celda de texto) deja:
  - `cashflow_sheet_cell` en 0 filas (antes 35);
  - `cashflow_cell` en 0 filas;
  - `issue` en 0.
  
  El único rastro es el evento `cashflow_projected` con `filas: 0` y `filas_sin_ubicar: 27`.
- **Esperado:** un problema visible (por ejemplo, un `issue` de pestaña con forma inesperada), o conservar la proyección anterior cuando no se ubica ninguna fila.
- **Real:** el cashflow y los indicadores desaparecen en silencio hasta la próxima lectura buena.
- No lo pide ningún criterio, así que va como minor con split-out.

### 4. [nit] Unidad del bloque Argentina

- **El cambio:** `config/cashflow_rows.yaml` pasa la unidad del bloque «Argentina en miles de pesos» de `miles_ars` a `ars`, y el comentario de `mcp.caja_mensual.unidad` dice «ars (pesos)». El punto 2 del alcance habla de «miles de pesos».
- **Lo medido:** en la copia, la mediana del cociente calculado ÷ planilla en meses reales es:
  - 0,97 en Gastos de Argentina;
  - 1,01 en Pagos Recibidos S.A.
  
  Es decir, los valores calculados están en la misma escala que los del Resumen. No hay un error de valor por un factor de mil.
- **Qué falta:** solo hace falta aclarar en el comentario de la columna que el bloque se llama «en miles» pero los montos están en la misma escala que la planilla. Así un lector de Claude Desktop no multiplica por mil.

### 5. [nit] Guarda casi muerta en salida mensual

`count(value) = 3` en el promedio de salida mensual no se dispara con meses reales, porque las filas con regla nunca dan nulo (`coalesce(..., 0)`). Solo protege el caso de que haya menos de tres meses en el Resumen. No molesta.

## Observaciones que no son hallazgos

- **Rendimiento:** las vistas MCP tardan 0,41 s (`caja_mensual`), 1,4 s (`indicadores_de_caja`) y 1 ms (`movimientos_de_caja`) sobre la copia.
- **Unicidad:** no hay celdas duplicadas por bloque, fila y mes.
- **Mes en curso:** en la copia, el saldo final de octubre es igual al de septiembre en los dos bloques con saldo, porque todavía no hay movimientos de octubre. Es coherente con «se recalcula con lo que hay».
- **Saldo de Argentina:** su cociente contra la planilla es de alrededor de 15. Es consistente con el saldo de apertura y las inversiones que faltan, ya anotados en Post-merge.

## No verificado

- No hay pantalla en este ticket (la `/caja` es T-021), así que no hubo prueba en navegador.
- No probé las vistas desde Claude Desktop con el servidor MCP real. Solo las probé con conexiones `mcp_reader` y `mcp_writer` en los tests.
- No probé lecturas concurrentes del Resumen y del Consolidado en el worker.

## Split-outs sugeridos

- Problema visible, o conservar la proyección anterior, cuando una lectura del Resumen no ubica ninguna fila (hallazgo 3).
- Comentario de unidad del bloque Argentina, «miles» en el nombre contra pesos en los montos (hallazgo 4). Se puede resolver dentro de la ronda 2 si se toca la migración.

La copia de la base usada (`qa_t019_copy_test`) ya fue borrada. El test descartable se borró antes del commit.
