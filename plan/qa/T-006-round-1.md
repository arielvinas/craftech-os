# QA T-006 — Ronda 1

**Verdict: PASS**
**Branch:** arielvinas/t-006 @ 3bcdf72
**Gates:** ruff check ✓ · ruff format --check ✓ (53 archivos) · pytest ✓ (166 passed, 1 warning: la deprecación de httpx en Starlette, ya registrada en `plan/improvements.md`; con `TEST_DATABASE_URL` apuntando a la base `_test`) · build de la imagen `web` ✓ (`docker compose up -d --no-deps --build web`)
**Criteria:** 8/10 verificados por completo (1, 3, 4, 5, 6, 7, 9, 10). El 2 y la segunda parte del 8 necesitan datos reales que todavía no existen: la base real tiene 0 `cell_change` y 0 `issue`, y T-005 no está mergeado. Los dos están cubiertos con datos sintéticos y anotados en `## Post-merge` (ver "No verificado").
**Mutation:** de 6 mutantes, 4 hacen fallar la suite. Cada uno corresponde a un cambio central: el autoescape, el pedido pendiente único, la validación de filtros y la CSP. Sobreviven 2, el escape del `ILIKE` y el "hasta" inclusivo (F1).

## Cómo se probó

- Leí todo el diff del ticket: `web/app.py`, `web/queries.py`, las plantillas, `style.css`, `cli.py`, `docker-compose.yml`, `pyproject.toml` y `test_web.py`. Comparé los tipos de cambio y de problema de la web con los `CHECK` de `0004_cell_change_issue.sql`, y los `kind` de `system_event` con lo que escribe el worker. Coinciden.
- **Contenedor contra la base real, solo lectura.** Levanté `web` con `--no-deps`. `postgres` y `worker` no se tocaron: su uptime no cambió. Para que Compose encontrara `infra/.env` puse un symlink temporal al `.env` de main, ignorado por git, y lo borré al final. Sobre ese contenedor solo hice pedidos GET y POST a ids inexistentes. No hice ningún "leer ahora" real porque el implementador ya lo había hecho.
- **Base `_test` sembrada con datos ficticios, servida en `127.0.0.1:8001`** con `uv run craftech-os web --port 8001`:
  - 3 fuentes: una con el título "Facturación - Craftech Total", otra con HTML en el título y una sin `drive_id`.
  - 236 cambios: un valor `<script>`, una fórmula con `<img onerror>`, un color `#ff0000`→`#00ff00`, un color malformado con comillas, una atribución `una_de`, un cambio `sin_datos` con unicode largo y 230 cambios masivos.
  - 2 problemas `color_desconocido`, vueltas del worker, un `source_read` con `drive_version` y un `api_retry`.
- **Navegador real (Orca/Chromium)** para los criterios 2, 3, 4, 5 y 6, con capturas en `plan/qa/evidence/`. Las capturas son todas de la base `_test` con datos ficticios: ninguna muestra valores reales.
- **Chequeo de mutantes:** apliqué cada mutante con `sed`, corrí `uv run pytest app/tests/test_web.py` y lo revertí con `git checkout`. Al terminar, `git status` quedó limpio.

## Criterios

1. ✓ `docker compose port web 8000` da `127.0.0.1:8000`. `curl` a `192.168.100.206:8000`, la IP de la red local, falla con código 7 (conexión rechazada). `/` responde 303 hacia `/cambios`.
2. ⚠ Verificado con datos sintéticos; con datos reales queda pendiente. Sobre la base `_test`:
   - `?planilla=1&tipo=color` muestra solo las 2 filas de color, con el cuadrado y los hexadecimales anterior y nuevo (`T-006-r1-cambios-color.png`).
   - El detalle muestra las fórmulas anterior y nueva.
   - El color malformado se ve como texto, sin cuadrado.

   La base real no tiene ningún `cell_change`, así que la verificación real queda en `## Post-merge`.
