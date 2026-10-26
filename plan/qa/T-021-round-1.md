# QA T-021, ronda 1

**Veredicto: PASS.** Se cumplen los siete criterios, tanto en los tests como en un navegador real (Chromium por Playwright), con datos sintéticos de 54 meses y contra la base local, donde solo tomé mediciones. Las 22 mutaciones de la suite son rojas salvo una, que es un hueco de test menor (F5). Quedan cinco hallazgos minor y dos nit, casi todos de presentación en pantallas angostas. Ninguno rompe un criterio.

**Rama:** `arielvinas/t-021-pantalla-caja` @ `ee10bf8`.

## Gates

- `uv run ruff check`: ok.
- `uv run ruff format --check`: ok (59 archivos).
- `uv run pytest -q`: 357 pasan, ninguno salteado, contra una base de prueba propia de QA (`qa_t021_r1_test`, ya borrada). No usé la base `_t021_test` de implement ni las de T-020.
- `uv build`: ok.

## Criterios (7/7)

1. **`GET /caja` responde 200 y "Caja" está en el menú: cumple.** Responde 200 con datos sintéticos y con la base local. El enlace aparece en el menú de todas las pantallas.
2. **Cinco indicadores con su fórmula y la leyenda "propuesto": cumple.** Lo verifiqué en el navegador (`evidence/T-021-r1-desktop.png`). Cuando un indicador es nulo, el valor muestra "—" y al lado el mes que le corresponde.
3. **Bloques, filas y meses, con la columna de conceptos fija y los meses desplazándose en horizontal: cumple.**
   - Con 1440 px de ancho y 54 meses, la tabla mide 5.788 px dentro de un contenedor de 1.398 px.
   - Al desplazar 1.500 px, las nueve celdas de concepto se quedan en `left: 21px`, y en el borde derecho de cada una `elementFromPoint` devuelve la propia celda, así que no la tapan los valores (`evidence/T-021-r1-desktop-scrolled.png`).
   - Contra la base local: 1.431 celdas en 5 bloques y 53 meses, todas dibujadas; la tabla mide 5.592 px.
   - Ver F1 y F3 para lo que pasa en anchos chicos.
4. **Tintes, celda sin valor, negativos y ningún valor del Resumen: cumple.**
   - El mes en curso va en amarillo y los proyectados en azul. Las celdas sin valor muestran "—" en gris sin perder el tinte de su mes (`evidence/T-021-r1-768-mes-en-curso.png`, `evidence/T-021-r1-desktop-fin-proyectados.png`).
   - Los negativos se ven en rojo, en la tabla y en las barras (`evidence/T-021-r1-desktop-inicio-negativos.png`, `evidence/T-021-r1-desktop-grafico-negativos.png`).
   - El `title` de cada celda es correcto para los tres orígenes:
     - `origen: sin_regla — mes proyectado: sin regla de proyección ratificada`;
     - `origen: sin_regla — fila sin regla ratificada para calcularla desde los movimientos`;
     - `origen: parametro — <texto del parámetro>`.

     Además, cada uno lleva la referencia `planilla / pestaña!celda` del Resumen.
   - El valor 98765 de la planilla no aparece en ningún lado del HTML.
5. **SVG del servidor, sin `<script>` y con la misma CSP: cumple.**
   - El encabezado CSP de `/caja` es `default-src 'self'`, idéntico al de `/cambios`.
   - En el HTML no hay `<script>` ni `style=`.
   - En el navegador hay cero errores de consola en `/caja`. El único 404 es `/favicon.ico`, que ya pasaba antes y en todas las pantallas.
6. **Sin migraciones nuevas ni rutas POST nuevas: cumple.**
   - El diff no toca `migrations/`.
   - `POST /caja` responde 405, `/caja?anio=2027` y `/caja?x=<script>` responden 200 sin efecto, y un `Host` ajeno responde 400.
   - El log del servidor contra la base local tiene solo líneas de acceso, sin nombres ni montos.
7. **Tests con datos sintéticos solamente: cumple.** Los tests y la evidencia usan "Planilla Ficticia C" y montos inventados. Contra la base local tomé solo conteos y anchos, sin capturas.

## Mutación

Usé un arnés descartable (`/tmp/qa-t021/mut.py`) que aplica cada mutación, corre `pytest app/tests/test_web.py -k caja` y restaura el archivo. Si no encuentra el texto exacto, falla.

- **22 mutantes, 21 muertos**, todos por los tests nuevos de `-k caja`. Entre ellos:
  - quitar el enlace del menú, `position: sticky` u `overflow-x: auto`;
  - quitar las clases `negativo`, `sin-valor` o `periodo-*`;
  - sacar del `title` el origen, el motivo o la celda;
  - quitar "propuesto" o la fórmula;
  - dibujar las barras negativas hacia arriba, correr la línea de cero o graficar el bloque en pesos;
  - invertir el orden de los bloques o quitar el estado vacío;
  - agregar un `<script>`, un `style=` o un `<form>`;
  - loguear las celdas.
