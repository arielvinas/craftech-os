---
id: T-017
title: Tablero de inicio de ingresos en la web (solo lectura)
status: in-progress
priority: medium
lane: ui
depends_on: []
effort: M
milestone: B
branch: arielvinas/t-017-tablero-ingresos
---

## Context

Ariel quiere ver los datos en vivo en un tablero al abrir la web, sin entrar pantalla por pantalla. La app propia es solo visualización: el chat y la IA van por Claude Desktop (reglas del repo).

Decisiones de Ariel del 24-oct-2026 (pedido con `/ticket`):
- **Facturado:** todo lo que está en Pagos, en cualquier estado, incluido "a facturar".
- **Moneda:** todo se muestra en USD, sin regla nueva: los montos en USD tal cual; las facturas en ARS por el monto en USD escrito en la fórmula de la planilla (`usd_inferido`), y los cobros heredan el de su factura. Lo que está en ARS sin ese monto no se convierte: se cuenta aparte.
- **Rango y lugar:** el año en curso (enero a diciembre), en `GET /`, que hoy redirige a `/cambios`.
- **Fundings aparte:** "aparte" no es una regla escrita; es la recomendación aceptada por Ariel. Significa que los fundings van en su propio bloque y nunca se suman a lo facturado (regla R15 de `docs/v0.9.md`: un funding no es una factura y no se suma con las facturas), y que se muestran las dos paridades: contra "Pagos confirmados" y contra la fila "TOTAL PAGOS AWS".

Verificado en el repo el 24-oct-2026:
- `app/craftech_os/web/app.py`: `GET /` es un `RedirectResponse("/cambios", status_code=303)`. Las demás rutas son `/cambios`, `/problemas`, `/fuentes`, `POST /fuentes/{id}/leer-ahora`, `/facturas`, `/fundings` y `/clientes`, con un middleware de política de seguridad de contenido (CSP).
- `app/craftech_os/web/queries.py` ya lee `mcp.paridad_fundings` (en `funding_parity`), `v_issue` (en `issues`) y el estado de las fuentes (en `source_rows`). **`mcp.paridad_fundings_aws` no se usa en ningún lugar de la web** (búsqueda de `paridad_fundings_aws` en `web/`).
- Vistas que ya existen y alcanzan, sin migraciones:
  - `mcp.devengados`: mes y `monto_usd` por cliente y unidad de negocio.
  - `mcp.facturas`: mes, estado, `monto`, `moneda` y `usd_inferido`.
  - `mcp.cobros`: se arma uniendo los pagos con su factura, así que cada cobro puede llevar el `usd_inferido` de su factura. Su `mes` es el **mes de la factura**, no el mes en que entró el dinero.
  - `mcp.fundings`: mes, `monto_usd` y estado.
  - `mcp.paridad_fundings` (por planilla, unidad de negocio y mes) y `mcp.paridad_fundings_aws` (por planilla, pestaña y mes), las dos con `total_planilla`, `suma_fundings` y `diferencia`.
  - `mcp.sources`: `leido_en`, `pestañas_activas`, `lectura_pedida_en`, `ultimo_error_en` y `ultimo_error`.
- `usd_inferido` existe solo para las facturas de la planilla de Pagos de Argentina. En la base local, la mayoría de las facturas en ARS lo tienen y un puñado no.
- El patrón a seguir es `plan/tickets/T-014-pantallas-ingresos.md`, y los tests de la web siembran datos sintéticos con `_seed_ingresos` en `app/tests/test_web.py`.

## Scope

**Dónde vive:**
- `web/app.py`: `GET /` deja de redirigir y muestra el tablero.
- `web/queries.py`: consultas nuevas, solo lectura, con parámetros ligados.
- una plantilla nueva `inicio.html` que sigue a `facturas.html` y `fundings.html`, más el enlace "Inicio" en el menú de `base.html`.
- `app/tests/test_web.py`.

1. **Ingresos por mes, en USD, del año en curso.** Una tabla con una fila por mes, de enero a diciembre, y una fila de total:
   - **Devengado:** suma de `mcp.devengados.monto_usd`.
   - **Facturado:** suma de todas las facturas de `mcp.facturas`, en cualquier estado. Las de USD por su monto; las de ARS por `usd_inferido`.
   - **Cobrado:** suma de `mcp.cobros` con el mismo criterio de moneda. La columna se titula de forma que quede claro que es **por mes de la factura**, no por mes en que entró el dinero.
   - **Sin convertir:** por mes, cuántas facturas y cuántos cobros en ARS no tienen `usd_inferido` y por eso no entran en las sumas. Cuando el número no es 0, enlaza a `/facturas?mes=<ese mes>`.
   - Cada mes enlaza a `/facturas?mes=<ese mes>`.
