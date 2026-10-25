---
id: T-018
title: Movimientos de caja desde la pestaña Consolidado
status: done
priority: high
lane: core
depends_on: []
effort: M
milestone: C
branch: arielvinas/t-018-movimientos-de-caja
---

## Context

Primer ticket de la caja de la etapa C. El diseño es `plan/adr/ADR-003-caja-desde-movimientos.md`, aprobado por Ariel el 25-oct-2026: la caja se recalcula desde los movimientos bancarios de la pestaña Consolidado de «Base informe Craftech » y se compara contra el cashflow que arma Finanzas. Este ticket solo trae los movimientos; el cashflow mensual es T-019, la paridad T-020 y la pantalla T-021.

Decisiones del documento de arquitectura (ADR-003), que este ticket aplica sin reabrir:
- **Fuente única:** la pestaña Consolidado (21.535 filas, 17 columnas: Mes Corriente, Origen, Bank, Tipo Erogacion, Frecuencia, Tipo Mov, Rubro, Agrupador, Equipo, Moneda, Amount, TC, Amount USD, Detalle, Subdetalle, Area, Tipo gasto). Su fórmula en A1 junta las pestañas de cada banco y las de ajuste; las pestañas de cada banco **no** se interpretan.
- **Entidad según el banco:** Galicia, Macro, Credicoop y Caja Córdoba son de Craftech S.A. (pesos); Mercury y Mesh son de la sociedad de Estados Unidos (dólares); VETA y cripto son históricas. La transferencia de Mercury a Mesh es interna y el gasto se registra en Mesh. Un banco fuera de la lista es un problema, nunca una suposición.
- **Ajustes:** las filas con banco CLIENTES o AFIP se guardan marcadas como ajuste.
- **Sueldos solo como total:** en las filas del rubro «01. Sueldos», las columnas Detalle, Subdetalle y Equipo se guardan vacías, porque pueden traer nombres de personas.
- **Lo que no tiene regla se guarda, no se interpreta** (reglas del repo): `config/cashflow_rows.yaml` solo dice qué rubros, agrupadores o bancos suman en cada fila del Resumen; una fila sin regla queda «sin regla».

Verificado en el repo el 25-oct-2026:
- `app/craftech_os/interpret/__init__.py`: `INTERPRETERS` despacha **por nombre de pestaña** (`"VENTAS"`, `"Pagos"`, `"Pagos ARG"`, `"FUNDINGS"`), y `run()` devuelve `None` si la pestaña no es de clase CARGA o no tiene esquema. Por cada tabla de `COLUMNS` borra con `DELETE ... WHERE source_tab_id` e inserta todas las filas de la lectura; los problemas van por `detect.upsert(conn, tipo, f"{tab_id}:{clave}", ...)` y al final registra el evento `tab_interpreted` con `duration_ms`.
- **Hay dos pestañas llamadas "Consolidado"** en `config/sources.yaml`: la de «Base informe Craftech » es CARGA (la que se usa) y la de «Budget por Area 2026 - Final» es DERIVADA. Como el despacho va por nombre, la segunda queda afuera solo por el chequeo de clase CARGA.
- `app/craftech_os/sources.py` (cerca de la línea 170) exige que toda pestaña CARGA con intérprete tenga un esquema con `grid` o `columns`.
- La sociedad de Estados Unidos se llama **'Craftech-io Inc.'** en `legal_entity` (migración 0008), al lado de 'Craftech S.A.'. El documento de arquitectura dice "Craftech Inc."; vale el nombre de la base.
- La última migración es `0013_fundings_collection_cut.sql`. La restricción `issue_issue_type_check` se redefinió por última vez en 0011, con su `COMMENT ON COLUMN issue.issue_type`.
- `ISSUE_TYPES` en `app/craftech_os/web/app.py` tiene que coincidir con esa restricción, y un test de `app/tests/test_web.py` lo verifica.
- Los tipos de problema que ya existen están en español (`color_desconocido`, `fila_sin_interpretar`, …). Los tres nuevos van en inglés con prefijo `cash_`, como dice el documento de arquitectura.

