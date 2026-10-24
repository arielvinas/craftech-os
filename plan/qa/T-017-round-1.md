# QA T-017 — Ronda 1

**Verdict: FAIL**
**Branch:** arielvinas/t-017-tablero-ingresos @ 84df9bf
**Gates:** lint ✓ (`ruff check`) formato ✓ (`ruff format --check`, 54 archivos) tests ✓ (320 passed, 0 skipped, con `TEST_DATABASE_URL` en una base `_test` propia) · sin typecheck ni build configurados en el repo
**Criteria:** 11/11 verificados (el comportamiento es correcto; el FAIL es por un hueco de tests en un registro, F1)
**Mutation:** 23 mutantes, 15 muertos, 8 vivos (detalle abajo)

## Cómo se probó

- Diff completo leído contra `main` (`web/app.py`, `web/queries.py`, `templates/inicio.html`, `templates/base.html`, `tests/test_web.py`, la línea nueva de `plan/improvements.md`).
- Base real local, solo lectura, con el rol de la app: `craftech-os web` en un puerto aparte. `/` responde 200 en unos 0,5 s. Devengado, facturado y cobrado de los doce meses de 2026 coinciden, mes por mes, con un cálculo SQL independiente sobre `mcp.devengado`, `mcp.facturas` y `mcp.cobros` con la regla de moneda del ticket. "Sin convertir" también coincide: 10 facturas y 7 cobros en el año. No hay filas duplicadas por (`pestaña_id`, `lectura_id`, `celda`) en `mcp.facturas`, así que el join de cobros no multiplica.
- Base sintética adversarial (`craftech_os_t017_test`, borrada al terminar): `_seed_inicio` más estos casos:
  - `<script>` en el título de una planilla y `<img onerror>` en el texto de un error;
  - una lectura pedida pendiente;
  - una factura en USD cobrada en abril;
  - un total y un hito de fundings del año anterior;
  - un problema `fila_sin_interpretar` reabierto.

  La base vacía se probó aparte, solo con las migraciones.
- Navegador real: Chromium (Playwright) a 1280 px y 375 px sobre la base sintética. Se llegó a `/` haciendo clic en "Inicio" desde `/fuentes`. Capturas en `plan/qa/evidence/T-017-r1-synthetic-1280.png` y `-375.png`, solo con datos de prueba. Sin errores de página. El único error de consola es el 404 de `/favicon.ico`, que ya existía. Las dos celdas `parity-off` se ven en rojo y en negrita (`rgb(179, 38, 30)`, peso 700).
- Los dos servidores que levanté quedaron parados.

## Criterios, uno por uno

1. `/` responde 200 y no redirige a `/cambios`; el menú tiene "Inicio" en `/cambios`, `/problemas`, `/fuentes`, `/facturas`, `/fundings` y `/clientes` (uno por pantalla), y el clic lleva a `/`. ✓
2. Facturado del mes = USD tal cual + `usd_inferido` de las ARS, sin pesos: ✓ (test; el mutante que suma pesos muere; coincide con SQL en datos reales).
3. ARS sin `usd_inferido` fuera del facturado y contada en "Sin convertir" con enlace a `/facturas?mes=`: ✓ (test y datos reales).
4. Cobro de una ARS con `usd_inferido` suma ese USD en el mes de la factura; el encabezado dice "Cobrado, por mes de la factura": ✓. El cobro de una factura en USD también suma (verificado con datos sintéticos y reales, sin test: ver F2).
5. Doce meses del año en curso más una fila de total: ✓ (también con la base vacía: doce meses en 0,00 y los mensajes de "No hay…" en paridades y problemas).
6. Un funding del mismo mes no cambia el facturado; vive solo en su bloque: ✓ (test; en la captura, marzo tiene 700 de fundings y el facturado no lo incluye).
7. Diferencias distintas de 0 resaltadas en cada paridad: ✓ (test, captura, estilo calculado). Las filas de paridad del año anterior no aparecen (datos sintéticos, sin test: ver F2).
8. Problemas abiertos por tipo con enlace a `/problemas?tipo=`; los resueltos no cuentan: ✓. Los 11 enlaces de tipo responden 200 contra la base real. Un problema reabierto se cuenta (datos sintéticos, sin test: ver F2).
9. Última lectura por planilla y error con su fecha: ✓. La lectura pendiente se muestra como "pendiente desde …" (datos sintéticos, sin test). Ver F3 sobre cómo se lee con los datos reales.
10. Sin formularios en `/` ni rutas POST nuevas: ✓ (`POST /` → 405; el diff no agrega rutas que escriban; la página no tiene ningún `<form>`).
11. Log del servidor después de abrir `/` y todos los enlaces: solo líneas de acceso (método, ruta, código), sin nombres ni montos. ✓

