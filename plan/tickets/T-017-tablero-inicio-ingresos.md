---
id: T-017
title: Tablero de inicio de ingresos en la web (solo lectura)
status: qa
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

- [x] Abrir `/` muestra el tablero (código 200), sin redirigir a `/cambios`. El menú tiene un enlace "Inicio".
- [x] Con datos sintéticos de un mes que tiene una factura en USD y una factura en ARS con `usd_inferido`, el facturado del mes es la suma del monto en USD más el `usd_inferido`, y la factura en ARS no suma su monto en pesos.
- [x] Una factura en ARS sin `usd_inferido` no entra en el facturado de su mes y aparece contada en "sin convertir", con enlace a `/facturas?mes=<ese mes>`.
- [x] El cobro de una factura en ARS con `usd_inferido` suma ese monto en USD en el cobrado del mes de la factura, y el encabezado de la columna dice que el corte es por mes de la factura.
- [x] Se ven los doce meses del año en curso, incluidos los meses sin datos (en 0 o vacíos), y una fila de total.
- [x] Un funding del mismo mes que una factura no cambia el facturado de ese mes: aparece solo en el bloque de fundings.
- [x] Una diferencia distinta de 0 en la paridad con "Pagos confirmados" y otra en la paridad con "TOTAL PAGOS AWS" se ven resaltadas, cada una en su tabla. Captura de pantalla con datos de prueba.
- [x] Los problemas abiertos se cuentan por tipo y cada tipo enlaza a `/problemas` filtrado; un problema resuelto no se cuenta.
- [x] Cada planilla muestra su última lectura, y una planilla con un error registrado muestra el error y su fecha.
- [x] No hay ningún formulario en `/` ni ninguna ruta POST nueva en la app.
- [x] Después de abrir `/`, el log del servidor web no tiene nombres de clientes ni montos.

## Out of scope

- Gráficos, exportar a CSV o un selector de año o de rango.
- Convertir ARS a USD por cotización, o cualquier regla financiera nueva.
- Cobrado por mes de ingreso del dinero.
- Pantallas de cashflow, gastos o resultados (etapas C y D).
- Migraciones o vistas nuevas en el esquema `mcp`.
- Cualquier escritura desde la web, login o exponer la web fuera de 127.0.0.1.

## Implementation

Archivos:
- `app/craftech_os/web/app.py`: `GET /` (función `inicio`) arma el tablero del año en curso (`date.today().year`, sin parámetros). `ISSUE_TYPES` pasa de 4 a los 11 tipos que acepta la base desde la migración 0009: sin eso, `/problemas?tipo=alias_sin_cliente` (y los otros 6 tipos nuevos) respondía 400 y los enlaces del tablero quedaban rotos.
- `app/craftech_os/web/queries.py`: `income_months`, `funding_months`, `funding_parity_of_year`, `funding_parity_aws_of_year`, `open_issue_counts`, `source_reads`. Todas de solo lectura sobre `mcp.*` y `v_issue`, con el año como parámetro ligado. Los doce meses salen de `generate_series(1, 12)`, así que los meses sin datos aparecen en 0.
- `app/craftech_os/web/templates/inicio.html` (nueva) y `base.html` (enlace "Inicio").
- `app/tests/test_web.py`: `_seed_inicio` (datos sintéticos en marzo del año en curso) y 6 tests nuevos; el test de "todas las pantallas responden 200" ahora espera 200 en `/` en lugar de la redirección.

Decisiones técnicas:
- Criterio de moneda en SQL: `CASE WHEN moneda = 'USD' THEN monto ELSE usd_inferido END`. El cobro toma el `usd_inferido` de su factura uniendo `mcp.cobros` con `mcp.facturas` por pestaña, lectura y celda (el mismo join que ya usa `invoices`).
- "Sin convertir" se muestra como "N factura(s), M cobro(s)" y enlaza a `/facturas?mes=<mes>`. Vacío cuando los dos son 0.
- La fila de total se suma en la plantilla (doce filas).
- Las paridades se filtran al año en curso; `/fundings` sigue mostrando todas.
- La fila "Pagos confirmados" y la fila "TOTAL PAGOS AWS" usan la misma macro de tabla.

Hallazgo para el producto: en `mcp.fundings` los hitos del tracker no tienen `mes` (la tabla exige mes solo para los de origen Pagos). Por eso la tabla "Fundings por mes" suma solo los hitos de Pagos, como pide el alcance ("la suma de `mcp.fundings.monto_usd` por mes"). Los del tracker se ven en las paridades. El tablero lo aclara en una nota y quedó registrado en `plan/improvements.md`.

