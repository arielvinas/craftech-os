# QA T-017 — Ronda 2

**Verdict: PASS**
**Branch:** arielvinas/t-017-tablero-ingresos @ df07a07
**Gates:** lint ✓ (`ruff check`) formato ✓ (`ruff format --check`, 54 archivos) tests ✓ (321 passed, 0 skipped, con `TEST_DATABASE_URL` en una base `_test` propia, borrada al terminar) · sin typecheck ni build configurados en el repo
**Criteria:** 11/11 verificados
**Mutation:** 30 mutantes (los 23 de la ronda 1 más 7 nuevos), 30 muertos, 0 vivos

## Cómo se probó

- Diff de la ronda de arreglos leído contra `84df9bf` (lo que vio la ronda 1): solo cambian `templates/inicio.html` (título de la columna y clase del error), `tests/test_web.py` (siembra y aserciones nuevas, un test nuevo) y dos líneas de `plan/improvements.md`. `queries.py`, `app.py`, `base.html` y las demás plantillas no cambiaron, así que el radio de impacto de la ronda 1 sigue valiendo y `/fuentes` no se tocó.
- Base real local, solo lectura, con el rol de la app y `craftech-os web` en un puerto aparte: `/` responde 200 en unos 0,5 s, doce meses, 10 celdas `parity-off`, ningún `<form>`, `<input>` ni `<button>`. En la tabla de planillas hay 20 filas: 11 errores en gris y 9 en rojo. Una consulta SQL independiente sobre `mcp.sources` (`ultimo_error_en < leido_en`) da el mismo 11/9. Los 11 enlaces `/problemas?tipo=<tipo>` responden 200.
- Base sintética (`_seed_inicio` de la ronda de arreglos) en un segundo servidor: facturado y cobrado de marzo en 1,100.00, mayo con 400.00 de fundings, ninguna fila de paridad del año anterior, tres tipos de problemas (incluido el reabierto), la planilla A con su error viejo en gris y la B con su error vigente en rojo y "pendiente desde".
- Navegador real: Chromium (Playwright) a 1280 px y 375 px. Se llegó a `/` con un clic en "Inicio" desde `/fuentes`. Capturas, solo con datos de prueba: `plan/qa/evidence/T-017-r2-synthetic-1280.png` y `T-017-r2-synthetic-375.png`. Color calculado: el error viejo `rgb(102, 102, 102)` (gris) y el vigente `rgb(179, 38, 30)` (rojo). Sin errores de consola ni de página.
- Logs de los dos servidores: solo líneas de acceso (método, ruta, código), sin nombres ni montos.
- Los dos servidores quedaron parados y la base de prueba propia se borró.

## Re-verificación de la ronda anterior

- **F1 (r1, major): ✓ resuelto.** `test_the_problemas_filter_accepts_every_type_the_database_allows` compara `ISSUE_TYPES` con los valores del CHECK `issue_issue_type_check` de la base migrada. Lo maté con tres mutantes: sacar `fila_sin_interpretar`, sacar `cotizacion_tipeada` y agregar un tipo inventado. Los tres ponen roja la suite, y es este test el que falla. La comparación es por igualdad de conjuntos, así que cubre los once tipos, no solo los siete nuevos.
- **F2 (r1, minor): ✓ resuelto.** Los siete mutantes que sobrevivían en la ronda 1 ahora mueren, cada uno en el test que corresponde:
  - cobrado de facturas en USD en 0 (`test_inicio_sums_each_month_in_usd`);
  - paridad con "Pagos confirmados" sin filtro de año y paridad con "TOTAL PAGOS AWS" sin filtro de año (test de paridades);
  - problemas sin `reabierto` (test de problemas);
  - lectura pendiente no mostrada (test de planillas);
  - total cobrado en 0,00 (test de doce meses y total);
  - el total del año de fundings en cada mes (test de paridades, por la fila de mayo).
