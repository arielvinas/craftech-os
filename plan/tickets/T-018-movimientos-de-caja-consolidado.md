---
id: T-018
title: Movimientos de caja desde la pestaña Consolidado
status: in-progress
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

- [ ] La migración 0014 crea `cash_movement` con `COMMENT ON` en castellano en la tabla y en cada columna, y la base rechaza una fila de «01. Sueldos» con Detalle, Subdetalle o Equipo no nulos.
- [ ] `issue_issue_type_check` acepta `cash_header_mismatch`, `cash_unknown_bank` y `cash_unmapped_rubro`, y `ISSUE_TYPES` de la web los incluye; el test que compara los dos sigue pasando.
- [ ] Una lectura sintética de Consolidado con encabezados correctos produce un movimiento por fila con mes, banco, entidad, moneda, monto, tipo de cambio, monto en dólares, tipo de movimiento, rubro y agrupador.
- [ ] Galicia, Macro, Credicoop y Caja Córdoba quedan en 'Craftech S.A.'; Mercury y Mesh en 'Craftech-io Inc.'; VETA y cripto marcados como históricos; CLIENTES y AFIP marcados como ajuste.
- [ ] Un banco fuera de la lista abre `cash_unknown_bank` y su fila queda sin entidad.
- [ ] Una lectura con otros encabezados abre `cash_header_mismatch`, no toca los movimientos de la lectura anterior y no inserta filas.
- [ ] Un rubro sin regla en `config/cashflow_rows.yaml` abre `cash_unmapped_rubro`.
- [ ] En las filas de «01. Sueldos» Detalle, Subdetalle y Equipo quedan nulos aunque la lectura los traiga, y ningún texto de esas celdas aparece en `issue.details` ni en `system_event.details` (test con un nombre sintético que se busca en las dos tablas).
- [ ] La pestaña DERIVADA "Consolidado" de «Budget por Area 2026 - Final» no se interpreta (test con las dos pestañas sembradas).
- [ ] Una segunda lectura reemplaza todos los movimientos de la pestaña (no se acumulan).
- [ ] El evento `tab_interpreted` de Consolidado registra `duration_ms` y las cantidades, sin montos; el tiempo medido sobre la base local queda en la descripción del pedido de cambios.
- [ ] `config/cashflow_rows.yaml` no tiene ningún monto, y las filas sin regla quedan listadas en la descripción del pedido de cambios.
- [ ] Los tests usan solo datos sintéticos.

## Out of scope

- El cashflow mensual, el origen de cada celda, los indicadores y las vistas MCP (T-019).
- La paridad contra el Resumen (T-020) y la pantalla `/caja` (T-021).
- La interpretación incremental (solo si el tiempo medido pasa de 10 segundos, y en otro ticket).
- El motor de proyección, escenarios, «Pagos en disputa», las facturas argentinas en el cashflow, budget y resultado, y la API de Mercury.
