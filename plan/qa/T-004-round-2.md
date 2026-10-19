# QA T-004 — Ronda 2

**Verdict: PASS**
**Branch:** arielvinas/t-004 @ 08fed12
**Gates:** ruff check ✓ · ruff format --check ✓ (48 archivos) · pytest ✓ (147 passed, con `TEST_DATABASE_URL` apuntando a un PostgreSQL 16 descartable de QA en `127.0.0.1:55435`, borrado al final) · build de imágenes no corrido (el arreglo no toca Dockerfile ni dependencias)
**Criteria:** 6/10 verificados (1, 4, 6, 7, 9, 10). Los criterios 2, 3 y 5 necesitan editar la planilla de prueba de Ariel y el 8 es posterior al merge, igual que en la ronda 1 (ver "No verificado"). En la simulación sobre datos reales, la intención del criterio 2 ahora se cumple: una inserción da un `row_inserted` y nada más.
**Mutation:** con 9 mutantes sobre `compare.py` y `detect.py`, 7 hacen fallar la suite. Sin `normalize` fallan 16 tests, entre ellos `test_a_moved_row_is_one_row_moved_and_nothing_else` y `test_a_moved_row_respelled_still_aligns_by_normalized_key`, así que el criterio 1 se cumple. Cada arreglo de la ronda 1 tiene un test que falla si se revierte: la reescritura de fórmulas, la guarda del hueco, la ambigüedad por contenido, las referencias a otra pestaña y el ordinal en `valor_ilegible`. Sobreviven 2 mutantes (F2 y F3).

## Cómo se probó

- Leí el diff de la ronda de arreglos (`c586745..08fed12`): `compare.py` (`_shift`, `_moved_formula`, ambigüedad por contenido), `detect.py` (ordinal) y los tests nuevos.
- Para los datos reales leí la base local de desarrollo sin escribir en ella: los últimos snapshots de las siete pestañas con esquema, copiados a `/tmp` y borrados al final. No hubo ninguna llamada a Google. Este reporte muestra solo conteos y formas de fórmulas, nunca valores ni claves.
- Escribí un simulador propio, independiente del código del ticket, que reproduce lo que hace Google al insertar o borrar una fila o una columna. Mueve las filas y corre las referencias de la misma pestaña, sin tocar las de otra pestaña ni los textos entre comillas. Al borrar, una referencia simple a la fila borrada pasa a `#REF!` y un rango que la contiene se achica.

## Re-verificación de la ronda anterior

- **F1 (r1, major) ✓ resuelto.** Inserté una fila con clave en el primer lugar de cada bloque, en el medio y después de la última fila de las siete pestañas reales. En todos los casos el resultado fue `{'row_inserted': 1}` y 0 ambiguas; en la ronda 1 daba 405 `formula`. Insertar una columna con encabezado en la grilla da `{'column_inserted': 1}` y nada más. Los casos sintéticos también dan bien: inserción dentro de un rango (`SUM(B4:B5)` → `B4:B6`), debajo del rango, movimiento por arrastre, `LOG10(`, `ATAN2(`, texto entre comillas que parece referencia y referencia a otra hoja sin comillas. Queda un caso de borrado, que va como F1 de esta ronda.
- **F2 (r1, minor) ✓ resuelto.** Lo cubre `test_a_gap_with_a_different_number_of_new_keys_is_ambiguous`, y el mutante `if False:` ahora lo hace fallar.
- **F3 (r1, minor) ✓ resuelto.** Lo cubre `test_an_insert_and_a_delete_in_the_same_block_are_not_ambiguous`, y el mutante "ambigüedad sin mirar el contenido" lo hace fallar. Una observación sin severidad: en los datos reales muchas filas con clave tienen el mismo contenido que otra del mismo bloque (67 de 187 en "Pagos" de Craftech Total y 40 de 93 en "Pagos" de SleakOps Total). Si en la misma lectura se borra una de esas filas y aparece otra con idéntico contenido, se marca `alineacion_ambigua`. Con contenido idéntico no hay forma de distinguir un renombre con movimiento de un alta más una baja, así que marcarlo es lo que pide el ticket ("no se adivina").
- **F4 (r1, minor) ✓ aceptado como documentado.** No hubo cambio de código. El ticket ahora pide, en `## Implementation` y `## Test plan`, insertar la fila con la clave escrita para la prueba en vivo.
- **F5 (r1, nit) ✓ resuelto en parte, el resto quedó registrado.** `valor_ilegible` lleva el ordinal: `cliente a (2):feb` (test nuevo; el mutante muere). Los colores sobre celdas vacías quedaron en `plan/improvements.md`.

## Criterios

