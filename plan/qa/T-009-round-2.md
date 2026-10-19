# QA T-009 — Ronda 2

**Verdict: FAIL**
**Branch:** arielvinas/t-009-clientes-canonicos @ 626d540
**Gates:** typecheck — (el repo no tiene) · lint ✓ (`ruff check`) · formato ✓ (`ruff format --check`, 75 archivos) · tests ✓ (235 passed, 0 skipped, con `TEST_DATABASE_URL` y las claves de los roles MCP) · build ✓ (`docker build -f infra/Dockerfile`)
**Criteria:** 6/7, igual que en la ronda 1 (los cambios desde entonces solo tocan `diff/compare.py`, el README y el ticket). El criterio 6 sigue diferido a Post-merge.
**Mutation:** 4 mutantes a mano sobre los dos cambios de `compare.py`: 3 muertos, 1 sobreviviente (F2)

Alcance de esta ronda: `git diff a671d27..HEAD`, es decir, los dos arreglos que pidió CodeRabbit en `app/craftech_os/diff/compare.py`, más el README y el ticket:
- (a) `present` ya no cuenta las filas hechas solo de celdas pintadas al correr las referencias de las fórmulas;
- (b) pintar o despintar una celda vacía genera un cambio de tipo `color`.

Entorno: contenedor propio `qa-t009-r2-pg` (postgres 16, scripts de `infra/postgres-init`), borrado al terminar. Pruebas en `/tmp/qa-t009-r2/` con documentos inventados. Para comparar contra la ronda 1, el código de `a671d27` se extrajo con `git archive`. Nada se escribió en Google Sheets ni en Drive.

## Findings

### F1 [major] La primera lectura después del deploy registra cambios `color` falsos en las pestañas CARGA con esquema
- **Repro:** `/tmp/qa-t009-r2/probe_deploy.py`. Toma la misma grilla de la API de Sheets: una pestaña "Pagos" con esquema, donde una fila de cliente está pintada entera de verde y tiene dos celdas vacías dentro. Arma el documento como lo guardaba la etapa A (`document.build(grid, False)`) y como lo guarda T-009 (`document.build(grid, True)`), y los compara con `compare`.
- **Expected:** 0 cambios. En la planilla no cambió nada; solo cambió lo que guardamos. El `## Test plan` del ticket lo promete: "El hash de las pestañas CARGA con esquema cambia una vez en la primera lectura después del deploy, y eso no genera cambios espurios". La ronda 1 lo había verificado.
- **Actual:** 2 cambios, `color C3 None -> #d9ebd4` y `color E3 None -> #d9ebd4`. El mismo script contra el código de la ronda 1 (`a671d27`) da 0.
- **Por qué importa:**
  - `diff/store.record` inserta esos cambios en `cell_change`, que es permanente, y salen por `mcp.changes`.
  - El comentario de `mcp.changes.tipo` dice que un cambio `color` "en la grilla de meses es un cambio de estado según la regla R29". Desde Claude Desktop se van a leer como cambios de estado que nadie hizo.
  - En las planillas reales es habitual pintar la fila entera para marcar un estado. Entonces la primera lectura de Pagos, Pagos ARG, VENTAS y FUNDINGS puede dejar cientos de cambios falsos, uno por cada celda vacía pintada dentro de una fila con datos.
  - Las filas hechas solo de celdas pintadas no generan cambios, porque se filtran antes de alinear.
- **Misma clase:** pasa lo mismo cada vez que una pestaña gana o pierde su esquema, o la clase CARGA, en `config/sources.yaml`. `keep_color_only` cambia de valor y aparecen o desaparecen de golpe todas las celdas vacías pintadas. También pasa en la comparación por posición, cuando una pestaña con esquema pierde su fila de encabezado.
- **Causa:** el cambio (b). `cell_changes` ahora toma una celda ausente como "sin pintar", pero en un documento anterior a T-009 una celda ausente puede estar pintada: simplemente no se guardaba.
- **Arreglos posibles (decide el runner):**
  1. Marcar el formato del documento, por ejemplo con una clave `color_only: true` que pone `document.build` cuando `keep_color_only` está activo. Pasar `None ↔ bg` en una celda ausente cuenta como cambio solo si los dos documentos tienen la marca.
  2. Revertir (b) y anotar en `plan/improvements.md` que pintar una celda vacía no genera cambio, para decidirlo después.

  En los dos casos falta un test: el mismo documento de la etapa A contra el de T-009 tiene que dar 0 cambios. Ese test no existía, y por eso el arreglo de CodeRabbit pasó con la suite en verde.

