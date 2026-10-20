# QA T-014 — Ronda 1

**Verdict: PASS**
**Branch:** arielvinas/t-014-pantallas-ingresos @ 89bbf64
**Gates:** typecheck — (el proyecto no tiene) · lint ✓ (`ruff check`, `ruff format --check`, 54 archivos) · tests ✓ (301 passed) · build — (el proyecto no tiene)
**Criteria:** 6/6 verificados (el criterio 2 hasta el enlace generado; abrirlo en Google Sheets queda como prueba manual, ver "No verificado")
**Mutation:** 8 mutantes; 7 muertos por los tests nuevos de `app/tests/test_web.py`, 1 sobrevive (F1, minor: hueco de test, el código es correcto)

## Cómo se probó

- **Base sintética** propia (`craftech_os_t014_test`), con los datos de `_seed_ingresos` más datos adversariales: un cliente llamado `<script>alert(1)</script>` con alias `<b>xss</b>`, una factura de monto 0 en estado "a facturar" y un problema `alias_sin_cliente` cuyo texto es `<script>`. Servidor en el puerto 8114.
- **Base real** (`craftech_os`), solo con GET, en el puerto 8115, para medir contra las planillas. En este reporte solo figuran conteos y celdas, nunca nombres ni montos reales. Las capturas son todas de la base sintética.
- **Navegador real:** Playwright con Chromium, a 1280 px y a 375 px. Recorrido completo con clics desde el menú y los formularios, sin errores de consola ni de página.
- Los dos servidores quedaron detenidos al terminar.

## Criterios

1. **`/facturas` muestra las facturas del mes con estado y color; filtrar por "retraso" deja solo esas.** ✓
   - Sintético: en 2026-09 se ven las cuatro facturas, cada una con su muestra de color y el nombre del estado. Elegir "retraso" en el formulario y apretar Filtrar deja una sola fila, la de estado retraso. Evidencia: `evidence/T-014-r1-facturas-desktop.png` y `evidence/T-014-r1-facturas-retraso-desktop.png`, más las versiones `-mobile`.
   - Real: septiembre de 2026 muestra 48 facturas (46 pagadas y 2 en retraso), y el filtro por retraso deja exactamente esas 2.
   - Contra las planillas, por SQL: en las 1599 facturas de la base real, la celda de origen existe, su valor es igual al monto mostrado y su color de fondo corresponde al estado (regla R29 de colores por estado).
2. **El enlace de origen lleva a la planilla, pestaña y celda correctas.** ✓ hasta el enlace generado.
   - El enlace tiene la forma `https://docs.google.com/spreadsheets/d/<id del archivo>/edit#gid=<id de la pestaña>&range=<celda>`.
   - En la base real, todos los enlaces llevan un identificador de archivo de 44 caracteres y el identificador de pestaña de la pestaña de origen.
   - El barrido de celdas del criterio 1 confirma que la celda nombrada es la de la factura.
3. **Una paridad del mes distinta de 0 se ve resaltada en `/facturas`, con captura.** ✓
   - Sintético: una diferencia de 2.00 aparece en rojo sobre fondo rosado; se verificó el estilo calculado en el navegador, no solo la clase. Una diferencia de 0 en 2026-08 no se resalta. Evidencia: `evidence/T-014-r1-facturas-desktop.png`.
   - Real: el único mes con diferencia distinta de 0 (2025-05) aparece resaltado.
4. **`/fundings` muestra los hitos con su origen, y un duplicado aparece marcado.** ✓
   - Sintético: se ven los hitos de origen pagos y tracker. Los dos lados del par duplicado muestran "duplicado", y el enlace lleva a `/problemas/<id>` del problema `funding_duplicado`. Evidencia: `evidence/T-014-r1-fundings-desktop.png`.
   - Real: los 195 hitos con clave provisional lo indican. "duplicado" aparece dos veces, porque el único problema abierto nombra los dos lados. La diferencia de paridad de fundings que es distinta de 0 se ve resaltada.
