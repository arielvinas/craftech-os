---
id: T-021
title: Pantalla /caja con tabla, indicadores y gráfico (solo lectura)
status: in-progress
priority: high
lane: ui
depends_on: [T-019]
effort: M
milestone: C
branch: arielvinas/t-021-pantalla-caja
---

## Context

Cuarto ticket de la caja (`plan/adr/ADR-003-caja-desde-movimientos.md`, aprobado por Ariel el 25-oct-2026). Muestra en la web el cashflow mensual de T-019 con el origen de cada número a la vista. La app propia es solo visualización (reglas del repo).

Decisiones del documento de arquitectura (ADR-003):
- Tabla con la columna de conceptos fija y los meses desplazándose en horizontal.
- El mes en curso y los meses proyectados van tintados; los negativos, en rojo. (Las celdas fijadas a mano ya no se rayan: ver `## Decisions`.)
- Indicadores arriba, cada uno con su fórmula al lado del número y la marca de que está propuesto, no ratificado.
- Gráfico en SVG armado en el servidor: sin JavaScript y sin cambiar la política de seguridad de contenido (CSP).
- El diseño de referencia no aporta números: todos salen de la base.

Verificado en el repo el 25-oct-2026:
- `app/craftech_os/web/app.py` es FastAPI con plantillas Jinja con autoescape, un middleware de CSP y escucha solo en 127.0.0.1. Las consultas viven en `web/queries.py`, solo lectura y con parámetros ligados.
- El menú de `base.html` tiene Inicio, Cambios, Problemas, Fuentes, Facturas, Fundings y Clientes.
- Los tests de la web siembran datos sintéticos con funciones `_seed_*` en `app/tests/test_web.py`.
- Las vistas que usa la pantalla (`mcp.caja_mensual` y `mcp.indicadores_de_caja`) las crea T-019; este ticket no agrega migraciones.

## Scope

**Dónde vive:**
- `web/app.py`: `GET /caja`.
- `web/queries.py`: consultas nuevas, solo lectura.
- plantilla nueva `caja.html` y el enlace "Caja" en el menú de `base.html`.
- el CSS existente (sin hojas externas).
- `app/tests/test_web.py`.

1. **Indicadores.** Caja hoy, salida mensual, meses de cobertura y los dos cierres de marzo-27 (con y sin pagos proyectados), cada uno con su fórmula en texto y la leyenda "propuesto".
2. **Tabla.** Un bloque por cada bloque del Resumen, filas por concepto y columnas por mes, en la unidad de la fila.
   - Columna de conceptos fija (`position: sticky`) y desplazamiento horizontal de los meses.
   - Clases: mes en curso y proyectado tintados, negativo en rojo, celda sin valor (`sin_regla` o `parametro`) marcada. Una leyenda explica cada marca.
   - Cada celda deja ver su origen (`recalculada`, `sin_regla`, `parametro`), su motivo si no tiene valor y la celda equivalente del Resumen, sin JavaScript (por ejemplo con `title`).
3. **Gráfico SVG.** El saldo final por mes, armado en el servidor dentro de la plantilla. Sin `<script>`, sin estilos en línea que pidan cambiar la CSP y sin librerías externas.
4. **Restricciones.** Solo lectura: ninguna ruta POST. Sin parámetros en la primera versión. Ningún nombre ni monto en los logs del servidor web.

**Descartado:**
- Una librería de gráficos en el navegador: obligaría a cambiar la CSP.
- Mostrar movimientos individuales en esta pantalla.

## Acceptance criteria

- [x] `GET /caja` responde 200 con datos sintéticos sembrados y "Caja" aparece en el menú.
- [x] Los cinco indicadores aparecen con su fórmula y la leyenda "propuesto".
- [x] La tabla muestra los bloques, filas y meses sembrados; la columna de conceptos es fija y los meses se desplazan en horizontal.
- [x] El mes en curso y los proyectados llevan su clase de tinte, una celda sin valor lleva su clase y su motivo, y un valor negativo la clase roja (test sobre el HTML). Ningún valor del Resumen aparece en la pantalla.
- [x] El gráfico es un `<svg>` en la respuesta, la página no tiene ningún `<script>` y el encabezado de CSP es el mismo que en las demás pantallas.
- [x] Sin migraciones nuevas y sin rutas POST nuevas.
- [x] Los tests usan solo datos sintéticos.

## Out of scope

- La paridad en pantalla (la vista es de T-020; mostrarla puede ser otro ticket).
- Selector de año, escenarios y detalle de movimientos.

## Decisions

- 2026-10-26 — **El ticket supone celdas con origen importada (valores tomados del Resumen); ¿siguen existiendo?** → No. Decisión de Ariel en T-019 (26-oct-2026): todo valor se calcula desde los movimientos y nunca se muestra un valor del Resumen, tenga o no fórmula. Seguir la nota agregada a plan/adr/ADR-003-caja-desde-movimientos.md: orígenes recalculada, sin_regla o parametro; las celdas sin regla quedan sin valor y con motivo, sin rayado; la planilla es solo referencia de paridad (recalculada contra cashflow_sheet_cell). Actualizar el ticket en consecuencia.

