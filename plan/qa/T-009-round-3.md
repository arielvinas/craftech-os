# QA T-009 — Ronda 3

**Verdict: PASS**
**Branch:** arielvinas/t-009-clientes-canonicos @ efc75ce
**Gates:** typecheck — (el repo no tiene) · lint ✓ (`ruff check`) · formato ✓ (`ruff format --check`, 76 archivos) · tests ✓ (237 passed, 0 skipped, con `TEST_DATABASE_URL` y las claves de los roles del servidor MCP) · build ✓ (`docker build -f infra/Dockerfile`)
**Criteria:** 6/7, igual que en las rondas 1 y 2. El criterio 6 (planilla de prueba real) sigue diferido a Post-merge.
**Mutation:** 7 mutantes a mano sobre `diff/compare.py`, `ingest/document.py` e `ingest/importer.py`: 7 muertos, 0 sobrevivientes

Alcance de esta ronda: `git diff 4904487..HEAD`. Son cuatro archivos:
- `app/craftech_os/diff/compare.py`: se revierte el cambio (b). Pintar o despintar una celda ausente ya no genera un cambio `color`.
- `app/tests/test_diff_compare.py`: sale el test de (b) y entra `test_keeping_painted_empty_cells_changes_nothing_on_the_first_read`. Ese test lee la misma grilla como en la etapa A y como en T-009, y compara en los dos sentidos: con esquema, sin esquema, y con esquema pero sin la fila de encabezado.
- `plan/improvements.md`: una línea `[decision-pending]` con lo que queda por decidir.
- el ticket.

Entorno: contenedor propio `qa-t009-r3-pg` (postgres 16, con los scripts de `infra/postgres-init`), borrado al terminar junto con la imagen de prueba. Las sondas están en `/tmp/qa-t009-r3/` y usan documentos inventados. Nada se escribió en Google Sheets ni en Drive.

## Findings

### F1 [minor] El README todavía dice que una celda vacía con solo color no se guarda
- **Dónde:** `README.md:109`, al final del párrafo de problemas: "Una celda vacía que solo tiene color no se guarda en la foto, así que su color no se detecta."
- **Expected:** desde T-009, en las pestañas CARGA con esquema la celda se guarda como `{c, bg}` y `color_desconocido` la ve. Lo que sigue sin pasar es que pintarla o despintarla genere un cambio `color`. Eso está anotado en `plan/improvements.md` y en el ticket, pero no en el README.
- **Actual:** la frase viene de la etapa A y T-009 no la actualizó. Un lector del README cree que `color_desconocido` sigue ciego a las celdas vacías.
- Es documentación y no cambia el veredicto. Hay que corregir esa frase en esta rama.

## Re-verificación de la ronda anterior
- **F1 (r2, major), cambios `color` falsos en la primera lectura después del deploy: ✓ resuelto.**
  - `cell_changes` volvió a ser igual al de `main`, salvo un comentario: hay cambio `color` solo cuando la celda está en los dos documentos.
  - La sonda de la ronda 2 (`probe_deploy.py`, fila de cliente pintada entera con dos celdas vacías) daba 2 cambios. Ahora da 0.
  - Repasé la misma clase de casos con `/tmp/qa-t009-r3/bin/probe_r3.py`, con esquema y por posición:
    - la lectura del deploy sin edición da 0 cambios;
    - la lectura del deploy con un valor escrito en la celda pintada da solo `value`;
    - pasar de un documento de T-009 a uno de la etapa A (la pestaña pierde el esquema) da 0 cambios;
    - entre dos documentos de T-009, cambiar el color de una celda vacía ya pintada da `color`;
    - entre dos documentos de T-009, pintar una celda con valor da `color`;
    - entre dos documentos de T-009, escribir en una celda pintada da solo `value`.
    
    Los 12 casos dan lo esperado. El test nuevo cubre los dos sentidos y las tres formas de comparar.