## Scope

**Dónde vive:**
- `app/migrations/0014_cash_movement.sql`.
- `app/craftech_os/interpret/consolidado.py` (nuevo) y su registro en `app/craftech_os/interpret/__init__.py`.
- `config/sources.yaml`: el esquema de la pestaña Consolidado de «Base informe Craftech ».
- `config/cashflow_rows.yaml` (nuevo) y su cargador.
- `app/craftech_os/web/app.py`: solo `ISSUE_TYPES`.
- `app/tests/`.

1. **Migración 0014.**
   - Tabla `cash_movement`, rehecha por lectura como las de ADR-002: `source_tab_id`, `snapshot_id`, `rules_version`, `row_key`, `cell_ref`, mes, banco, entidad (referencia a `legal_entity`, nula en las históricas) con una marca `historical`, moneda, monto, tipo de cambio, monto en dólares, tipo de movimiento, rubro, agrupador, una marca `adjustment` (bancos CLIENTES y AFIP), y Detalle, Subdetalle y Equipo como texto que puede ser nulo.
   - Un `CHECK` que impide Detalle, Subdetalle o Equipo no nulos cuando el rubro es «01. Sueldos».
   - `CHECK` en las enumeraciones (moneda, tipo de movimiento) y `COMMENT ON` en castellano en la tabla y cada columna.
   - `issue_issue_type_check` redefinida con los tres tipos nuevos, y su `COMMENT ON COLUMN issue.issue_type` actualizado:
     - `cash_header_mismatch`: los encabezados de la lectura no son los 17 esperados (las lecturas viejas de 396 filas y 40 columnas caen acá). Esa lectura no se interpreta y se dejan intactos los movimientos de la lectura anterior buena.
     - `cash_unknown_bank`: un banco que no está en la lista de bancos y entidades. La fila se guarda sin entidad y no suma en ninguna fila del cashflow.
     - `cash_unmapped_rubro`: un rubro o agrupador que no aparece en ninguna regla de `config/cashflow_rows.yaml`.
   - Permisos: escritura para `craftech_app`; ningún `GRANT` a `mcp_reader` todavía (las vistas MCP son de T-019).
2. **Intérprete de Consolidado.**
   - Valida los encabezados contra los 17 del esquema antes de leer cualquier fila.
   - Saca la entidad de una lista cerrada de bancos en el esquema, resuelta contra `legal_entity` por nombre ('Craftech S.A.' y 'Craftech-io Inc.'). VETA y cripto llevan la marca `historical`.
   - La transferencia de Mercury a Mesh se guarda como movimiento interno (tipo de movimiento propio), para que no se cuente dos veces.
   - Vacía Detalle, Subdetalle y Equipo en las filas de «01. Sueldos» **antes** de construir la fila, no después.
   - **Desambiguación de la pestaña:** el despacho va por nombre y hay dos "Consolidado". El intérprete se registra de manera que solo corra para la pestaña de «Base informe Craftech » (por título de planilla, no solo por el chequeo de clase CARGA). Un test lo cubre con las dos pestañas sembradas.
   - El `details` de cada problema lleva planilla, pestaña, celda y cantidades; nunca montos ni textos de Detalle.
3. **Esquema en `config/sources.yaml`.** Encabezado, columna clave y lista de columnas de Consolidado, más la lista de bancos con su entidad. Pasa la validación de `sources.py` (esquema con `columns`).
4. **`config/cashflow_rows.yaml`.** Los bloques del Resumen («Argentina en miles de pesos», saldo final en dólares, Craftech Inc. en dólares, Craftech Inc. con pagos proyectados y «Diferencia entre proyectado y real»), y por cada fila qué rubros, agrupadores o bancos suman y en qué unidad. Solo etiquetas, ningún monto. Se cargan las reglas que salen directo de los rubros; las filas cuyo mapeo no es obvio quedan sin regla y se listan en la descripción del pedido de cambios para que Ariel las lleve a Emi o Ro.
   - Intercompany = rubro «CAJA. Intercompany».
   - Cargas sociales = rubro «01. Sueldos» con agrupador CCSS (solo personal argentino o híbrido, y solo en el cashflow).
