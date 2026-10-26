---
id: T-021
title: Pantalla /caja con tabla, indicadores y gráfico (solo lectura)
status: todo
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
- El mes en curso y los meses proyectados van tintados; las celdas fijadas a mano en el Resumen (sin fórmula), rayadas; los negativos, en rojo.
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
   - Clases por origen: mes en curso y proyectado tintados, celda fijada a mano rayada, negativo en rojo. Una leyenda explica cada marca.
   - Cada celda deja ver su origen (`recalculada`, `importada`, `parametro`) y la celda del Resumen de donde viene, sin JavaScript (por ejemplo con `title`).
3. **Gráfico SVG.** El saldo final por mes, armado en el servidor dentro de la plantilla. Sin `<script>`, sin estilos en línea que pidan cambiar la CSP y sin librerías externas.
4. **Restricciones.** Solo lectura: ninguna ruta POST. Sin parámetros en la primera versión. Ningún nombre ni monto en los logs del servidor web.

**Descartado:**
- Una librería de gráficos en el navegador: obligaría a cambiar la CSP.
- Mostrar movimientos individuales en esta pantalla.

## Acceptance criteria

- [ ] `GET /caja` responde 200 con datos sintéticos sembrados y "Caja" aparece en el menú.
- [ ] Los cinco indicadores aparecen con su fórmula y la leyenda "propuesto".
- [ ] La tabla muestra los bloques, filas y meses sembrados; la columna de conceptos es fija y los meses se desplazan en horizontal.
- [ ] El mes en curso y los proyectados llevan su clase de tinte, una celda importada sin fórmula lleva la clase de rayado y un valor negativo la clase roja (test sobre el HTML).
- [ ] El gráfico es un `<svg>` en la respuesta, la página no tiene ningún `<script>` y el encabezado de CSP es el mismo que en las demás pantallas.
- [ ] Sin migraciones nuevas y sin rutas POST nuevas.
- [ ] Los tests usan solo datos sintéticos.

## Out of scope

- La paridad en pantalla (la vista es de T-020; mostrarla puede ser otro ticket).
- Selector de año, escenarios y detalle de movimientos.
