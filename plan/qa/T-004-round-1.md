# QA T-004 — Ronda 1

**Verdict: FAIL**
**Branch:** arielvinas/t-004 @ c586745
**Gates:** ruff check ✓ · ruff format --check ✓ (47 archivos) · pytest ✓ (140 passed, con `TEST_DATABASE_URL` apuntando a un PostgreSQL 16 descartable de QA en `127.0.0.1:55434`) · build de imágenes no corrido (el ticket no toca Dockerfile ni dependencias)
**Criteria:** 6/10 verificados (1, 4, 6, 7, 9, 10). Los criterios 2, 3 y 5 necesitan editar la planilla de prueba de Ariel y el 8 es posterior al merge; ver "No verificado". El criterio 2 se cumple al pie de la letra en la simulación, pero no en su intención (F1).
**Mutation:** 19 mutantes sobre `compare.py`, `detect.py`, `store.py` e `importer.py`; 18 detectados. Quitar `normalize` hace fallar 10 tests, entre ellos `test_a_moved_row_is_one_row_moved_and_nothing_else` y `test_a_moved_row_respelled_still_aligns_by_normalized_key`, así que el criterio 1 se cumple. Sobrevive uno (F2).

## Cómo se probó

- Tests de integración contra un contenedor `postgres:16` propio de QA, borrado al final. No toqué la base de desarrollo.
- Para datos reales usé solo lectura sobre la base local de desarrollo (snapshots que ya importó el worker), copiada a `/tmp` y borrada al final. No hubo ninguna llamada a Google. El reporte muestra solo conteos, nunca valores.
- Las siete pestañas con esquema, sobre su último snapshot real: el encabezado aparece en todas, ninguna cae a comparación por posición y comparar cada snapshot consigo mismo da 0 cambios.
- Historia real completa: 23 pares de snapshots consecutivos de la misma pestaña pasados por `compare` + `find`. Resultado: 0 excepciones, 214 cambios `value`, 0 `formula`. En esa historia no hubo inserción de filas, que es lo que dispara F1.

## Criterios

1. ✓ 22 tests en `test_diff_compare.py` en verde; el mutante "sin normalización" los pone en rojo (ver Mutation).
2. ⚠ No verificado en la planilla de prueba. Lo cubre la suite sintética (inserción arriba del bloque → un `row_inserted`, sin `value`; `color` con hexadecimales; `emptied`). Ver F1: en una pestaña real con fórmulas, la misma inserción produce cientos de `formula`.
3. ⚠ No verificado en la planilla de prueba. El upsert por (`type`, `stable_key`) y la actualización de `last_seen_at` están cubiertos en `test_diff_store.py`. Sobre los snapshots reales se detectan colores fuera de la lista de R29 (por ejemplo `#ffff00` y `#ea9999`), uno por pestaña y color.
4. ✓ `v_issue` muestra `ignorado`, que se mantiene tras una nueva detección, y `reabierto` tras `resuelto` + detección (tests de integración en verde; el mutante que invierte el orden de resoluciones se detecta).
5. ⚠ No verificado en la planilla de prueba. `register_tabs` registra `tab_renamed` conservando el id de `source_tab` y sus snapshots, y `tab_added` + `pestana_sin_clasificar`; cubierto por tests de integración. También registra `tab_rename_blocked` cuando el nombre nuevo ya existe.
6. ✓ `config/sources.yaml` tiene siete esquemas (el ticket dice "seis pestañas" y nombra siete) y `sources load` los guarda en `source_tab.schema`. El diff del YAML no contiene nombres de clientes.
7. ✓ Sin esquema, un cambio de valor da `value` con `cell_ref` y `row_key` nulo (test en verde y verificado a mano).
8. ⚠ Posterior al merge, legítimamente: necesita un día de worker sobre las planillas reales.
9. ✓ Las fixtures usan "Cliente A/B" y montos inventados. `tab_diffed` y la salida de `craftech-os diff` muestran solo conteos. `cell_change` guarda valores y solo se lee desde la base.
10. ✓ `uv run pytest` y `ruff check` en limpio.

## Findings

