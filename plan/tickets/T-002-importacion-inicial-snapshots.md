---
id: T-002
title: Importación inicial: lector de Google Sheets, tabla snapshot y carga única de las 20 planillas
status: pr
priority: high
lane: core
depends_on: [T-001]
effort: L
milestone: A
branch: arielvinas/t-002
---

## Context

Segunda mitad de la unidad 1 del corte del ADR (`plan/adr/ADR-001-espejo-de-planillas-en-postgres.md`): leer Google y guardar la primera versión de cada pestaña. Origen de producto: `docs/03-proposal.md` sección 3.1 (capa cruda: cada versión de cada pestaña, entera, para siempre), sección 4.1 (importación inicial: todas las pestañas, incluidas ocultas e históricas, con valores, fórmulas, formato efectivo y celdas combinadas) y anexo B (hechos medidos el 18-oct-2026). Decisión 3 de Ariel: la historia de celdas empieza el día del arranque; `snapshot.origin` queda desde ahora porque cuesta una columna.

Hechos verificados el 18-oct-2026 con la service account `finance-bot-ingest` (anexo B de la propuesta), que el implementador no necesita volver a probar:
- Abre las 20 planillas del anexo A. Todas están en unidades compartidas: toda llamada a Drive necesita `supportsAllDrives=true` (sin eso, 404).
- Los números de versión de Drive cambian con cada guardado (por ejemplo "Facturación - Craftech Total" estaba en 66.931).
- Volumen estimado: 342 pestañas, 1 a 2 millones de celdas con contenido. La pestaña "CASH FLOW USA" de "CASH FLOW MENSUAL" tiene 62 columnas × 1.545 filas; las pestañas `data-*` llegan a 14.000 filas.
- La clave de la service account vive en `~/.config/craftech-os/secrets/` (nombre de archivo en `infra/.env`), nunca en el repo.

Verificado en el repo: T-001 deja `source` con `drive_id` nulo y `source_tab` con `sheet_id` nulo; este ticket los completa. No hay ningún cliente de Google en el repo ni se toma nada de la rama descartada `spike/stage-a`.

Prerrequisito operativo (ADR, seguridad en los límites): FileVault activo en la laptop de Ariel antes de la primera importación, porque entran sueldos y clientes al volumen de Docker. Lo verifica Ariel; el ticket lo deja anotado en el README.

## Scope

**Dónde vive:** `app/craftech_os/ingest/` (lectura de Google y snapshots), migración `0002_snapshot.sql`, `config/sources.yaml` (ids de Drive), CLI.