### F2 [minor] Hueco de test: escribir en una celda vacía que ya estaba pintada no debe sumar un cambio `color`
- **Repro:** cambiar en `cell_changes` la condición `(... or nv is None)` por `(... or True)`. La suite completa sigue verde: 235 passed.
- Con ese mutante, escribir un valor en una celda vacía con fondo (antes ausente, ahora `{value, bg}`) genera `value` y además `color None -> bg`. Es el caso común de cargar un dato en una fila pintada. La condición nueva está bien, pero ningún test la fija.

### F3 [minor] Pintar una celda vacía genera un cambio solo si la fila tiene algún valor
- **Repro:** `/tmp/qa-t009-r2/probe_formula.py`, casos 6 y 7. Pintar o despintar una celda de una fila totalmente vacía no genera ningún cambio. En cambio, pintar una celda vacía de una fila con datos sí genera `color`.
- Es una consecuencia de la decisión de la ronda 1: una fila hecha solo de celdas pintadas no es una fila. Pero el nombre del test nuevo (`test_painting_or_unpainting_an_empty_cell_is_a_color_change`) promete más de lo que hace. Si se mantiene (b), conviene documentar este límite en el docstring o en el nombre del test.

## Cambio (a): corrimiento de fórmulas, verificado ✓
`/tmp/qa-t009-r2/probe_formula.py` compara nueve escenarios con el código de esta rama y con el de la ronda 1:
- documentos idénticos;
- una fila insertada o borrada arriba de una fila pintada vacía;
- un rango que empieza o termina en la fila pintada;
- pintar o despintar una fila vacía;
- dos escenarios con documentos de la etapa A, sin celdas pintadas.

Con esta rama, los nueve dan 0 cambios de fórmula. Con la ronda 1, cinco daban cambios `formula` falsos, incluso con documentos idénticos (`=B6+SUM(B4:B6)` contra sí misma). El arreglo corrige un error real que la ronda 1 no vio.

Para las pestañas de la etapa A, por lectura del código: todas las celdas guardadas tienen la clave `value`, aunque sea nula. Por lo tanto `_has_value` no deja afuera ninguna fila y el `present` nuevo es igual al anterior. Los dos escenarios de la etapa A lo confirman.

## Mutación
| Mutante | Resultado |
|---|---|
| M1: volver `present` a todas las filas de `old_doc` (revertir a) | muere (`test_a_formula_pointing_at_a_painted_empty_row_does_not_change`) |
| M2: sacar `or nv is None` (revertir b) | muere (`test_painting_or_unpainting_an_empty_cell_is_a_color_change`) |
| M3: `or True` (color también cuando aparece un valor) | **sobrevive** → F2 |
| M4: ignorar el despintado (`new_bg ... or old_bg`) | muere |

## Re-verificación de la ronda anterior
- F1 a F5 (r1, todos `minor`): siguen abiertos. Desde `a671d27` no hubo cambios en `clients.py` ni en `ingest/` ni en sus tests, así que no hay nada nuevo que verificar. Siguen siendo `minor` y no cambian el veredicto.
- La afirmación de la ronda 1 de que "la primera lectura después del deploy no genera cambios espurios" **ya no vale**: ver F1.
- README y ticket: la ruta `/data/Contacts.csv` coincide con el montaje `-v ~/repos/craftech-os-data:/data:ro`. ✓

## No verificado
- El criterio 6 contra la planilla real (pintar una celda en la planilla de prueba de Ariel): QA nunca escribe en Google Sheets. Sigue en Post-merge, igual que en la ronda 1. Cuando se haga esa prueba, conviene contar cuántos cambios `color` deja la primera lectura después del deploy. Si F1 está arreglado, tienen que ser 0.

## Split-outs sugeridos (fuera del alcance)
- Ninguno nuevo. F1 está dentro del alcance: es la promesa explícita del `## Test plan` del ticket.