5. **Tiempo de reinterpretación.** El evento `tab_interpreted` de Consolidado lleva `duration_ms` y la cantidad de movimientos y problemas. Se mide sobre la lectura real de la base local y el número va en la descripción del pedido de cambios. Si pasa de 10 segundos, se registra como pregunta abierta para la interpretación incremental; no se implementa acá.

**Descartado:**
- Interpretar las pestañas de cada banco: Consolidado ya las junta.
- Adivinar la entidad de un banco nuevo: es un problema `cash_unknown_bank`.
- Guardar Detalle, Subdetalle o Equipo de los sueldos, aunque sea cifrado.

## Acceptance criteria

- [x] La migración 0014 crea `cash_movement` con `COMMENT ON` en castellano en la tabla y en cada columna, y la base rechaza una fila de «01. Sueldos» con Detalle, Subdetalle o Equipo no nulos.
- [x] `issue_issue_type_check` acepta `cash_header_mismatch`, `cash_unknown_bank` y `cash_unmapped_rubro`, y `ISSUE_TYPES` de la web los incluye; el test que compara los dos sigue pasando.
- [x] Una lectura sintética de Consolidado con encabezados correctos produce un movimiento por fila con mes, banco, entidad, moneda, monto, tipo de cambio, monto en dólares, tipo de movimiento, rubro y agrupador.
- [x] Galicia, Macro, Credicoop y Caja Córdoba quedan en 'Craftech S.A.'; Mercury y Mesh en 'Craftech-io Inc.'; VETA y cripto marcados como históricos; CLIENTES y AFIP marcados como ajuste.
- [x] Un banco fuera de la lista abre `cash_unknown_bank` y su fila queda sin entidad.
- [x] Una lectura con otros encabezados abre `cash_header_mismatch`, no toca los movimientos de la lectura anterior y no inserta filas.
- [x] Un rubro sin regla en `config/cashflow_rows.yaml` abre `cash_unmapped_rubro`.
- [x] En las filas de «01. Sueldos» Detalle, Subdetalle y Equipo quedan nulos aunque la lectura los traiga, y ningún texto de esas celdas aparece en `issue.details` ni en `system_event.details` (test con un nombre sintético que se busca en las dos tablas).
- [x] La pestaña DERIVADA "Consolidado" de «Budget por Area 2026 - Final» no se interpreta (test con las dos pestañas sembradas).
- [x] Una segunda lectura reemplaza todos los movimientos de la pestaña (no se acumulan).
- [x] El evento `tab_interpreted` de Consolidado registra `duration_ms` y las cantidades, sin montos; el tiempo medido sobre la base local queda en la descripción del pedido de cambios.
- [x] `config/cashflow_rows.yaml` no tiene ningún monto, y las filas sin regla quedan listadas en la descripción del pedido de cambios.
- [x] Los tests usan solo datos sintéticos.

## Out of scope

- El cashflow mensual, el origen de cada celda, los indicadores y las vistas MCP (T-019).
- La paridad contra el Resumen (T-020) y la pantalla `/caja` (T-021).
- La interpretación incremental (solo si el tiempo medido pasa de 10 segundos, y en otro ticket).
- El motor de proyección, escenarios, «Pagos en disputa», las facturas argentinas en el cashflow, budget y resultado, y la API de Mercury.

## Implementation