1. **Dependencias nuevas:** `google-api-python-client` y `google-auth` (Sheets v4 y Drive v3). Alcances solo de lectura: `spreadsheets.readonly`, `drive.readonly`. Credenciales desde la ruta en `GOOGLE_APPLICATION_CREDENTIALS`, montada en Compose como archivo de solo lectura desde `~/.config/craftech-os/secrets/` (variable `GOOGLE_SA_KEY_FILE` en `infra/.env`). Reintentos con espera creciente ante 429 y 5xx; cada reintento deja un `system_event`.
2. **Resolución de ids de Drive, una sola vez:** `craftech-os sources resolve` busca cada planilla por título exacto en Drive (`files.list` con `supportsAllDrives` e `includeItemsFromAllDrives`), exige exactamente una coincidencia (cero o varias = error que nombra el título) y escribe el `drive_id` en `config/sources.yaml` y en `source`. Los ids quedan commiteados en el YAML: en runtime se lee por id, nunca por título. Descartado: resolver por título en cada lectura (un renombre cambiaría la identidad de la planilla).
3. **Migración `0002_snapshot.sql`:** `snapshot` (id, source_tab, `drive_version`, `drive_modified_at`, `read_at`, `duration_ms`, `origin` con valores `lectura` y `revision_google`, `content_hash` sha256, `content` jsonb, `row_count`, `col_count`, `cell_count`). Índice por (source_tab, read_at). Nunca se borra ni se actualiza una fila (test: la aplicación no tiene ningún `DELETE`/`UPDATE` sobre `snapshot`). `COMMENT ON` en español en todo. `source_tab` gana `sheet_id` (ya existe, nulo) como identidad de runtime: Google lo mantiene estable aunque la pestaña se renombre.
4. **Lector de una pestaña:** una llamada `spreadsheets.get` con `includeGridData=true`, `ranges=<nombre de pestaña>` y máscara de campos acotada a: valor efectivo, valor formateado, valor ingresado (de donde sale la fórmula), color de fondo efectivo, patrón de formato numérico, celdas combinadas, propiedades de la pestaña (id, título, oculta, filas y columnas de la grilla). El documento JSONB guarda: filas con celdas no vacías (valor, texto formateado, fórmula si la hay, color de fondo en hexadecimal minúscula o nulo, formato numérico o nulo), lista de rangos combinados, tamaño usado. El hash se calcula sobre la serialización canónica (claves ordenadas) del documento. Entrada no confiable: el lector no interpreta nada, guarda lo que vino; lo que no sea serializable se registra como `system_event` de error y la pestaña se marca como fallida en esa corrida.
5. **Alta de pestañas desde Google:** antes de leer, `spreadsheets.get` sin datos lista las pestañas reales. Cada una se casa con `source_tab` por nombre (primera vez) y guarda su `sheet_id`; las de planillas con `all_tabs` toman esa clase; una pestaña que no está en el YAML se da de alta con clase `SIN_CLASIFICAR` y un `system_event` (en T-004 pasa a ser un problema). Una pestaña del YAML que no existe en Google queda `activa = false` con `system_event`.
6. **`craftech-os import [--source <título>]`:** lee todas las pestañas de las 20 planillas (todas las clases, incluidas ocultas, `HISTORICA`, `IGNORAR` y `A_CONFIRMAR`), de a una, y guarda un `snapshot` por pestaña con `origin = 'lectura'`, la versión y `modifiedTime` de Drive al momento de la lectura (`files.get` con `supportsAllDrives`). Si ya existe un snapshot de esa pestaña con el mismo hash como último, no guarda otro (así la importación se puede reanudar). Cada pestaña deja un `system_event` tipo `tab_read` con duración en ms y conteo de celdas; cada planilla, un resumen. **Los logs y los eventos llevan identificadores y conteos, nunca valores de celdas.**
7. **Medición:** `craftech-os import` termina imprimiendo las 10 pestañas más lentas con su duración; el ADR fija 60 segundos por lectura completa de "Facturación - Craftech Total" como disparador de optimización. Se anota el resultado medido en `## Implementation` del ticket.
8. **Tests:** unitarios del armado del documento JSONB y del hash a partir de respuestas sintéticas de la API (fixtures inventados, con nombres de cliente ficticios); de integración de `snapshot` contra el PostgreSQL del Compose. Ningún test llama a Google.

**Descartado:** normalizar celda por celda (ADR, cambio 8: millones de filas por día); compresión propia (lz4 de PostgreSQL alcanza); leer por rangos parciales o en paralelo (ADR: recién si una lectura supera 60 segundos, medido acá); caché de lecturas.

## Acceptance criteria

