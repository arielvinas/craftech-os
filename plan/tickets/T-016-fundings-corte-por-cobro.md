---
id: T-016
title: "Fundings: corte por mes de cobro en el log y textos de CEI ratificados"
status: in-progress
priority: high
lane: core
depends_on: []
effort: M
milestone: B
branch: arielvinas/t-016-fundings-corte-por-cobro
---

## Context

La regla R28 corta los fundings de AWS en dos fuentes: la pestaña Pagos aporta lo cobrado hasta febrero de 2026 (por la columna de mes) y el log "FUNDINGS - Log de status [OFICIAL]" aporta lo posterior. Hoy el log se corta por la **fecha de carga** ("Fecha De Carga En Fp"): da hito una fila cargada desde el 25/2/2026 o todavía sin fecha de carga. Las dos fuentes miran fechas distintas, y eso deja un hueco: una fila del log **cargada en enero de 2026 y cobrada en junio de 2026** no está en Pagos (que termina en febrero) ni en el log (se cargó antes del corte). Es la diferencia de junio de 2026 que hoy muestra la vista de paridad contra la fila "TOTAL PAGOS AWS" de Pagos (ver T-012, sección "Por qué hay diferencia en junio de 2026").

**Decisión de Ariel del 22-oct-2026** (pendiente de ratificar por Ro; se aplica como supuesto vigente, ya registrada en la regla R28 de `docs/v0.9.md`): el corte lo decide el **mes de cobro** en las dos fuentes. Pagos sigue aportando lo cobrado hasta febrero de 2026; el log aporta las filas cuyo mes de cobro es marzo de 2026 o posterior, sin importar cuándo se cargaron. Mes de cobro de una fila del log = "Fecha de pago"; si está vacía, el sign-off estimado más 30 días (regla R22, el mismo cobro estimado que ya usa la vista de paridad); si las dos faltan, se usa la fecha de carga como hoy.

Además, el programa CEI (regla R40) quedó **ratificado por Emi y Ro** (commit `6fc6187`), y la regla R28 ampliada dice que desde marzo de 2026 manda el log: un monto de Pagos fuera de la fila CEI no es funding. El código todavía dice "pendiente de ratificar por Emi y Ro" en:

- `app/migrations/0012_cei_aws_parity.sql`: los COMMENT de `funding_milestone` (línea 26), `mcp.fundings` (línea 28) y `mcp.paridad_fundings_aws` (línea 68), y el texto del motivo en `issue_resolution` (línea 84). La migración 0012 está aplicada y tiene checksum: no se edita.
- `app/craftech_os/mcp/server.py:93`: glosario del servidor MCP (entradas "Hito de funding" y "CEI").
- `app/craftech_os/interpret/fundings.py:23`: comentario junto a `CEI_LAST_MONTH`.

Verificado en el código:

- `app/craftech_os/interpret/fundings.py:88-90`: el corte actual es `load_date = day(cell("load_date"))` y `if load_date is not None and load_date < CUT: continue`, con `CUT = date(2026, 2, 25)`.
- La columna "Fecha Estimada De Cobro" del log **no se lee** (no está en `config/sources.yaml:166-178`); el cobro estimado se calcula como sign-off estimado más 30 días.
- Los tests de fundings están en `app/tests/test_fundings.py`; el de corte actual es `test_the_tracker_gives_milestones_loaded_from_february_25_2026`.

## Scope

1. **Corte por mes de cobro** en `app/craftech_os/interpret/fundings.py`, para las filas del log:
   - Mes de cobro = mes de "Fecha de pago"; si falta, mes de sign-off estimado más 30 días.
   - Con mes de cobro anterior a marzo de 2026: no da hito (lo cubre Pagos).
   - Con mes de cobro de marzo de 2026 en adelante: da hito, aunque se haya cargado antes del 25/2/2026.
   - Sin ninguna fecha de cobro: se mantiene el criterio de hoy (cargada desde el 25/2/2026 o sin fecha de carga da hito); si se cargó antes del 25/2/2026, **abre un problema** con motivo (no se adivina de qué lado cae), siguiendo el patrón de los problemas que ya abre el módulo.
   - Pagos no cambia.
   - Efecto conocido y aceptado: un hito sin pagar puede cambiar de lado si cambia su sign-off estimado; el reemplazo entero por lectura lo absorbe.