5. **`/clientes` lista las filas sin cliente con enlace al problema, y no hay ningún control para editar.** ✓
   - Sintético: hay cero `form`, `input`, `button`, `textarea` y `select` en la página. El clic en una fila sin cliente lleva a su `/problemas/<id>`. Evidencia: `evidence/T-014-r1-clientes-desktop.png`.
   - Real: 415 filas sin cliente, con 0 clientes cargados.
   - Un POST a `/facturas` da 405, y el test `test_the_web_has_no_new_post_route` cubre el resto.
6. **Los logs del servidor no contienen nombres ni montos después de recorrer las tres pantallas.** ✓ Los logs de los dos servidores, el sintético y el real, solo tienen la ruta y los parámetros `mes`, `estado`, `entidad` y el número de cliente.

## Pasada adversarial

- **Filtros inválidos dan 400 "Filtro inválido":**
  - `mes=2026-13`, `mes=2026-9`, un mes con dígitos de ancho completo y un mes con `%00`;
  - `estado=Retraso`, porque la mayúscula no está en la lista cerrada;
  - `cliente=-1` y `cliente=1&cliente=abc`;
  - una `entidad` con un espacio al final.
- **Valores válidos pero extremos dan 200 sin errores:** `cliente=999999`, que no existe y da una tabla vacía; `mes=0001-01` y `mes=9999-12`.
- **Host ajeno:** da 400, porque el filtro de hosts permitidos solo acepta 127.0.0.1 y localhost.
- **Escapado de HTML:** no hay ningún `<script>` crudo en las tres pantallas. El cliente, el alias y el texto huérfano con HTML se muestran escapados, como se ve en las capturas.
- **Tiempo de respuesta:** con la base real, las tres pantallas responden en menos de 50 ms.
- **Pantalla angosta (375 px):** sin errores; las tablas se desbordan hacia la derecha (ver F4).
- **Pantallas que ya existían:** `/cambios`, `/problemas` y `/fuentes` siguen respondiendo y sus tests pasan. Los cambios en archivos compartidos, `base.html` y `style.css`, solo agregan enlaces y clases.

## Mutación

Cada mutante se aplicó a mano, se corrió `app/tests/test_web.py` y se restauró con `git checkout`. Atribución: en cada caso fallaba un test nuevo de este ticket.

| Mutante | Resultado | Test nuevo que lo mata |
|---|---|---|
| Quitar el resaltado de paridad en `facturas.html` | rojo | `test_a_parity_difference_is_highlighted_and_zero_is_not` |
| Quitar el resaltado de paridad en `fundings.html` | rojo | `test_fundings_shows_the_origin_and_marks_duplicates_and_provisional_keys` |
| Ignorar el filtro `estado` en `invoices` | rojo | `test_facturas_shows_the_state_with_its_color_and_filters_by_state` |
| Buscar el duplicado solo en el lado tracker | rojo | `test_fundings_shows_the_origin_and_marks_duplicates_and_provisional_keys` |
| Quitar el filtro de estado abierto o reabierto en `funding_duplicado` | **verde** | ninguno (F1) |
| Quitar el filtro de estado abierto o reabierto en las filas sin cliente | rojo | `test_clientes_lists_rows_without_client_and_has_no_edit_control` |
| Quitar Facturas del menú | rojo | `test_the_income_screens_answer_200_and_are_in_the_menu` |
| Quitar Clientes del menú | rojo | `test_the_income_screens_answer_200_and_are_in_the_menu` |

Después de restaurar, la suite completa da 301 passed y el árbol queda sin cambios.

## Findings

### F1 [minor] Ningún test cubre que un duplicado de funding ya resuelto deje de marcarse
- **Repro:**
  1. En `app/craftech_os/web/queries.py`, función `fundings`, borrar la condición `AND i.status IN ('abierto', 'reabierto')` de la subconsulta del duplicado.
  2. Correr `uv run pytest app/tests/test_web.py`: los 29 tests pasan.
