---
id: T-002
title: Importación inicial: lector de Google Sheets, tabla snapshot y carga única de las 20 planillas
status: todo
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

- [ ] `craftech-os sources resolve` completa `drive_id` para las 20 planillas; `config/sources.yaml` commiteado tiene los 20 ids y `git diff` muestra solo ids, ningún dato.
- [ ] `craftech-os import` corre completo en la laptop de Ariel y deja en `snapshot` exactamente una fila por pestaña activa (del orden de 342; el número exacto queda en `## Implementation`), cada una con `drive_version`, `drive_modified_at`, `content_hash` y `content` no nulos y `origin = 'lectura'`.
- [ ] Correr `craftech-os import` de nuevo sin que cambie nada en Google no agrega filas a `snapshot` (mismo hash), y sí agrega `system_event` de lectura.
- [ ] Para una pestaña con celdas coloreadas (por ejemplo "Pagos" de "Facturación - Craftech Total"), el JSONB contiene colores de fondo en hexadecimal, fórmulas en las celdas que las tienen y al menos un rango combinado si la pestaña los tiene; se verifica con una consulta SQL, sin mostrar valores de celdas en el ticket ni en el QA.
- [ ] Toda pestaña real tiene `sheet_id` en `source_tab`; una pestaña presente en Google y ausente del YAML queda con clase `SIN_CLASIFICAR` y un `system_event` que la nombra.
- [ ] `system_event` tiene un evento `tab_read` por pestaña leída con `duration_ms` y `cell_count`; ningún `system_event` ni línea de log contiene un valor de celda (test sobre el serializador de eventos con un fixture que incluye un texto marcador y verifica que no aparece).
- [ ] Un 429 simulado en test produce reintento con espera creciente y un `system_event` por intento; después del máximo de reintentos la pestaña se marca fallida y la importación sigue con la siguiente.
- [ ] La clave de la service account no está en la imagen (`docker history`/`docker run ... ls` no la encuentra) ni en el repo; el contenedor la ve solo por el montaje de solo lectura.
- [ ] `uv run pytest` y `ruff check` en limpio; ningún test necesita red.

## Out of scope

- Lectura continua, chequeo de versión, ventana de calma, `read_request`, dump (T-003).
- Diferencias entre versiones, `cell_change`, `issue` (T-004).
- Drive Activity API (T-005).
- Importar revisiones viejas de Google (`origin = 'revision_google'` queda definido pero sin código que lo use; decisión 3 de Ariel).
- Interpretar cualquier valor (etapa B). El lector guarda, no entiende.
- Optimizar lecturas lentas: se mide, no se optimiza, salvo que una pestaña supere los 60 segundos (en ese caso se anota en `plan/improvements.md`, no se resuelve acá).