2. **Fundings, en un bloque aparte.** Nunca se suman con lo facturado ni aparecen en la misma tabla (regla R15).
   - Por mes, la suma de `mcp.fundings.monto_usd`.
   - La paridad contra "Pagos confirmados" (`mcp.paridad_fundings`) y la paridad contra la fila "TOTAL PAGOS AWS" (`mcp.paridad_fundings_aws`), cada una en su propia tabla, con la diferencia resaltada con la clase `parity-off` cuando no es 0, igual que en `/fundings`.
   - El bloque enlaza a `/fundings`.
3. **Problemas abiertos.** La cantidad de problemas abiertos o reabiertos por tipo, cada tipo enlazado a `/problemas?tipo=<tipo>`. El filtro de estado de `/problemas` acepta un solo valor (`abierto`, `resuelto`, `ignorado` o `reabierto`, en `ISSUE_STATES` de `web/app.py`), así que el enlace no fija el estado.
4. **Última lectura de cada planilla.** Por planilla: cuándo se leyó por última vez (`leido_en`), si tiene una lectura pedida pendiente y su último error con la fecha, si lo hay. Enlaza a `/fuentes`.
5. **Restricciones.**
   - Solo lectura: ningún formulario ni ruta POST nueva. El botón "Leer ahora" sigue viviendo solo en `/fuentes`.
   - Autoescape, y ningún nombre ni monto en los logs del servidor web.
   - El tablero no recibe parámetros: el año es siempre el año en curso. Si en el futuro se agrega un selector de año, se valida contra una lista cerrada como los filtros de T-014.
   - Las consultas leen las vistas `mcp.*` (y `v_issue` para los problemas) con el rol de la app, siguiendo el patrón de `queries.py`.
6. **Tests** con datos sintéticos: las sumas por mes, la conversión con `usd_inferido`, el conteo de lo no convertido, que los fundings no se suman a lo facturado, las dos paridades resaltadas, y que no haya formularios ni rutas POST nuevas.

**Descartado:**
- **Gráficos:** el tablero es solo tablas, como el resto de la web. Son pocas piezas.
- **Convertir ARS por una cotización** (la de la factura o una del día): sería interpretar una regla financiera que Emi y Ro no ratificaron. Se usa solo el monto en USD que la planilla ya escribe, y lo demás se cuenta aparte.
- **Cobrado por mes en que entró el dinero:** ese corte espera la ratificación de Ro. Hoy `mcp.cobros.mes` es el mes de la factura y así se rotula.
- **Sumar fundings con facturado** en un "total de ingresos": lo prohíbe la regla R15.

## Acceptance criteria

- [ ] Abrir `/` muestra el tablero (código 200), sin redirigir a `/cambios`. El menú tiene un enlace "Inicio".
- [ ] Con datos sintéticos de un mes que tiene una factura en USD y una factura en ARS con `usd_inferido`, el facturado del mes es la suma del monto en USD más el `usd_inferido`, y la factura en ARS no suma su monto en pesos.
- [ ] Una factura en ARS sin `usd_inferido` no entra en el facturado de su mes y aparece contada en "sin convertir", con enlace a `/facturas?mes=<ese mes>`.
- [ ] El cobro de una factura en ARS con `usd_inferido` suma ese monto en USD en el cobrado del mes de la factura, y el encabezado de la columna dice que el corte es por mes de la factura.
- [ ] Se ven los doce meses del año en curso, incluidos los meses sin datos (en 0 o vacíos), y una fila de total.
- [ ] Un funding del mismo mes que una factura no cambia el facturado de ese mes: aparece solo en el bloque de fundings.
- [ ] Una diferencia distinta de 0 en la paridad con "Pagos confirmados" y otra en la paridad con "TOTAL PAGOS AWS" se ven resaltadas, cada una en su tabla. Captura de pantalla con datos de prueba.
- [ ] Los problemas abiertos se cuentan por tipo y cada tipo enlaza a `/problemas` filtrado; un problema resuelto no se cuenta.
- [ ] Cada planilla muestra su última lectura, y una planilla con un error registrado muestra el error y su fecha.
- [ ] No hay ningún formulario en `/` ni ninguna ruta POST nueva en la app.
- [ ] Después de abrir `/`, el log del servidor web no tiene nombres de clientes ni montos.

## Out of scope

- Gráficos, exportar a CSV o un selector de año o de rango.
- Convertir ARS a USD por cotización, o cualquier regla financiera nueva.
- Cobrado por mes de ingreso del dinero.
- Pantallas de cashflow, gastos o resultados (etapas C y D).
- Migraciones o vistas nuevas en el esquema `mcp`.
- Cualquier escritura desde la web, login o exponer la web fuera de 127.0.0.1.