- **Expected:** que un test falle. La sección de implementación del ticket dice que se marca solo con un problema `funding_duplicado` "abierto o reabierto".
- **Actual:** el código hoy hace lo correcto, lo comprobé leyéndolo, pero nada lo protege: si alguien quita la condición, un hito cuyo duplicado ya se resolvió volvería a mostrarse como "duplicado" sin que la suite lo note. El mismo filtro en las filas sin cliente sí está cubierto.
- **Sugerencia:** en el test de fundings, resolver el problema y comprobar que la marca desaparece.

### F2 [nit] El mes por defecto usa la fecha del sistema, no la zona horaria de Craftech
- `_month` en `app/craftech_os/web/app.py:130` usa `date.today()`, que depende de la zona horaria del servidor. En la máquina de Ariel coincide con Buenos Aires. Si algún día corre en un contenedor o servidor en UTC, entre las 21:00 y las 24:00 del último día del mes la pantalla abriría en el mes siguiente. El resto de la web ya convierte a Buenos Aires para mostrar los cobros.

### F3 [nit] `client_rows` puede dar 500 si se agrega un cliente durante la carga de la página
- `app/craftech_os/web/queries.py:316-327` hace tres consultas separadas: clientes, razones sociales y aliases. Arma un diccionario con los clientes de la primera consulta y después indexa con `found[r["cliente_id"]]`.
- Con el nivel de aislamiento por defecto, cada consulta ve datos nuevos. Si entre la primera y la tercera consulta se crea un cliente con un alias, por ejemplo desde Claude Desktop con `vincular_alias`, la página da un `KeyError` y responde 500. Al recargar, la página anda.
- Es muy improbable. Se arregla con una sola instantánea de la base (por ejemplo, una transacción `REPEATABLE READ`) o ignorando los identificadores que no están en el diccionario.

### F4 [nit] A 375 px las tablas desbordan la pantalla y la barra del menú queda cortada
- A 375 px, el ancho total de la página es de 730 px en `/facturas`, 932 px en `/fundings` y 551 px en `/clientes`. El fondo gris del menú solo cubre los primeros 375 px. Evidencia: `evidence/T-014-r1-facturas-mobile.png` y `evidence/T-014-r1-fundings-mobile.png`.
- Las pantallas que ya existían hacen lo mismo (`/cambios` 600 px, `/problemas` 675 px, `/fuentes` 624 px), así que no lo introduce este ticket. Ningún criterio pide uso en celular, y la web es para el escritorio de Ariel.

### F5 [nit] "sin cliente" se ve distinto en Facturas y en Fundings
- En `/facturas`, "sin cliente" va en rojo con el texto de la planilla debajo. En `/fundings` va en texto normal y sin el texto de la planilla. Ver las dos capturas de escritorio.

### F6 [nit] Los colores por estado están escritos dos veces
- `STATE_COLORS` en `app/craftech_os/web/app.py:47` repite, invertido, el diccionario `STATES` de `app/craftech_os/interpret/pagos.py:22`, que relaciona cada color con su estado según la regla R29.
- Hoy coinciden. Si la regla cambia, hay que acordarse de tocar los dos lugares. Son dos copias, así que según las reglas de simplicidad todavía no corresponde extraerlo; lo dejo anotado.

## Re-verificación de la ronda anterior

No aplica: es la primera ronda.

## No verificado

- **Criterio 2, al abrir el enlace:** abrir el enlace en Google Sheets y ver que se selecciona la celda requiere iniciar sesión con la cuenta de Craftech. Queda como prueba manual de Ariel: abrir `/facturas`, hacer clic en cualquier celda de la columna Origen y comprobar que Google Sheets abre esa planilla, en esa pestaña y con esa celda seleccionada. El enlace generado, el identificador de pestaña y la celda sí se verificaron contra la base.

## Split-outs sugeridos (fuera del alcance)

- [ui] A 375 px todas las pantallas de la web desbordan horizontalmente y el fondo del menú queda cortado (F4). Es así desde antes de este ticket. Solo hace falta si alguna vez se quiere usar la web en el celular.