2. **Migración nueva `app/migrations/0013_*.sql`** que reescribe los COMMENT de `funding_milestone`, `funding_milestone.origin`, `mcp.fundings`, `mcp.fundings.origen` y `mcp.paridad_fundings_aws` con:
   - el criterio de corte por mes de cobro (decisión de Ariel del 22-oct-2026, pendiente de ratificar por Ro);
   - el programa CEI ratificado por Emi y Ro;
   - en la vista de paridad: desde marzo de 2026 un monto de Pagos fuera de la fila CEI no es funding (manda el log), y una diferencia en esos meses delata ese caso o un hito mal leído.
   - El motivo ya guardado en `issue_resolution` por la 0012 es historia: si las resoluciones son de solo agregar, no se toca y se deja una línea en la migración diciendo por qué; si el modelo admite corregir el texto, se corrige.
3. **Textos en código**: glosario de `app/craftech_os/mcp/server.py:93` y comentario de `app/craftech_os/interpret/fundings.py:23`, sin "pendiente de ratificar" para CEI y con el corte por mes de cobro.
4. **Tests** en `app/tests/test_fundings.py` para cada caso de los criterios.

Descartado: leer la columna "Fecha Estimada De Cobro" del log. Duplica una fecha que ya se calcula con la regla R22 y abriría una segunda fuente de verdad para el cobro estimado.

## Acceptance criteria

- [x] Una fila del log cargada en enero de 2026 con "Fecha de pago" en junio de 2026 da un hito de origen tracker en junio de 2026.
- [x] Una fila del log cargada en enero de 2026 sin "Fecha de pago" y con sign-off estimado más 30 días en abril de 2026 da un hito en abril de 2026.
- [x] Una fila del log con "Fecha de pago" en enero de 2026 no da hito, aunque esté cargada desde el 25/2/2026.
- [x] Una fila del log sin "Fecha de pago" ni sign-off estimado, cargada antes del 25/2/2026, no da hito y abre un problema con motivo; cargada desde el 25/2/2026 o sin fecha de carga, da hito como hoy.
- [x] Con los datos reales de Craftech, la diferencia de junio de 2026 en `mcp.paridad_fundings_aws` se cierra (o, si queda alguna, se explica en el PR con la celda que la causa).
- [x] Interpretar dos veces seguidas deja los mismos hitos y los mismos problemas, sin duplicados.
- [x] `grep -rn "pendiente de ratificar por Emi y Ro"` sobre `app/` solo encuentra la migración 0012 (inmutable); los COMMENT vigentes en la base (`obj_description` de las tablas y vistas tocadas) ya no lo dicen.
- [x] La migración 0012 no cambia (su checksum sigue igual).

## Out of scope

- Reabrir el programa CEI o su fin en septiembre de 2026.
- Cambiar cómo se lee Pagos o su corte en febrero de 2026.
- Leer la columna "Fecha Estimada De Cobro" del log.
- Cambiar la vista de paridad más allá de su COMMENT (ya suma el log por mes de pago o, si no tiene, por mes de cobro estimado).

## Implementation