Archivos:
- `app/migrations/0014_cash_movement.sql`: tabla `cash_movement` con `COMMENT ON` en castellano en la tabla y cada columna. Tiene `CHECK` de moneda (ARS, USD, USDC), de tipo de movimiento (los 6 de la pestaña más `Interno`) y de mes en día 1. Un `CHECK` impide que una fila histórica o de ajuste tenga entidad. La restricción `cash_movement_sueldos_without_detail` impide Detalle, Subdetalle o Equipo no nulos si el rubro es «01. Sueldos» **o** el tipo de movimiento es Sueldos. También redefine `issue_issue_type_check` (los 11 tipos anteriores más los 3 `cash_*`) y actualiza los comentarios de `issue.issue_type`, `issue.stable_key` y `mcp.issues.tipo`.
- `app/craftech_os/interpret/consolidado.py` (nuevo): valida los 17 encabezados antes de leer filas y saca la entidad del mapa `banks` del esquema. La transferencia de Mercury a Mesh (banco MERCURY, rubro «CAJA. Mesh», agrupador MESH) pasa a tipo `Interno`. En las filas privadas vacía Detalle, Subdetalle y Equipo antes de construir el movimiento. Los bancos desconocidos y los rubros sin regla se agrupan: un problema por banco o por rubro, con la cantidad de filas y la primera celda.
- `app/craftech_os/interpret/__init__.py`: registra "Consolidado" con `ONLY_IN`, así que el intérprete solo corre si el título de la planilla es «Base informe Craftech ». Si los encabezados no coinciden, registra los problemas y el evento y no borra nada. El evento `tab_interpreted` suma `movements`.
- `app/craftech_os/sources.py`: el esquema de Consolidado exige las 17 columnas y un mapa `banks` no vacío. El chequeo de "CARGA con intérprete" usa el mismo despacho por título.
- `config/sources.yaml`: el esquema de Consolidado (17 columnas y bancos). `config/cashflow_rows.yaml` (nuevo): bloques y filas del Resumen, solo etiquetas.
- `app/craftech_os/web/app.py`: los 3 tipos nuevos en `ISSUE_TYPES`.
- `app/tests/test_consolidado.py` (16 tests, datos sintéticos) y `app/tests/test_db.py` (listas de tablas, migraciones y pestañas con esquema).

Decisiones técnicas:
- **Sueldos también por tipo de movimiento:** en la lectura real hay 85 filas con Tipo Mov "Sueldos" bajo otros rubros que traían Detalle: CCSS (37), «19. Impuestos» (29), «06. Capacitación» (8), «10. Comercial» (5), «21. Impuesto a las Gcias» (3), «09. Honorarios profesionales» (2) y «07. Sist. y Proc. Datos» (1). El alcance solo nombraba el rubro «01. Sueldos». Se vacían igual, para no guardar nombres, y la restricción de la base cubre los dos casos. **Lo tienen que ratificar Emi o Ro.**
- En las filas privadas, el agrupador no va al `details` del problema `cash_unmapped_rubro`, porque puede traer un nombre. En la tabla sí se guarda, porque el cashflow lo necesita (CCSS).
- Un tipo de movimiento o una moneda fuera de la lista se guarda nulo y abre `fila_sin_interpretar` con su celda. En la lectura real pasa una vez: una fila con Tipo Mov "Ordinario".
- Los bancos de ajuste (CLIENTES, AFIP) y los históricos (VETA, cripto) quedan sin entidad.
- El dueño de las tablas es `craftech_app`, así que no hace falta `GRANT`. A `mcp_reader` no se le dio nada.
- La restricción de tipos de problema se redefinió por última vez en 0009 (el ticket decía 0011). La 0014 parte de esa versión.
- La pestaña DERIVADA "Consolidado" es de «Budget por Area 2026 - Final». Queda afuera por el título y además por la clase.