- **F2 (r2, minor), faltaba un test para "escribir en una celda pintada no suma `color`": ✓ resuelto por la reversión.** Con la condición actual, el caso no puede dar `color`: la celda ausente no se compara. M3 (abajo) prueba que el test nuevo mata la variante amplia de la condición.
- **F3 (r2, minor), el nombre del test prometía más de lo que hacía: ✓ ya no aplica.** El test se borró junto con (b).
- **F1 a F5 (r1, todos minor): siguen abiertos.** Desde la ronda 2 no hubo cambios en `clients.py` ni en `ingest/`. F3, F4 y F5 están en `plan/improvements.md`.

## Cambio (a), corrimiento de fórmulas con filas solo pintadas: ✓ sigue valiendo
- `/tmp/qa-t009-r3/probe_formula.py` (los nueve escenarios de la ronda 2) da 0 cambios de fórmula falsos en los nueve.
- El mutante M1 lo revierte y muere en `test_a_formula_pointing_at_a_painted_empty_row_does_not_change`.

## Alcance del cambio en las pestañas de la etapa A
Lo verifiqué leyendo `git diff main..HEAD` sobre `ingest/` y `diff/`, y lo confirmé con las sondas.
- **`document.build(grid, False)`, el modo de toda pestaña que no es CARGA con esquema:** produce lo mismo que en `main`. El único cambio es que `fmt` se lee antes del chequeo. Una celda sin valor sigue devolviendo `None`.
- **`compare`:** en un documento de la etapa A, toda celda guardada tiene la clave `value`, así que `_has_value` es verdadero en todas las filas. Por eso `old_by_name` y `present` son iguales a los de `main`, porque `blocks` reparte todas las filas, incluidas las de antes del encabezado. Los escenarios de la etapa A en `probe_formula.py` dan lo mismo que antes.
- **`cell_changes`:** es igual a `main`.
- **`importer.read_tab`:** activa `keep_color_only` solo cuando la pestaña es `class = 'CARGA' AND schema IS NOT NULL`. M7, que lo activa para todas, muere.

## Mutación
Harness: `/tmp/qa-t009-r3/bin/mutants.py`. Si falta un archivo o un patrón, falla, y restaura cada archivo con `git checkout`.

| Mutante | Resultado (test que lo mata) |
|---|---|
| M1: revertir (a), `present` con todas las filas de `old_doc` | muere (`test_a_formula_pointing_at_a_painted_empty_row_does_not_change`) |
| M2: reintroducir (b), una celda ausente cuenta como sin pintar | muere (`test_keeping_painted_empty_cells_changes_nothing_on_the_first_read`, el test nuevo) |
| M3: `color` si existe cualquiera de los dos lados | muere (el test nuevo) |
| M4: no generar nunca `color` | muere (`test_a_color_change_has_both_hexadecimals`, que ya existía) |
| M5: no filtrar las filas solo pintadas al alinear | muere (`test_a_painted_empty_cell_is_kept_only_in_a_carga_tab_with_schema`) |
| M6: `keep_color_only` nunca guarda la celda | muere (el mismo) |
| M7: `keep_color_only` en todas las pestañas | muere (el mismo) |

Atribución: M2 y M3 los mata el test agregado en esta ronda, que es lo que hacía falta probar. M4 lo mata un test que ya existía, y está bien así: dice que la reversión no apagó los cambios `color` reales.

## No verificado
- **Criterio 6, contra la planilla real:** QA nunca escribe en Google Sheets. Sigue en Post-merge (paso 6), como en las rondas anteriores. Cuando se haga esa prueba, la primera lectura después del deploy tiene que dejar 0 cambios `color`. Pintar la celda vacía tiene que verse en `mcp.celdas` y, si el color no está en la lista, abrir `color_desconocido`. No va a aparecer un cambio `color` en `mcp.changes`: es el límite que se aceptó y quedó anotado.
- Sin navegador: T-009 no tiene pantallas (las pantallas web son de T-014).

## Split-outs sugeridos (fuera del alcance)
- Ninguno nuevo. La decisión pendiente sobre los cambios `color` en celdas vacías ya está en `plan/improvements.md`.