- [x] `craftech-os sources resolve` completa `drive_id` para las 20 planillas; `config/sources.yaml` commiteado tiene los 20 ids y `git diff` muestra solo ids, ningún dato.
- [x] `craftech-os import` corre completo en la laptop de Ariel y deja en `snapshot` exactamente una fila por pestaña activa (del orden de 342; el número exacto queda en `## Implementation`), cada una con `drive_version`, `drive_modified_at`, `content_hash` y `content` no nulos y `origin = 'lectura'`.
- [x] Correr `craftech-os import` de nuevo sin que cambie nada en Google no agrega filas a `snapshot` (mismo hash), y sí agrega `system_event` de lectura. Excepción aceptada (decisión de Ariel del 18-oct-2026): una pestaña cuyo único cambio es el ruido de punto flotante del recálculo de fórmulas de Google (misma versión de Drive y mismo `modifiedTime` que el snapshot anterior, solo cambia el valor efectivo de celdas con fórmula) puede sumar un snapshot nuevo; el código del hash no cambia y distinguir un cambio real queda para T-004.
- [x] Para una pestaña con celdas coloreadas (por ejemplo "Pagos" de "Facturación - Craftech Total"), el JSONB contiene colores de fondo en hexadecimal, fórmulas en las celdas que las tienen y al menos un rango combinado si la pestaña los tiene; se verifica con una consulta SQL, sin mostrar valores de celdas en el ticket ni en el QA.
- [x] Toda pestaña real tiene `sheet_id` en `source_tab`; una pestaña presente en Google y ausente del YAML queda con clase `SIN_CLASIFICAR` y un `system_event` que la nombra.
- [x] `system_event` tiene un evento `tab_read` por pestaña leída con `duration_ms` y `cell_count`; ningún `system_event` ni línea de log contiene un valor de celda (test sobre el serializador de eventos con un fixture que incluye un texto marcador y verifica que no aparece).
- [x] Un 429 simulado en test produce reintento con espera creciente y un `system_event` por intento; después del máximo de reintentos la pestaña se marca fallida y la importación sigue con la siguiente.
- [x] La clave de la service account no está en la imagen (`docker history`/`docker run ... ls` no la encuentra) ni en el repo; el contenedor la ve solo por el montaje de solo lectura.
- [x] `uv run pytest` y `ruff check` en limpio; ningún test necesita red.

## Out of scope

- Lectura continua, chequeo de versión, ventana de calma, `read_request`, dump (T-003).
- Diferencias entre versiones, `cell_change`, `issue` (T-004).
- Drive Activity API (T-005).
- Importar revisiones viejas de Google (`origin = 'revision_google'` queda definido pero sin código que lo use; decisión 3 de Ariel).
- Interpretar cualquier valor (etapa B). El lector guarda, no entiende.
- Optimizar lecturas lentas: se mide, no se optimiza, salvo que una pestaña supere los 60 segundos (en ese caso se anota en `plan/improvements.md`, no se resuelve acá).

## Implementation

**Archivos:**
- `app/craftech_os/ingest/google.py`: las cinco llamadas de solo lectura (`files.list`, `files.get`, `spreadsheets.get` sin datos y con datos), con reintento ante 429 y 5xx. La espera es de 1, 2, 4… segundos y hay hasta 6 reintentos; cada intento deja un evento `google_retry`.
- `app/craftech_os/ingest/document.py`: arma el documento JSONB desde la respuesta de la API (filas, celdas no vacías, colores en hex, fórmulas, combinadas, tamaño usado). La serialización es canónica y el hash es sha256.
- `app/craftech_os/ingest/importer.py`: da de alta las pestañas desde Google, lee de a una pestaña, compara el hash contra el último snapshot y registra los eventos `tab_read`, `tab_failed`, `tab_unclassified`, `tab_missing`, `source_read` y `source_failed`.
- `app/craftech_os/cli.py`: agrega `sources resolve` e `import [--source]`. Los errores esperables salen como `error: …`, sin traceback.
- `app/craftech_os/sources.py` y `config/sources.yaml`: `drive_id` en el YAML, más `with_drive_ids` para escribirlo sin tocar el resto del archivo.
- `app/migrations/0002_snapshot.sql`: crea `snapshot`, más `UNIQUE (source_id, sheet_id)` en `source_tab`.
- `infra/docker-compose.yml` y `infra/.env.example`: la clave se monta de solo lectura en `/run/secrets/google-sa.json`.
- `README.md`: sección de importación inicial, con FileVault como prerrequisito.