Verificado: lint, formato y la suite completa en verde; prueba de humo con datos sintéticos (captura en `plan/qa/evidence/T-017-inicio.png`) y contra la base local real. Con la base real `/` respondió 200 en unos 0,5 s, se vieron 12 meses, 10 celdas con `parity-off` y los 11 tipos de problema enlazados respondieron 200. El log de uvicorn solo tiene líneas de acceso, sin nombres ni montos.

Cómo probar rápido: `cd app && TEST_DATABASE_URL=... uv run pytest tests/test_web.py -k inicio`.

### Ronda de arreglos 1 (`plan/qa/T-017-round-1.md`)

- F1 (major): test nuevo `test_the_problemas_filter_accepts_every_type_the_database_allows`, que compara `ISSUE_TYPES` con los valores del CHECK `issue_issue_type_check` de la base migrada. Se vio rojo al sacar `fila_sin_interpretar` antes de commitearlo.
- F2 (minor): `_seed_inicio` suma el cobro de la factura en USD, un hito de Pagos en mayo, hitos y totales de marzo del año anterior en las dos paridades, un problema `fila_sin_interpretar` resuelto ayer y visto de nuevo (reabierto), un `source_failed` actual de la planilla B y una lectura pedida pendiente. Las aserciones cubren cada uno: cobrado de marzo y total en 1,100.00, mayo con 400.00, ninguna fila de paridad del año anterior, tres tipos abiertos, un solo "pendiente desde". El código no cambió por F2: estaba bien, faltaban los tests.
- F3 (minor), arreglo mínimo que sugiere el informe, sin tocar vistas: la columna se titula "Última lectura con cambios" y el error se muestra en gris (`muted`) cuando es anterior a `leido_en`, y en rojo (`warning`) si no. El problema de fondo quedó como split-out en `plan/improvements.md`.
- F4 (nit): fuera del alcance, registrado en `plan/improvements.md` (misma clase que T-014 F2).
- Mutación: el harness de QA más un mutante para F3 (el error viejo en rojo): 24 mutantes, 24 muertos.
- Prueba de humo contra la base real local con el rol de la app, en un puerto aparte: `/` responde 200, 11 errores en gris y 9 en rojo (coincide con lo que midió QA), log sin nombres ni montos.

## Test plan

1. Abrir `/`: responde 200, sin redirección; el menú muestra "Inicio" primero.
2. Un mes con una factura en USD de 1000 y una en ARS de 121000 con `usd_inferido` 100: facturado 1,100.00; el monto en pesos no aparece en la página.
3. Una factura en ARS sin `usd_inferido`, con su cobro: no suma, y "Sin convertir" dice "1 factura, 1 cobro" con enlace a `/facturas?mes=AAAA-MM`.
4. Cobrado de la factura en ARS con `usd_inferido`: suma 100 en el mes de la factura; el encabezado dice "Cobrado, por mes de la factura".
5. Doce filas de enero a diciembre del año en curso; los meses vacíos en 0.00; la fila Total suma las columnas.
6. Un funding de Pagos de 700 en el mismo mes: el facturado no cambia; aparece solo en la tabla de fundings.
7. Paridad con "Pagos confirmados" (hito del tracker pagado sin total, -300) y con "TOTAL PAGOS AWS" (650 contra 700, -50): las dos resaltadas con `parity-off`, cada una en su tabla.
8. Problemas: un tipo abierto cuenta 1; uno resuelto y uno ignorado no aparecen; cada enlace `/problemas?tipo=<tipo>` responde 200 (incluidos los 7 tipos agregados a `ISSUE_TYPES`).
9. Planillas: la columna dice "Última lectura con cambios". La que tiene un `source_failed` anterior a su última lectura muestra fecha y error en gris; la que falló después, en rojo; una lectura pedida pendiente muestra "pendiente desde" (todo con test desde la ronda 1).
11. Cobro de una factura en USD: suma su monto en el cobrado del mes de la factura. Hitos de Pagos en marzo y mayo: cada mes muestra solo el suyo. Paridades del año anterior: no aparecen. Un problema reabierto se cuenta.
10. Sin `<form>`, `<input>` ni `<button>` en `/`; el conjunto de rutas POST sigue siendo solo `leer-ahora`; el log del servidor no tiene nombres ni montos.

Radio de impacto:
- `base.html`: todas las pantallas cambian el menú.
- `inicio.html` solo: el cambio de la ronda 1 en la tabla de planillas no toca `/fuentes`.
- `ISSUE_TYPES`: el desplegable de tipos de `/problemas` ahora lista 11 tipos y el filtro acepta los 7 nuevos.
- `GET /` ya no redirige a `/cambios`: cualquier marcador o enlace a `/` cae en el tablero.
- `queries.py` solo suma funciones; ninguna existente cambió.

## Post-merge

Ninguno: no hay migraciones, variables de entorno ni comandos nuevos. El contenedor web toma el código nuevo al reconstruir su imagen, como en cualquier ticket de la web.