## Implementation

- `app/craftech_os/web/queries.py`: `cashflow_cells` lee `mcp.caja_mensual` en el orden del Resumen (bloque, fila, mes); `cashflow_indicators` lee `mcp.indicadores_de_caja` por `orden`. Sin parámetros.
- `app/craftech_os/web/app.py`: ruta `GET /caja`. Agrupa las celdas por bloque → fila → mes y arma la lista de meses con su período (real, en_curso, proyectado). `_chart` calcula en el servidor las barras del gráfico, escaladas entre el mínimo y el máximo, alrededor de una línea de cero.
- `app/craftech_os/web/templates/caja.html`: indicadores como `<dl>` con nombre, valor (USD con dos decimales, cobertura en meses con un decimal, "—" si falta), fórmula y "propuesto" cuando la vista lo marca. Después vienen la leyenda (`id="leyenda"`) y la tabla dentro de `div.caja-scroll`, con un `<tbody>` por bloque y una fila de encabezado que lleva el nombre del bloque, su unidad y los meses. Cada celda tiene un `id="celda-<bloque>-<fila>-<AAAA-MM>"` y las clases `periodo-<período>` más `negativo` o `sin-valor`. Su `title` dice "origen: X — motivo · planilla / pestaña!celda". Al final va el gráfico `<svg>`, con un `<title>` por barra que muestra el mes y el valor, y el estado vacío: "Todavía no hay cashflow: falta una lectura del Resumen."
- `app/craftech_os/web/static/style.css`: clases nuevas para la columna de conceptos fija (`position: sticky`), el scroll horizontal, los tintes del mes en curso y los proyectados, el rojo de los negativos, la celda sin valor (gris en itálica, para que no tape el tinte del mes) y las barras, en azul o en rojo si son negativas.
- `app/craftech_os/web/templates/base.html`: enlace "Caja" en el menú.
- Decisiones propias:
  - El gráfico muestra el **Saldo Final de "Craftech Inc. en dólares"**, el mismo bloque que usan los indicadores. Solo incluye los meses que tienen valor; los proyectados sin regla no se dibujan.
  - No hay JavaScript ni estilos en línea: el SVG usa atributos de presentación y clases CSS, y la política de seguridad de contenido (CSP) no cambia.
- Cómo probar rápido: `uv run pytest -q app/tests/test_web.py -k caja`.
- Prueba manual contra la base local, mirando solo el código de respuesta y los conteos, sin valores: 200, 1431 celdas en 5 bloques (todas dibujadas), 39 barras, 5 "propuesto", ningún `<script>` ni `style=`, y sin errores en el log.
- Sin verificar: cómo se ve en un navegador real. El ancho de la tabla con todos los meses y si la columna fija queda bien al desplazar quedan para la prueba en navegador de QA.

## Test plan

1. Abrir `/caja` sin lecturas del Resumen: aparece "Todavía no hay cashflow" y no hay gráfico.
2. Abrir `/caja` con datos: el enlace "Caja" figura en el menú y responde 200 con la misma CSP que `/cambios`.
3. Indicadores: los cinco aparecen con su fórmula y "propuesto". Si la salida mensual es cero, la cobertura muestra "—".
4. Desplazar la tabla en horizontal en un navegador angosto: la columna de conceptos queda fija y no se superpone con los valores.
5. Revisar los tintes: el mes en curso y los proyectados tienen su color, y la celda sin valor sigue mostrando el tinte de su mes.
6. Pasar el mouse sobre una celda sin regla (debe decir "fila sin regla ratificada"), sobre una de un mes proyectado ("mes proyectado") y sobre una de parámetro ("origen: parametro"). La referencia "planilla / pestaña!celda" tiene que ser la del Resumen.
7. Confirmar que un valor negativo aparece en rojo, tanto en la tabla como en la barra del gráfico.
8. Comprobar que ningún número de la pantalla viene del Resumen: con datos sintéticos, las celdas de la planilla valen 98765 y ese número no aparece.
9. Revisar el código fuente de la página: no hay `<script>`, ni `style=`, ni formularios.
10. Confirmar que el bloque en ARS muestra su unidad en el encabezado y que sus valores no se mezclan con los del gráfico.

Alcance de lo tocado:

- `base.html`, por el menú: todas las pantallas lo heredan.
- `style.css`: solo se agregaron clases nuevas. `.negativo` y `.sin-valor` no existían; `.concepto` y `.caja-scroll` tampoco.
- `test_web.py`: solo se agregaron tests.

## Post-merge

- Reconstruir y reiniciar el contenedor web para que sirva la pantalla nueva: `docker compose -f infra/docker-compose.yml up -d --build web`. Para verificarlo, abrir http://127.0.0.1:8000/caja y comprobar que responde 200.
- No hay migraciones ni variables de entorno nuevas.