Comportamientos fuera de la pantalla nueva:
- `/problemas?tipo=` acepta los 11 tipos. `ISSUE_TYPES` es igual al conjunto del CHECK de `issue.issue_type` en la base migrada. ✓ (falta el test, F1).
- El `Host` ajeno sigue en 400 y `/?anio=2020` se ignora: el tablero no recibe parámetros.
- Escape: el título con `<script>` y el error con `<img onerror>` salen escapados en la tabla de planillas y en la paridad; no se abrió ningún diálogo en el navegador.

## Mutación

Harness en el scratchpad (`/tmp/t017-mut/mut.py`; falla si un archivo o patrón no existe y deja el árbol limpio). Corre `app/tests/test_web.py`.

| Mutante | Resultado | Lo mata |
|---|---|---|
| Facturado ARS suma pesos | muerto | `test_inicio_sums_each_month_in_usd` |
| "Sin convertir" de facturas cuenta todas | muerto | idem |
| Cobrado ARS suma pesos | muerto | idem |
| "Sin convertir" de cobros en 0 | muerto | idem |
| Join de cobros sin `celda` | muerto | idem |
| Once meses | muerto | test de los doce meses |
| Problemas cuentan los resueltos | muerto | test de problemas |
| `ISSUE_TYPES` vuelve a 4 | muerto | test de problemas |
| Sin clase `parity-off` | muerto | test de paridades |
| Sin enlace "Inicio" | muerto | `test_every_screen_answers_200` |
| Sin fecha del error | muerto | test de planillas |
| Sin enlace de "Sin convertir" | muerto | test de sumas |
| Total facturado = devengado | muerto | test de total |
| Año anterior | muerto | test de sumas |
| Devengado en 0 | muerto | test de sumas |
| `ISSUE_TYPES` sin `fila_sin_interpretar` (vale para 6 de los 7 tipos nuevos) | **vivo** | — (F1) |
| Cobrado de facturas USD en 0 | **vivo** | — (F2) |
| Paridad con "Pagos confirmados" sin filtro de año | **vivo** | — (F2) |
| Paridad con "TOTAL PAGOS AWS" sin filtro de año | **vivo** | — (F2) |
| Problemas sin `reabierto` | **vivo** | — (F2) |
| Lectura pendiente no se muestra | **vivo** | — (F2) |
| Total cobrado en 0,00 | **vivo** | — (F2) |
| Fundings: el total del año en cada mes | **vivo** | — (F2) |

En los ocho casos vivos el código está bien por lectura, y los datos sintéticos y reales lo confirman. Lo que falta es el test.

## Findings

### F1 [major] Seis de los siete tipos nuevos de `ISSUE_TYPES` no tienen un test que falle si se los quita
- **Repro:** sacar `fila_sin_interpretar` (o cualquiera de los tipos nuevos salvo `alias_sin_cliente`) de `ISSUE_TYPES` en `app/craftech_os/web/app.py`, y correr `uv run pytest app/tests/test_web.py`: queda verde.
- **Expected:** `ISSUE_TYPES` es un registro cerrado y el ticket le agrega siete entradas. Cada entrada agregada necesita un test que falle sin ella. **Actual:** solo `alias_sin_cliente` lo tiene.
- **Consecuencia:** si se pierde una entrada, el tablero sigue mostrando el enlace `/problemas?tipo=<ese tipo>` y el enlace devuelve 400. No es hipotético: en la base real hay problemas abiertos de `fila_sin_interpretar`.
- **Arreglo barato:** cualquiera de estos dos hace fallar la suite si falta una entrada.
  - Un test que compare `set(ISSUE_TYPES)` con los valores del CHECK de `issue.issue_type` en la base migrada.
  - Un test parametrizado que pida `/problemas?tipo=<t>` → 200 para cada tipo del CHECK.