1. ✓ Los 22 tests sintéticos de `test_diff_compare.py` del punto 6 pasan, más los 6 nuevos. El mutante sin normalización hace fallar los tests de "fila movida".
2. ⚠ No verificado en la planilla de prueba (es manual de Ariel). En la simulación sobre las siete pestañas reales, una inserción da exactamente un `row_inserted` y ningún `value`. `color` con hexadecimales y `emptied` siguen cubiertos por la suite.
3. ⚠ No verificado en la planilla de prueba. Lo cubre `test_diff_store.py`: el mismo color en 51 celdas da un solo problema, y `last_seen_at` avanza.
4. ✓ Los tests de `v_issue` para ignorado y reabierto siguen en verde. El arreglo no tocó la migración ni `store.py`.
5. ⚠ No verificado en la planilla de prueba. Lo cubren los tests de integración de `register_tabs`, que este arreglo no tocó.
6. ✓ `config/sources.yaml` no cambió en esta ronda. Siete esquemas, sin nombres de clientes.
7. ✓ El test sin esquema sigue en verde: `value` con `cell_ref` y `row_key` nulo.
8. ⚠ Posterior al merge, legítimamente.
9. ✓ Los tests y fixtures nuevos usan "Cliente A–E", "Otra pestaña" y montos inventados. El reporte y los scripts de QA muestran solo conteos.
10. ✓ `uv run pytest` (147) y `ruff check` en limpio.

## Findings

### F1 [minor] Borrar la última fila de un rango sumado deja cambios `formula` falsos
- **Repro sintético:** el total de un bloque tiene `=SUM(B4:B5)` y se borra la fila 5. Google reescribe la fórmula como `=SUM(B4:B4)`.
- **Expected:** solo `row_deleted`.
- **Actual:** `['formula', 'row_deleted']`, con `old_formula =SUM(B4:B5)` y `new_formula =SUM(B4:B4)`.
- **Causa:** `_shift` lleva una fila borrada "al lugar de la siguiente sobreviviente". Eso está bien para el inicio de un rango, pero el final de un rango que termina en la fila borrada se achica a la fila anterior.
- **Alcance real:** borré de a una todas las filas con clave única que no abren bloque en las siete pestañas, unas 500. Solo una dio falsos: la fila 12 de "Pagos" de SleakOps Total, con 23 `formula` del tipo `=SUM(Q11:Q12)` → `=SUM(Q11:Q11)`, por debajo de la alarma de 200 del ADR. El mismo efecto se suma a otras dos situaciones:
  - Borrar una de dos filas con la misma clave da 38 y 77 `formula` en "Pagos" de Craftech Total. Esa corrida además levanta `alineacion_ambigua`, como pide el ticket.
  - Borrar una fila que abre un bloque ("Total Ingresos" de "Pagos ARG" de Craftech Total) da hasta 720. Ese ya es un cambio de estructura.
- **Por qué minor:** el caso es acotado, los cambios falsos quedan visibles y revisables, no se pierden datos y no afecta a ningún criterio. Las referencias simples a la fila borrada pasan a `#REF!` y se reportan como `formula`, lo cual es correcto: la fórmula cambió de verdad.
- **Sugerencia (no la apliqué):** distinguir el extremo final de un rango y llevarlo a la sobreviviente anterior, con un test de borrado de la última fila del rango.

### F2 [minor] El corrimiento de columnas en fórmulas no tiene test
- **Repro:** el mutante que reemplaza `c = move_column(column_index(letters))` por `c = column_index(letters)` en `_moved_formula` sobrevive a toda la suite.
- **Por qué importa:** con ese mutante, insertar una columna con encabezado en la grilla de las pestañas reales da entre 194 y 1091 `formula` falsos por pestaña, y aun así los 147 tests pasan. Hoy el código es correcto (sin el mutante da solo `column_inserted`), pero una regresión pasaría sin que nadie la note.
- **Expected:** un test con una columna insertada a la izquierda de celdas con fórmula, por ejemplo `=C5` que pasa a `=D5`, que dé solo `column_inserted`.

### F3 [nit] El corrimiento de referencias más allá de la última fila alineada no tiene test
- **Repro:** el mutante que cambia en `_shift` la rama "después del último ancla" por `return x` sobrevive. En la simulación real no cambió ningún resultado, porque ninguna fórmula apunta a filas sin datos debajo de una inserción. Le falta un test, por ejemplo `=SUM(B4:B500)` después de insertar una fila arriba.

## No verificado

- **Criterios 2, 3 y 5:** requieren editar la planilla de prueba de Ariel, y QA no escribe en Google. Para el 2, insertar la fila con la clave escrita (ver F4 de la ronda 1).
- **Criterio 8:** posterior al merge (un día de worker sobre las planillas reales).
- **Build de imágenes:** no corrido; el arreglo no cambia Dockerfile ni dependencias.

## Split-outs sugeridos (fuera del alcance)

- Ninguno nuevo. El de la ronda 1 (colores sobre celdas vacías) ya está en `plan/improvements.md`.