- **F3 (r1, minor): ✓ resuelto con el arreglo mínimo que proponía el informe.** La columna se titula "Última lectura con cambios". El error se ve en gris cuando es anterior a `leido_en` y en rojo si no. Mutantes nuevos, todos muertos en `test_inicio_shows_each_source_last_read_and_error`: todo en rojo, todo en gris, comparación invertida y el título viejo. Revisé los bordes por lectura:
  - `ultimo_error_en` no puede ser nulo cuando hay error, porque sale de `system_event.occurred_at`, que es `NOT NULL`. La comparación no puede tirar un error de tipo.
  - Sin `leido_en`, el error se ve en rojo, que es lo correcto: nunca se leyó bien.
  - Con las dos fechas iguales también se ve en rojo, del lado prudente.

  El problema de fondo quedó registrado en `plan/improvements.md` como `[observability]`.
- **F4 (r1, nit): ✓ registrado** en `plan/improvements.md` como `[ui]`, fuera del alcance como se sugirió. El código sigue usando `date.today()`.

## Criterios, uno por uno

1. `/` responde 200 sin redirigir; "Inicio" en el menú lleva a `/`. ✓
2. Facturado = USD tal cual + `usd_inferido` de las ARS, sin pesos. ✓ (test, mutante muerto, base real)
3. ARS sin `usd_inferido` fuera del facturado y en "Sin convertir" con enlace a `/facturas?mes=`. ✓
4. El cobro de la ARS con `usd_inferido` suma ese USD en el mes de la factura, y el encabezado dice "Cobrado, por mes de la factura". ✓ Ahora también hay test del cobro en USD.
5. Doce meses más total. ✓ El total compara las tres columnas exactas.
6. El funding no cambia el facturado. ✓
7. Las dos paridades resaltadas, cada una en su tabla. ✓ (captura r2; la de "TOTAL PAGOS AWS" ahora muestra también mayo, -400, por el hito nuevo de la siembra)
8. Problemas abiertos y reabiertos por tipo, con enlace; los resueltos e ignorados no cuentan. ✓
9. Última lectura y error con su fecha. ✓ Con la distinción vieja/vigente de F3.
10. Sin formularios en `/` ni rutas POST nuevas. ✓ El diff de la ronda no agrega rutas.
11. Log sin nombres ni montos. ✓

## Mutación

Harness en el scratchpad (`/tmp/t017-r2/mut.py`, derivado del de la ronda 1). Falla si falta un archivo o si un patrón no aparece exactamente una vez, y restaura el archivo después de cada mutante. Corre `app/tests/test_web.py`. Resultado: 30 de 30 en rojo, `SURVIVORS: []`, y el árbol quedó limpio.

Los siete mutantes nuevos de esta ronda: `ISSUE_TYPES` sin `cotizacion_tipeada`, `ISSUE_TYPES` con un tipo extra, error viejo en rojo, error vigente en gris, comparación invertida, encabezado viejo y cobros que solo suman ARS. La atribución está chequeada: cada mutante de F1, F2 y F3 lo mata un test agregado o ampliado en la ronda de arreglos, no uno que ya existía.

## Findings

Ninguno nuevo. Para una ronda de re-verificación es esperable. Igual hice una pasada adversarial más sobre lo que cambió (bordes de la comparación de fechas, nulos, colores calculados, coincidencia con SQL en datos reales) y no encontré nada.

## No verificado

- No hay captura con datos reales: tendría nombres de clientes y montos, que no pueden entrar a `plan/` según `plan/guidelines/code.md`.
- A 375 px las tablas desbordan de ancho, igual que en la ronda 1 y en las demás pantallas. No lo trajo este ticket y ya figura como split-out sugerido en la ronda 1.

## Split-outs sugeridos (fuera del alcance)

- Ninguno nuevo. Los de la ronda 1 (`[observability]` y `[ui]`) ya están en `plan/improvements.md`. El `[ux]` del desborde a 375 px sigue sugerido y no está registrado.