**Decisiones técnicas:**
- Una pestaña se casa con su fila de `source_tab` por `sheet_id`; si no tiene, por nombre, y solo contra filas que todavía no tienen `sheet_id`.
- `sources load` ya no desactiva las pestañas `SIN_CLASIFICAR`, porque vienen de Google y no del YAML.
- Un error al leer una pestaña la marca fallida y la corrida sigue. Puede ser un error HTTP, de transporte, de serialización, una respuesta de Drive sin `version` o sin `modifiedTime` (se validan dentro del mismo `try` que la lectura, antes de pedir la grilla), o un JSON que PostgreSQL no acepta (por ejemplo `\u0000`). Al final el comando sale con código 1 y dice cuántas lecturas fallaron.
- **httplib2** corta por defecto las respuestas gzip que se expanden más de 100 veces. La grilla de una pestaña grande supera ese límite (en la primera corrida hubo una de 100,4 veces). Desactivé ese chequeo de proporción, porque el único interlocutor es Google por TLS, y dejé un tope de 1 GiB por respuesta y un timeout de 300 segundos. `httplib2` y `google-auth-httplib2` se importan directamente, así que están declarados en `pyproject.toml` (piso en las versiones del lock, 0.32 y 0.4: el módulo `httplib2.decode` que usa el código es reciente).

**Medido en la laptop de Ariel (18-oct-2026), con la base de desarrollo:**
- Snapshots: **342**, uno por cada una de las 342 pestañas activas. Ninguna quedó sin `sheet_id` ni sin snapshot, y ninguna tiene más de uno después de la primera corrida.
- Campos: ningún snapshot tiene nulos en `drive_version`, `drive_modified_at`, `content_hash` ni `content`, y todos tienen `origin = 'lectura'`.
- Volumen: 3.276.719 celdas con contenido, la pestaña más grande con 309.396; la tabla ocupa 28 MB.
- Primera corrida completa: **7 min 01 s**. Hubo 4 respuestas 429 reales en `sheets.get`, que se reintentaron con esperas de 1, 2, 4 y 8 segundos y se recuperaron.
- **"Facturación - Craftech Total"**: 47 pestañas leídas en **44,6 segundos**. Queda por debajo del disparador de 60 segundos del ADR, así que no hay entrada en `improvements.md`.
- Pestañas más lentas: "Budget por Area 2026 - Final" / "SleakOps" con 16,8 s, "P&L Completo Craftech" / "gastos" con 11,2 s y "Base informe Craftech " / "Consolidado" con 9,2 s.
- "Pagos" de "Facturación - Craftech Total": 2.176 celdas, las 2.176 con fondo en hex `#rrggbb`. Hay 1.097 celdas con fórmula y 4 rangos combinados. Lo verifiqué solo con conteos, sin mostrar valores.
- Clases de las pestañas activas: CARGA 90, DERIVADA 171, HISTORICA 57, A_CONFIRMAR 12 e IGNORAR 12. Hoy no hay ninguna pestaña `SIN_CLASIFICAR`, porque el YAML cubre todas; ese caso está cubierto por test.
- Claves de los eventos en vivo: `tab_read` lleva `cell_count` y `stored`; `source_read` lleva `stored`, `unchanged` y `failed`; `google_retry` lleva `call`, `status`, `attempt` y `wait_s`. Ningún evento lleva valores.
- **Segunda corrida, sin cambios en Google**: 338 pestañas sin cambio y 4 con snapshot nuevo, todas de "CASH FLOW MENSUAL" (CASH FLOW ARG, Cash Flow - c/ pagos proyectados, CASH FLOW USA y Resumen mensual Cash Flow ARG-USA). Agregó 342 `tab_read`.
  - En esas 4 pestañas la versión de Drive y el `modifiedTime` son los mismos. Lo único que cambia es el valor efectivo de celdas con fórmula: diferencias de hasta 4e-8, ruido de punto flotante del recálculo de Google. El texto formateado es idéntico.
  - Ariel decidió aceptar ese ruido en la capa cruda (ver `## Decisions`): el criterio 3 se reescribió para excluirlo y no cambia el código del hash. Las otras 338 pestañas no suman snapshot. El caso queda anotado en `plan/improvements.md` para T-003 (no relee si la versión de Drive no cambió) y T-004 (qué cuenta como cambio).
- La corrida que se cortó por el límite de httplib2 dejó 70 snapshots parciales. Los borré a mano (`TRUNCATE snapshot` en la base de desarrollo) antes de la corrida completa. Sus eventos, hasta el id 71, quedaron.

