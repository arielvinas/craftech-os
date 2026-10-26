# Guías de código

- Los informes de QA y la sección `## Implementation` de los tickets citan celdas (planilla, pestaña, celda) y cantidades, nunca nombres de clientes ni montos reales. Origen: T-012, la revisión encontró nombres y montos reales en `plan/` (20-oct-2026).
- Toda pantalla nueva se revisa a 375 px de ancho; las tablas y los gráficos anchos se desplazan dentro de su propio contenedor, nunca la página entera. Origen: T-021, tres hallazgos de pantalla angosta en el mismo ticket (26-oct-2026).