- **Sobrevivió uno:** `{% if chart %}` → `{% if true %}` (F5).

## Findings

### F1 [minor] En 375 px, la columna fija de conceptos ocupa casi todo el ancho y los meses no se ven

- **Repro:** abrir `/caja` con 375 px de ancho, con la base local, y desplazar la tabla.
- **Expected:** la columna fija deja ver al menos un par de meses.
- **Actual:**
  - Con la base local, la etiqueta más larga tiene 40 caracteres. Como la columna va sin cortes de línea (`white-space: nowrap`), mide 314 px de los 333 px del contenedor: quedan unos 19 px para los meses.
  - Con datos sintéticos y una etiqueta más larga, la columna ocupa todo el ancho (`evidence/T-021-r1-mobile-scrolled.png`).
  - En 768 px y en escritorio se ve bien.
- **Por qué es minor:** la web escucha solo en 127.0.0.1 y se usa desde la computadora. Arreglo sugerido: un `max-width` en `.concepto` y permitir el corte de línea en esa columna.

### F2 [minor] El gráfico tiene un ancho fijo y desborda la página en pantallas angostas

- **Repro:** abrir `/caja` con 375 px de ancho.
- **Actual:**
  - El `<svg>` mide 936 px con la base local (24 px por cada una de las 39 barras), y la página entera se desplaza en horizontal: el documento mide 957 px.
  - El fondo del menú se corta a los 375 px (`evidence/T-021-r1-mobile.png`).
- **Arreglo sugerido:** el SVG ya tiene `viewBox`, así que alcanza con agregar `svg.grafico { max-width: 100%; height: auto; }` en el CSS, sin tocar la política de seguridad de contenido.

### F3 [minor] Al desplazar la tabla se ven restos de texto a la izquierda de la columna fija

- **Repro:** desplazar la tabla en horizontal, en cualquier ancho.
- **Actual:** en los primeros píxeles a la izquierda de la columna de conceptos se ven pedazos de los valores que pasan por debajo (por ejemplo "S", "2", "G", "00"). Se nota en el borde izquierdo de `evidence/T-021-r1-768-mes-en-curso.png` y de `evidence/T-021-r1-desktop-scrolled.png`.
- **Causa probable:** la tabla usa `border-collapse: collapse` y los bordes compartidos no se quedan fijos junto con la celda. Es un defecto visual sin pérdida de información.

### F4 [minor] El eje del gráfico muestra solo el número de mes sobre más de tres años

- **Actual:** con la base local hay 39 barras, rotuladas "06 07 … 12 01 …", y no se ve en qué año empieza o termina cada tramo. El valor y el mes con año aparecen solo al pasar el mouse sobre la barra (`<title>`).
- **Sugerencia:** mostrar el año en enero, o en la primera y la última barra.

### F5 [minor] Ningún test cubre el caso de una tabla con datos pero sin gráfico

- **Mutante sobreviviente:** cambiar `{% if chart %}` por `{% if true %}` deja la suite verde. Pasa porque el único test sin gráfico es el del estado vacío, donde ese bloque ni se evalúa.
- **Verificado a mano:** borré la fila "Saldo Final" de Craftech Inc. de una base sintética. `/caja` respondió 200 con 324 celdas y sin `<svg>`, así que el código actual funciona; lo que falta es el test.

### F6 [nit] La barra del mes en curso se dibuja igual que la de los meses cerrados

El mes en curso está incompleto, pero su barra se ve igual que las demás. En cambio, en la tabla va tintado, y "Caja hoy" toma el último mes cerrado. Podría llevar la clase de tinte o una opacidad menor.

### F7 [nit] Los `id` de las celdas tienen espacios

Por ejemplo, `id="celda-Craftech Inc. en dólares-Saldo Final-2026-10"`. HTML5 no admite espacios en un `id`. Hoy solo lo usan los tests, así que no rompe nada.

## Re-verificación de la ronda anterior

No aplica: es la primera ronda.

## No verificado

- Safari y Firefox: probé solo en Chromium. `position: sticky` en celdas de tabla anda en los tres, pero no lo comprobé en los otros dos.
- No miré contra la base local la apariencia de valores reales (no hice capturas, por la guía de no guardar montos). Los conteos coinciden con los de implement: 1.431 celdas, 39 barras, 5 "propuesto", 14 negativos en la tabla y ninguna barra negativa.

## Split-outs sugeridos (fuera del alcance)

- [nit] `/favicon.ico` responde 404 en todas las pantallas y deja un error en la consola del navegador. Ya pasaba antes de T-021.