### F1 [major] Insertar una fila en una pestaña con fórmulas genera cientos de cambios `formula` falsos
- **Contexto:** cuando se inserta, borra o mueve una fila, Google reescribe las referencias de todas las fórmulas que apuntan debajo. Por ejemplo, `=C98+D98` pasa a ser `=C99+D99`. `cell_changes` compara el texto de la fórmula tal cual (`of != nf`), así que cada fórmula desplazada cuenta como un cambio.
- **Repro:** se toma el último snapshot real de "Pagos" de Craftech Total y se inserta en una copia local una fila con clave en el bloque "General", desplazando las referencias como lo haría Google. Después se corre `compare(viejo, nuevo, esquema)`.
- **Expected:** un `row_inserted` y nada más, que es la intención del criterio 2 y del riesgo "cientos de cambios falsos" que el ADR-001 pide evitar.
- **Actual:** `{'formula': 405, 'row_inserted': 1}` y 0 `value`. Eso supera la alarma de 200 cambios por pestaña por día del ADR, con una sola inserción.
- **Alcance:** celdas con fórmula en los últimos snapshots reales de las siete pestañas con esquema:

  | Planilla | Pestaña | Celdas con fórmula | Con referencia a su propia fila |
  |---|---|---|---|
  | Craftech Total | Pagos | 1097 | 584 |
  | SleakOps Total | Pagos | 1375 | 321 |
  | Craftech Total | VENTAS | 980 | 494 |
  | SleakOps Total | VENTAS | 459 | 254 |
  | Craftech Total | Pagos ARG | 1162 | 188 |
  | SleakOps Total | Pagos ARG | 204 | 34 |
  | FUNDINGS | FUNDINGS | 91 | 91 |

- **Sugerencia (no la apliqué):** comparar las fórmulas en forma relativa a la celda (al estilo R1C1, con desplazamientos en lugar de números de fila) o descontar el desplazamiento de filas de la alineación antes de comparar. Agregar fixtures con fórmulas a `test_diff_compare.py`, porque hoy ninguna tiene fórmulas.

### F2 [minor] La rama de huecos con distinta cantidad de filas con clave no tiene test, y si se rompe tumba el worker
- **Repro:** el mutante que reemplaza `if old_keyed and new_keyed and len(old_keyed) != len(new_keyed):` en `compare.py` por `if False:` sobrevive a toda la suite.
- **Por qué importa:** sin esa guarda, el `zip(..., strict=True)` siguiente lanza `ValueError`. Como el diff corre dentro de la transacción del snapshot (`importer.read_tab`), la excepción haría perder el snapshot y el worker reintentaría la misma pestaña en cada vuelta.
- **Expected:** un test con un hueco entre anclas que tenga, por ejemplo, dos filas con clave de un lado y una del otro.

### F3 [minor] `alineacion_ambigua` falsa cuando se inserta y se borra en el mismo bloque en una misma lectura
- **Repro:** bloque "General" con filas A, B, D. Entre dos lecturas se inserta "Cliente C" arriba y se borra "Cliente D" abajo.
- **Expected:** `row_inserted` C + `row_deleted` D, sin problemas.
- **Actual:** los cambios salen bien, pero además se crean dos `issue` `alineacion_ambigua` (para `cliente c` y `cliente d`) que quedan abiertos para siempre. Las claves no se repiten ni hay duda real. Con dos ediciones entre lecturas de cinco minutos, esto aparecerá en las planillas reales.
- (En cambio, renombrar dos claves a una sola en el mismo lugar marca A, B y X como ambiguas, que es razonable.)

### F4 [minor] Insertar una fila vacía no deja ningún cambio
- **Repro:** se inserta una fila en blanco arriba del bloque.
- **Actual:** `[]`. El documento del snapshot (T-002) omite las filas sin celdas, así que la fila vacía no existe para el diff. Las filas de abajo tampoco cambian, porque se alinean por clave.
- **Riesgo:** si en la prueba en vivo del criterio 2 se inserta una fila vacía, el resultado será "ningún `row_inserted`". Para esa prueba, conviene insertar una fila con al menos la clave escrita. No lo considero un error del diff (una fila vacía no es un compromiso), pero hay que avisarlo.

### F5 [nit] Problemas que no se pueden detectar o que se agrupan de más
- Los colores `#c9daf8` y `#d0e0e3` que registra F-05 en `docs/02-questions.md` están en celdas vacías. El documento de T-002 descarta las celdas que solo tienen color de fondo, así que `color_desconocido` nunca los va a ver. La expectativa del `## Post-merge` del ticket sobre `#d0e0e3` no se va a cumplir.
- La clave estable de `valor_ilegible` es `{clave de fila}:{encabezado}` sin el ordinal. Dos filas con la misma clave y texto en el mismo mes se unen en un solo problema. Por ejemplo, en SleakOps Total "Pagos" hay 9 `valor_ilegible`.

## No verificado

- **Criterios 2, 3 y 5:** requieren editar la planilla de prueba de Ariel (insertar filas, pintar celdas, renombrar y agregar pestañas). QA no escribe en Google, así que son pruebas manuales de Ariel. Las cubren tests de integración sintéticos y mutantes. Para el 2, ver F1 y F4.
- **Criterio 8:** posterior al merge (un día de worker sobre las planillas reales), como dice el ticket.
- **Build de imágenes:** no corrido; el ticket no cambia Dockerfile ni dependencias.

## Split-outs sugeridos (fuera del alcance)

- [T-002] El documento del snapshot descarta las celdas que solo tienen color de fondo, y con eso los colores de F-05 sobre celdas vacías quedan invisibles para `color_desconocido`. Decidir si conservarlas (ver F5).