## Test plan

- **Unitarios** (`test_document.py`): armado del documento desde grillas sintéticas (colores en hex, canales omitidos, fórmulas, combinadas, bloques con offset, celdas vacías), un hash estable ante el orden de las claves y un error ante NaN.
- **Integración** (`test_import.py`, con Google falso en memoria y sin red):
  - Importación completa y re-corrida sin snapshots nuevos.
  - Una pestaña nueva queda `SIN_CLASIFICAR` con evento, una ausente queda inactiva y `sources load` no borra las `SIN_CLASIFICAR`.
  - Un texto marcador no aparece en ningún evento ni en la salida.
  - Un 429 o un 503 se reintenta con esperas de 1 y 2 segundos. Tras el máximo de reintentos la pestaña falla y la corrida sigue; un 403 no se reintenta.
  - Un 404 de planilla, un error de transporte (`DecodeLimitError`) y un `\u0000` fallan solo su pestaña o su planilla.
  - Una respuesta de Drive sin `version`, o sin `modifiedTime`, falla solo esa pestaña con un `tab_failed` `{"error": "KeyError"}` y la corrida sigue (`test_a_drive_answer_without_version_fails_only_that_tab`, dos casos).
  - Una planilla sin `drive_id` no llama a Google, y un `--source` desconocido da error.
  - `resolve` parcial, con duplicados.
  - No hay `DELETE`, `UPDATE` ni `TRUNCATE` sobre `snapshot` en el código.
- **QA en vivo**: correr `craftech-os import --source "Facturación - Craftech Total"` y las consultas de conteo de arriba. Nunca imprimir `content`. En la ronda de arreglos la corrí de nuevo: `source_read` dio 0 stored, 47 unchanged, 0 failed.
- **Criterio 3 reescrito**: una re-corrida puede sumar snapshots solo en pestañas con la misma `drive_version` y el mismo `drive_modified_at` que su snapshot anterior y cuyo único cambio de contenido es el valor efectivo de celdas con fórmula por ruido del recálculo (hoy, las 4 de "CASH FLOW MENSUAL"); cualquier otra pestaña con un snapshot nuevo sin cambio en Google es un fallo.
- **Dependencias**: `pyproject.toml` declara `httplib2` y `google-auth-httplib2`; la imagen construida importa `httplib2.decode` y `google_auth_httplib2`.
- **Radio de impacto**: `sources load` (T-001) cambió en dos cosas: guarda `drive_id` y respeta las `SIN_CLASIFICAR`. `source_tab` tiene una restricción única nueva, `(source_id, sheet_id)`.

## Post-merge

- En el `infra/.env` de main, agregar `GOOGLE_SA_KEY_FILE=gcp-finance-bot-ingest.json`, que es el nombre del archivo dentro de `~/.config/craftech-os/secrets/`.
- Comprobar que FileVault esté activo en la laptop.
- Correr, en este orden: `docker compose -f infra/docker-compose.yml build app`, `… run --rm app craftech-os migrate`, `… run --rm app craftech-os sources load` y `… run --rm app craftech-os import`.
- La base de desarrollo ya tiene `0002_snapshot.sql` aplicada desde esta rama y los 342 snapshots. Si la migración cambia antes del merge, hay que recrear la base con `docker compose -f infra/docker-compose.yml down -v` y volver a correr los pasos de arriba.


## Decisions

- 2026-10-18 — **Una segunda importación sin cambios en Google agrega snapshots en 4 pestañas de CASH FLOW MENSUAL por ruido de punto flotante del recálculo de Google (hasta 6e-8, misma versión y modifiedTime de Drive). ¿Cómo se resuelve?** → Opción a: ajustar el criterio. Se acepta ese ruido en la capa cruda, sin cambiar el código del hash ni deduplicar por versión de Drive. Distinguir un cambio real queda para T-004 (diferencias celda a celda). El criterio del ticket se reescribe para excluir el ruido de recálculo de fórmulas.
