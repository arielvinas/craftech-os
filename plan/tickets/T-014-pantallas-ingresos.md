---
id: T-014
title: Pantallas web de solo lectura: Facturas y cobros, Fundings y Clientes
status: backlog
priority: medium
lane: ui
depends_on: [T-012]
effort: M
milestone: B
---

## Context

ADR-002, sección 9 y seguridad ("Web"). La app propia es solo visualización: el chat y la IA van por Claude Desktop (reglas del repo).

Decisiones de Ariel del 19-oct-2026: ADR-002 aprobado.

Verificado en el repo el 19-oct-2026:
- `app/craftech_os/web/app.py` tiene las rutas `/cambios`, `/cambios/{id}`, `/problemas`, `/problemas/{id}`, `/fuentes` y `POST /fuentes/{id}/leer-ahora`, con un middleware de CSP.
- Las consultas viven en `web/queries.py` y las plantillas en `web/templates/`. Los tests están en `app/tests/test_web.py`.
- Las vistas `mcp.*` de ingresos las crean T-009 a T-012.

## Scope

**Dónde vive:**
- `web/app.py`
- `web/queries.py`
- plantillas nuevas que siguen las de `/cambios` y `/problemas`
- `test_web.py`

1. **`/facturas`.** Facturas por mes con cliente, razón social, entidad legal, estado (con el color de la planilla), monto, neto, vencimiento y cobro con su fecha y certeza.
   - Filtros por mes, estado, entidad legal y cliente.
   - Cada fila enlaza a su celda de origen (planilla, pestaña y celda).
   - Arriba, la paridad del mes con la planilla, con la diferencia resaltada si no es 0.
2. **`/fundings`.** Hitos con origen, programa, oportunidad, estado, monto, sign-off y cobro estimados, más la paridad con "Pagos confirmados".
   - Los duplicados y las claves provisionales se marcan.
3. **`/clientes`.** Clientes con sus razones sociales y plazos de pago, y los aliases vigentes.
   - Una sección "Filas sin cliente" con los problemas `alias_sin_cliente` abiertos, cada uno con enlace a `/problemas/{id}`.
   - No se pueden editar desde la web: se resuelven con `vincular_alias` en Claude Desktop.
4. **Navegación.** Las tres pantallas se suman al menú existente.
5. **Restricciones.** Solo lectura, autoescape y ningún nombre ni monto en los logs del servidor web. Las consultas leen las vistas `mcp.*` o las mismas tablas con el rol de la app, siguiendo el patrón de `queries.py`.
6. **Tests:** cada pantalla con datos sintéticos, los filtros, la paridad resaltada, y que no haya ningún formulario ni POST nuevo.

**Descartado:** gráficos, exportar a CSV o editar aliases desde la web. Son pocas piezas, y la edición vive en Claude Desktop.

## Acceptance criteria

- [ ] Con los datos de la planilla de prueba interpretados, `/facturas` muestra las facturas del mes con su estado y color, y filtrar por estado "retraso" deja solo esas.
- [ ] El enlace de origen de una factura lleva a la planilla, pestaña y celda correctas.
- [ ] Si la paridad del mes es distinta de 0, se ve resaltada en `/facturas`. Captura de pantalla con datos de prueba.
- [ ] `/fundings` muestra los hitos con su origen, y un duplicado aparece marcado.
- [ ] `/clientes` lista las filas sin cliente con enlace al problema, y no hay ningún control para editar.
- [ ] Los logs del servidor web, después de recorrer las tres pantallas, no contienen nombres ni montos.

## Out of scope

- Cualquier escritura desde la web.
- Pantallas de cashflow, gastos o P&L (etapas C y D).
- Login o exponer la web fuera de 127.0.0.1.
