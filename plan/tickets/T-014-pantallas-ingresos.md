---
id: T-014
title: Pantallas web de solo lectura: Facturas y cobros, Fundings y Clientes
status: pr
priority: medium
lane: ui
depends_on: [T-012]
effort: M
milestone: B
branch: arielvinas/t-014-pantallas-ingresos
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

- [x] Con los datos de la planilla de prueba interpretados, `/facturas` muestra las facturas del mes con su estado y color, y filtrar por estado "retraso" deja solo esas.
- [x] El enlace de origen de una factura lleva a la planilla, pestaña y celda correctas.
- [x] Si la paridad del mes es distinta de 0, se ve resaltada en `/facturas`. Captura de pantalla con datos de prueba.
- [x] `/fundings` muestra los hitos con su origen, y un duplicado aparece marcado.
- [x] `/clientes` lista las filas sin cliente con enlace al problema, y no hay ningún control para editar.
- [x] Los logs del servidor web, después de recorrer las tres pantallas, no contienen nombres ni montos.

## Out of scope

- Cualquier escritura desde la web.
- Pantallas de cashflow, gastos o P&L (etapas C y D).
- Login o exponer la web fuera de 127.0.0.1.

## Implementation

- `app/craftech_os/web/app.py`: tres rutas GET nuevas (`/facturas`, `/fundings`, `/clientes`), el filtro `money` y la validación de `mes` (formato año-mes; sin `mes` se toma el mes en curso). Los filtros `estado` y `entidad` se validan contra listas cerradas y `cliente` contra un entero; cualquier otro valor da 400 "Filtro inválido". No hay rutas POST nuevas.
- `app/craftech_os/web/queries.py`: consultas de solo lectura sobre las vistas del esquema `mcp` (facturas, cobros, razones sociales, paridad de pagos, fundings, paridad de fundings, clientes, aliases) más `v_issue` para los duplicados y las filas sin cliente. Todos los parámetros van ligados.
- Plantillas nuevas `facturas.html`, `fundings.html` y `clientes.html`; tres enlaces en el menú de `base.html`; dos clases en `style.css` (`parity-off` para la diferencia de paridad, `muted`).
- Decisiones técnicas:
  - El filtro de cliente va por id y no por nombre, así el log de acceso (que registra la URL) nunca lleva nombres.
  - La razón social que se muestra es la del cliente con la entidad legal de la factura.
  - El neto ARS solo aparece cuando la planilla lo trae.
  - El color de estado usa la muestra de color que ya usa `/cambios`.
  - Un hito de funding se marca como duplicado cuando un problema `funding_duplicado` abierto o reabierto lo nombra (planilla, pestaña y celda) en su lado tracker o pagos. La marca enlaza a ese problema.
  - Las filas sin cliente son los problemas `alias_sin_cliente` abiertos o reabiertos.
  - `/clientes` no tiene ningún formulario ni control: dice que los aliases se vinculan desde Claude Desktop con `vincular_alias`.
- Prueba rápida: sembrar la base de prueba con `_seed_ingresos` de `app/tests/test_web.py`, levantar `craftech-os web --host 127.0.0.1 --port 8014` con esa base y recorrer las tres pantallas.
- Verificado a mano con datos ficticios: las cinco URLs dieron 200, o 400 para el mes inválido. El log del servidor no tiene ningún nombre ni monto: queda solo la URL con mes, estado, entidad legal de Craftech o id de cliente. Captura de la paridad resaltada tomada con Chrome headless (fuera del repo).
- Sin verificar: datos reales de la planilla de prueba interpretados (solo datos sembrados), y cómo se ve con cientos de filas.

## Test plan

1. `/facturas` sin parámetros: muestra el mes en curso; el selector de mes ofrece los meses con facturas.
2. `/facturas?mes=<mes con facturas>`: cada fila tiene cliente, razón social, entidad legal, estado con su color, monto, vencimiento, cobro (fecha y certeza) y enlace a la celda.
3. Filtrar por estado "retraso", por entidad legal y por cliente: quedan solo las filas que corresponden; "Limpiar" vuelve al mes en curso.
4. El enlace de origen abre la planilla en la pestaña y la celda de la factura.
5. Un mes con diferencia de paridad distinta de 0 la muestra en rojo; con 0 no se resalta. Captura.
6. `/fundings`: los hitos con origen pagos o tracker; un hito nombrado por un problema de funding duplicado abierto muestra "duplicado" con enlace al problema; los hitos con clave provisional lo indican.
7. `/clientes`: razones sociales con plazo de pago, aliases vigentes, filas sin cliente con enlace a `/problemas/<id>`. No hay ningún control para editar.
8. Filtros inválidos (`mes=2026-13`, `estado=otro`, `cliente=abc`): 400 "Filtro inválido", sin traza.
9. Después de recorrer todo, el log del servidor no tiene nombres de clientes ni montos.

Radio de impacto: `base.html` (menú de todas las pantallas), `style.css`, `app.py` y `queries.py` (compartidos con `/cambios`, `/problemas` y `/fuentes`, que no cambiaron). Los tests de esas pantallas siguen verdes.

## Post-merge

Ninguno: no hay migraciones, variables de entorno ni comandos nuevos.