Medición sobre la lectura local de Consolidado (snapshot 1850, en una transacción revertida, sin escribir nada):
- 21.534 movimientos, en unos 1,1 s (`duration_ms` 1112 y 1098 en dos corridas). Está muy por debajo de los 10 s, así que no hace falta interpretación incremental.
- 15 problemas: 14 `cash_unmapped_rubro` y 1 `fila_sin_interpretar`. Ningún `cash_unknown_bank`.
- Movimientos por entidad: 'Craftech S.A.' 11.183, 'Craftech-io Inc.' 9.796, ajuste 428, histórico 127.
- Ninguna fila de Sueldos (por rubro o por tipo) guarda Detalle, Subdetalle o Equipo.

Rubros sin regla en `config/cashflow_rows.yaml`, con su cantidad de filas, para que Ariel los lleve a Emi o Ro:

| Rubro | Filas |
|---|---|
| 26. Distribución de dividendos | 10 |
| 27. Pago Cta Pmo | 36 |
| CAJA. Aportes | 4 |
| CAJA. Crypto | 16 |
| CAJA. Extracción Caja Chica | 137 |
| CAJA. Mesh (fuera de la transferencia de Mercury a Mesh) | 168 |
| CAJA. Pago préstamo | 26 |
| CAJA. Transfencia Cuenta Propia | 641 |
| CCSS (como rubro) | 37 |
| CIRCUITO TECNOM | 240 |
| CIRCUITO YELLAMO | 25 |
| Egresos (como rubro) | 1 |
| Ingresos financieros (como rubro) | 109 |
| Mesh Cashback | 35 |

«CAJA. Transfencia Cuenta Propia» no se trató como movimiento interno: no lo dice ninguna regla ratificada.

Filas del Resumen sin regla (20), que quedan «sin regla» hasta que Emi o Ro las ratifiquen:
- Argentina: Saldo Inicial, Subtotal ingresos, Saldo Final, Ventas en $, Gastos en $.
- Saldo final en dólares: Saldo Final en USD.
- Craftech Inc. en dólares: Saldo Inicial, Subtotal ingresos, Saldo Final.
- Craftech Inc. con pagos proyectados: las 7 filas.
- Diferencia entre proyectado y real: las 4 filas.

Los saldos y subtotales son cuentas sobre otras filas, y quedan para T-019. Las filas proyectadas no salen de los movimientos.

Para el pedido de cambios: el tiempo medido (unos 1,1 s para 21.534 movimientos) y las dos listas de arriba tienen que ir en la descripción. Hasta entonces los criterios 11 y 12 quedan sin tildar.

## Test plan

1. Gates: `uv run ruff check .`, `uv run ruff format --check`, `uv run pytest -q` con `TEST_DATABASE_URL` (337 pasan) y `uv build`. No hay herramienta de tipos en el repo.
2. Mutaciones:
   - sin el vaciado de Sueldos, el test de Sueldos falla;
   - sin el chequeo `ONLY_IN`, falla `test_only_the_consolidado…`.
3. `cd app && uv run pytest tests/test_consolidado.py` cubre:
   - encabezados distintos: un problema y ningún movimiento tocado;
   - mapa de bancos y banco desconocido;
   - rubro sin regla;
   - Sueldos con un nombre sintético buscado en `issue.details` y `system_event.details`;
   - rechazo de la base por rubro y por tipo;
   - las dos pestañas "Consolidado";
   - una segunda lectura que reemplaza;
   - el evento con `duration_ms` y las cantidades.
4. Contra la base local, en una transacción revertida: `interpret.run` sobre la última lectura de Consolidado. Solo se imprimen cantidades y etiquetas.

## Post-merge

1. Aplicar la migración: `craftech-os migrate` (aplica `0014_cash_movement.sql`).
2. Recargar las fuentes para que la pestaña Consolidado tome su esquema: `craftech-os sources load`.
3. Pedir una lectura nueva de «Base informe Craftech » (o esperar la del worker), para que Consolidado se interprete y se llene `cash_movement`.