3. ✓ Lo cubre el test `test_cell_values_are_escaped`. En el navegador, el HTML servido no tiene ningún `<script`, el DOM tiene 0 elementos `script` y 0 `img`, y el texto `<script>alert(1)</script>` se ve literal, tanto en la lista como en el detalle (`T-006-r1-cambio-script.png`). La fórmula con `<img onerror>` también se ve como texto.
4. ✓ Con problemas sintéticos, porque la base real tiene 0 `issue`.
   - La fila aparece `abierto` (`T-006-r1-problemas-abierto.png`).
   - Inserté por SQL una resolución `ignorado` con autor y motivo; el motivo incluía HTML. La fila pasó a `ignorado` y mostró el autor y el motivo, con el HTML escapado (`T-006-r1-problemas-ignorado.png`).
   - Un problema resuelto hace una hora y visto después se muestra `reabierto`.
   - El filtro por estado separa bien los cuatro estados.
   - En el detalle, el JSON con `<script>` se ve escapado.
5. ✓ En la base real, `/fuentes` (por `curl`) muestra "20 planillas." y "Pedido de lectura pendiente: no" en las 20. En `_test`:
   - Muestra pestañas, clase, último snapshot, última vuelta, el intervalo máximo (0:37:00) y la versión de Drive 4711.
   - Sin dump aparece el aviso de más de 48 horas (`T-006-r1-fuentes-sin-dump.png`).
   - El test `test_fuentes_warns_when_the_dump_is_missing_or_old` cubre los tres casos: sin dump, dump viejo y dump reciente.
6. ✓ En el navegador sobre `_test`:
   - El primer clic dio "Pedido de lectura creado…" (`T-006-r1-leer-ahora-1.png`).
   - El segundo dio "Ya había un pedido pendiente…" (`T-006-r1-leer-ahora-2.png`), y en la base sigue habiendo un solo `read_request` pendiente.
   - En la planilla sin `drive_id`, el mensaje es "no tiene identificador de Drive" y no se crea ningún pedido.
   - Recargar la página después del 303 no repite el POST.

   En la base real, el único `read_request` es el del implementador: se pidió a las 03:33:57 UTC y el worker lo atendió a las 03:35:56 UTC, o sea que "en la siguiente vuelta la planilla aparece releída" se cumplió.
7. ✓ `?tipo=xxx` da 400 y `/cambios/999999` da 404 con la página de error, sin traza, tanto en el contenedor real como en los tests. Probé además estos casos, todos sin traza:

   | Pedido | Respuesta |
   |---|---|
   | `/cambios/abc` | 400 |
   | ids enormes, en la ruta y en el POST | 404 |
   | `pagina=100001` | 400 |
   | "clave" de 201 caracteres | 400 |
   | `desde=2026-13-01` | 400 |
   | planilla con dígitos de ancho completo | 400 |
   | `/docs` y `/openapi.json` | 404 |
   | `GET` a `leer-ahora` | 405 |
   | editor con texto que parece SQL | 200 |
   | `%_\` en "clave" | 200 |
8. ⚠ Primera parte ✓: un cambio `sin_datos` dice "sin atribuir (Google no informó editor)", y una atribución `una_de` muestra "una de: people/1, people/2". El test `test_attribution_shows_unattributed_then_the_profile_name` comprueba que, si existe `editor_profile`, se muestra el nombre más nuevo. La segunda parte es posterior al merge de T-005 y está en `## Post-merge`.
9. ✓ `grep -r autoescape app/craftech_os/web/` muestra `autoescape=True`. Con el mutante M1 fallan `test_autoescape_is_forced` y `test_cell_values_are_escaped`.
10. ✓ `pytest` y `ruff check` pasan en limpio. Las plantillas y los tests usan solo nombres ficticios ("Planilla Ficticia A", "Revisora Ficticia", `people/111`).

## Mutación