- `app/craftech_os/interpret/fundings.py`: el corte del log pasa a ser por mes de cobro. Cobro = "Fecha de pago" o, si falta, sign-off estimado + 30 días (el mismo `estimated_collection` que ya se guardaba). Cobro en febrero de 2026 o antes → no da hito; marzo de 2026 o después → da hito sin mirar la fecha de carga. Sin ninguna fecha de cobro → como antes por fecha de carga, salvo que cargada antes del 25/2/2026 abre `fila_sin_interpretar` con clave `<bloque>:<fila>:cobro`, `cell_ref` en la celda de "Fecha de pago" y `reason` "sin fecha de pago ni sign-off estimado y cargada antes del 25/2/2026: no se sabe si la cubre Pagos". No se agregaron constantes: el corte usa `LAST_PAGOS_MONTH`. Comentarios de módulo, de `CUT` y de `CEI_LAST_MONTH` actualizados.
- `app/migrations/0013_fundings_collection_cut.sql`: solo COMMENT de `funding_milestone`, `funding_milestone.origin`, `mcp.fundings`, `mcp.fundings.origen`, `mcp.paridad_fundings_aws` y además `mcp.paridad_fundings`, cuyo texto ("los hitos cargados antes del 25/2/2026 están en Pagos") quedaba falso con el corte nuevo. `issue_resolution` es de solo agregar: el motivo que guardó la 0012 no se toca y la migración lo dice.
- `app/craftech_os/mcp/server.py`: glosario, entradas "Hito de funding" (corte por mes de cobro, pendiente de ratificar por Ro) y "CEI" (ratificado por Emi y Ro).
- Tests: `test_the_tracker_is_cut_by_collection_month_whenever_the_row_was_loaded` (los casos de los criterios, los bordes 28/2 y 1/3 del cobro estimado, "Fecha de pago" que manda sobre el sign-off, idempotencia) y `test_the_fundings_descriptions_say_cei_is_ratified_and_cut_by_collection`. Ajustados: la lista de migraciones de `test_db.py`, la aserción del glosario de `test_mcp.py` y dos comentarios de fixtures de `test_fundings.py`.
- Datos reales (copia descartable de la base local, borrada después; misma copia interpretada primero con el código de main y después con el de la rama): la diferencia de junio de 2026 de "Facturación - Craftech Total" en `mcp.paridad_fundings_aws` queda en 0. La cierran dos filas del log, celdas I14 e I19 de "FUNDINGS - Log de status [OFICIAL]", cargadas en enero de 2026 y pagadas en junio de 2026. El log pasa de 95 a 97 hitos y abre un `alias_sin_cliente` nuevo para el texto de esas filas. Ninguna fila real cae en el problema nuevo `:cobro`. Las diferencias de otros meses (marzo a agosto de 2026 y de noviembre de 2026 a marzo de 2027 en Craftech; mayo de 2025 y marzo a mayo de 2026 en SleakOps) ya estaban con el código de main y no cambian: no son de este ticket.
- Sin consulta al advisor.

## Test plan

1. Fila del log cargada en enero de 2026 con "Fecha de pago" en junio de 2026 → hito tracker; en `mcp.paridad_fundings_aws` suma en junio de 2026.
2. Cargada en enero de 2026, sin "Fecha de pago", sign-off estimado el 5/3/2026 → hito con cobro estimado el 4/4/2026.
3. Cargada el 25/2/2026 con "Fecha de pago" en enero de 2026 y sign-off en mayo → sin hito (manda la fecha de pago).
4. Bordes: sign-off 29/1/2026 (cobro 28/2) → sin hito; sign-off 30/1/2026 (cobro 1/3) → hito.
5. Sin "Fecha de pago" ni sign-off: cargada antes del 25/2/2026 → sin hito y un `fila_sin_interpretar` con `reason`; cargada el 25/2/2026 o sin fecha de carga → hito.
6. `craftech-os interpret --all` dos veces → mismos hitos y problemas.
7. Una "Fecha de pago" con texto (no fecha) → se trata como vacía y decide el sign-off.
8. `grep -rn "pendiente de ratificar por Emi y Ro" app/` → solo la 0012; `obj_description` de las vistas y la tabla tocadas no lo dicen.

Radio de impacto: `interpret/fundings.py` alimenta `funding_milestone`, `mcp.fundings`, `mcp.paridad_fundings`, `mcp.paridad_fundings_aws`, el chequeo `funding_duplicado` y las pantallas que muestran fundings (T-014). Un hito sin pagar puede cambiar de lado si cambia su sign-off estimado (aceptado en el ticket).

## Post-merge

1. En main, contra la base local: `uv run craftech-os migrate` (aplica `0013_fundings_collection_cut.sql`, solo COMMENT). Verificar: `SELECT name FROM schema_migration ORDER BY 1 DESC LIMIT 1` da la 0013.
2. Reconstruir y reiniciar el worker para que use el intérprete nuevo: `docker compose -f infra/docker-compose.yml up -d --build worker web`.
3. `uv run craftech-os interpret --all` (o esperar la próxima lectura). Verificar: `SELECT mes, diferencia FROM mcp.paridad_fundings_aws WHERE planilla = 'Facturación - Craftech Total' AND mes = '2026-06-01'` da 0.