- Consulté la severidad con un asesor. Me dijo major, porque es el caso que la regla nombra y porque el enlace roto se ve con datos reales. Me quedé con major.

### F2 [minor] Comportamientos del tablero sin test (los puntos ciegos declarados)
- **Repro:** los siete mutantes vivos de la tabla, salvo el de F1. Son los huecos que implement declaró: un solo año y un solo mes, sin cobros en USD, sin lecturas pendientes, sin paridades de otros años, sin un mes con hitos de los dos lados.
- **Expected:** que la suite falle si se rompen. **Actual:** sigue verde.
- **Prioridad:** el cobro en USD es el más importante, porque en los datos reales la gran mayoría de los cobros son en USD. Si se rompe, el cobrado del tablero cae a casi nada con la suite en verde. Después vienen los dos filtros de año de las paridades y el "pendiente desde", que el ítem 9 del `## Test plan` da por probado sin que haya un test.
- **Arreglo:** en `_seed_inicio` alcanza con agregar:
  - una factura en USD con su cobro;
  - un total y un hito del año anterior;
  - un problema reabierto;
  - una `read_request` pendiente;
  - un segundo mes con fundings.

  Más las aserciones correspondientes.

### F3 [minor] La tabla de planillas presenta como vigente un error que ya pasó
- **Repro (base real):** las 20 planillas muestran "Último error" en rojo. Son errores de red del 22 y 23 de octubre. En 11 de ellas el error es anterior a la fecha de "Última lectura", así que la lectura siguiente salió bien.
- **Por qué confunde:** `mcp.sources.ultimo_error` es el último `source_failed` registrado, aunque después haya lecturas buenas. A la vez, `leido_en` es, según su comentario, "la lectura más reciente que guardó algún cambio", no la última lectura hecha. Con el título "Última lectura", una planilla que se lee bien todos los días pero no cambia parece vieja. Y un error resuelto hace días se ve igual que uno de hoy.
- **Expected:** que se pueda distinguir si la planilla está fallando ahora. **Actual:** no se puede.
- **Alcance:** el ticket pidió justamente `leido_en` y el último error, así que es minor y no se deben mezclar arreglos de vista con este ticket. Arreglo mínimo sin tocar vistas: titular la columna "Última lectura con cambios" y mostrar el error en gris, no en rojo, cuando sea anterior a `leido_en`. El problema de fondo, que una planilla sin cambios no tiene una fecha de "leída bien por última vez", va como split-out.

### F4 [nit] El año del tablero sale del reloj del host
- `inicio()` usa `date.today()`. Los servicios de docker compose tienen `TZ` en Buenos Aires, pero si la web corre fuera de compose en otra zona, entre la medianoche UTC y la de Buenos Aires del 31 de diciembre muestra el año que no es. Es lo mismo que T-014 F2.

## Re-verificación de la ronda anterior

- Primera ronda: no aplica.

## No verificado

- Un mes con un hito de Pagos y uno del tracker a la vez se probó solo con los datos sintéticos de marzo: el tracker no tiene `mes` y queda fuera de la suma mensual por diseño, como registra la línea nueva de `plan/improvements.md`. No hay test (F2).
- A 375 px la tabla de ingresos se desborda de ancho (606 px de contenido). Pasa lo mismo en `/cambios`, `/fundings`, `/facturas` y `/fuentes`, así que no lo trajo este ticket.
- No hay captura con datos reales: tendría nombres de clientes y montos, que no pueden entrar a `plan/` según `plan/guidelines/code.md`.

## Split-outs sugeridos (fuera del alcance)

- [observability] `mcp.sources` no tiene la fecha de la última lectura que salió bien cuando la planilla no cambió, y `ultimo_error` no dice si un error ya quedó atrás. El tablero y `/fuentes` no pueden mostrar si una planilla falla hoy. Ver F3.
- [ux] A 375 px las tablas desbordan en todas las pantallas; hace falta un contenedor con scroll horizontal en `base.html`.