| Mutante | Resultado |
|---|---|
| M1 `autoescape=False` en `app.py` | ✓ muere: 2 tests fallan |
| M2 sin `ON CONFLICT DO NOTHING` en `request_read` | ✓ muere: falla `test_read_now_twice_leaves_one_pending_request` |
| M3 `_choice` acepta cualquier valor | ✓ muere: fallan 3 casos de `test_invalid_filter_is_400_without_the_database` |
| M4 sin el header CSP | ✓ muere: falla `test_every_screen_answers_200` |
| M5 "clave" sin escapar `%`, `_` y `\` en el `ILIKE` | ✗ sobrevive (F1) |
| M6 "hasta" sin el día siguiente (deja de ser inclusivo) | ✗ sobrevive (F1) |

## Hallazgos

### F1 — minor — Dos reglas de filtro documentadas no tienen test
`## Implementation` dice que "clave" escapa `%`, `_` y `\`, y que "hasta" es inclusivo porque se compara con el día siguiente (`app/craftech_os/web/queries.py:32` y `:44`). Si se borra cualquiera de las dos cosas, los 16 tests siguen en verde (mutantes M5 y M6). En el navegador las dos funcionan:
- `clave=%` da 0 filas;
- `desde=hasta=2026-10-05` da las 13 filas de ese día.

Pero una regresión no la detectaría nadie: buscar "%" mostraría todos los cambios, y filtrar un solo día no mostraría nada. Sugerencia: dos asserts en `test_filters_narrow_the_changes`.
- `?clave=%` no debe traer ninguna fila.
- `?desde=X&hasta=X`, con X el día de hoy en Buenos Aires, debe traer los cambios sembrados.

### F2 — nit — Variable `now` sin usar
`app/craftech_os/web/app.py:247` pasa `"now": datetime.now().astimezone()` a `fuentes.html`, pero la plantilla no lo usa. Es código muerto.

### F3 — nit — Enlace de paginación con `?&` cuando no hay filtros
`cambios.html:95` y `:97` arman `/cambios?{{ query }}&pagina=N`. Sin filtros, el enlace queda `/cambios?&pagina=2`. Funciona igual, porque el parámetro vacío se ignora; solo se ve feo en la barra de direcciones.

### F4 — nit — Sin `<meta name="viewport">`
`base.html` no declara `viewport`, así que en un celular la página se dibuja a 980 px de ancho y achicada (medido con emulación de iPhone 12: `innerWidth` 980). La versión para celular no es un criterio del ticket y la app es local para la laptop. Lo anoto por si más adelante se usa desde el teléfono.

## No verificado

- **Criterio 2 con datos reales:** no hay ningún `cell_change` en la base real. Queda en `## Post-merge`; con datos sintéticos está verificado arriba.
- **Criterio 4 con los `color_desconocido` reales de T-004:** no hay ningún `issue` en la base real. Está cubierto con datos sintéticos, en el test y en el navegador.
- **Criterio 8, segunda parte:** depende de que se mergee T-005. Queda en `## Post-merge`.
- **"Leer ahora" con un clic en el navegador contra la base real:** lo evité a propósito para no escribir en la base compartida. El implementador hizo el POST por HTTP y el worker lo atendió; en el navegador lo verifiqué sobre `_test`.

## Limpieza

Al terminar dejé todo como estaba:
- Paré el servidor de `:8001`.
- Paré y borré el contenedor `craftech-os-web-1` (`stop web` y `rm -f web`). `postgres` y `worker` siguieron corriendo, sin cambios.
- Borré el symlink `infra/.env`.
- Cerré la pestaña del navegador.
- La base `_test` quedó con los datos sembrados; los tests la recrean en cada corrida.

No hubo ninguna escritura en Google Sheets ni en Drive.

## Split-outs

Ninguno. F1 es un arreglo chico de tests dentro de este mismo ticket; F2, F3 y F4 se pueden anotar en `plan/improvements.md` si el coordinador lo prefiere.
