---
id: T-003
title: Lectura continua: worker cada 5 minutos por número de versión, ventana de calma, "leer ahora" y dump diario
status: qa
priority: high
lane: core
depends_on: [T-002]
effort: M
milestone: A
branch: arielvinas/t-003
---

## Context

Unidad 2 del corte del ADR (`plan/adr/ADR-001-espejo-de-planillas-en-postgres.md`, cambios 2 y riesgo "pérdida del disco"). Origen de producto: `docs/03-proposal.md` sección 4.3 (lectura continua: cada 5 minutos solo el número de versión; lectura completa solo si cambió; calma de 2 minutos con tope de 10; solo pestañas de carga y derivadas), decisión 8 de Ariel ("Sí" al chequeo cada 5 minutos) y sección 2.4 (la laptop dormida corre lecturas: aceptado; la fecha del cambio sale de Drive Activity en T-005, no de la lectura).

Hechos verificados (anexo B de la propuesta): `files.get` con `fields=version,modifiedTime` y `supportsAllDrives=true` es una llamada liviana; 20 planillas × 12 veces por hora queda muy por debajo de las cuotas de Google.

El ADR reemplaza la cola de tareas de la propuesta por una tabla `read_request` que el worker revisa en cada vuelta (cambio 2) y agrega el dump diario porque Google no devuelve versiones viejas con el permiso actual: si se pierde el disco se pierde toda la historia. Pregunta abierta 1 del ADR (destino final del dump, S3 o carpeta sincronizada) sigue abierta y no bloquea: acá el dump va a una carpeta local.

Verificado en el repo tras T-002: existe el lector de pestañas, `snapshot` y `system_event`; no existe ningún proceso de larga duración ni servicio `worker` en Compose.

## Scope

**Dónde vive:** `app/craftech_os/worker.py` (bucle), `app/craftech_os/ingest/` (chequeo de versión y calma), migración `0003_read_request.sql`, `infra/docker-compose.yml` (servicio `worker`), CLI.

1. **Migración `0003_read_request.sql`:** `read_request` (id, source, `requested_at`, `requested_by` texto, `served_at` nulo hasta atenderlo, `snapshot_count` resultante). `COMMENT ON` en español.
2. **Bucle del worker** (`craftech-os worker`), un proceso, sin librería de planificación: cada vuelta (a) atiende los `read_request` pendientes, (b) consulta `files.get` de las 20 planillas pidiendo `version` y `modifiedTime`, (c) para cada planilla cuya versión difiere de la última conocida espera la ventana de calma (relee `modifiedTime` cada 30 segundos hasta que pasen 2 minutos sin cambios, con tope de 10 minutos desde el primer cambio visto), (d) lee las pestañas `CARGA` y `DERIVADA` de esa planilla con el lector de T-002 y guarda un `snapshot` solo si el hash difiere del último, (e) registra en `system_event` un evento `worker_tick` con duración y conteos, y duerme hasta completar 5 minutos desde el inicio de la vuelta. Un error en una planilla se registra y no frena a las demás; un error no previsto termina el proceso con código distinto de 0 (Compose lo reinicia con `restart: unless-stopped`); nunca se traga una excepción.
3. **Pestañas que no se releen:** `HISTORICA`, `IGNORAR`, `A_CONFIRMAR` y `SIN_CLASIFICAR` no entran en la lectura continua (decisión de Ariel para "A confirmar"; propuesta 4.3 para las demás). `craftech-os import --source <título>` sigue sirviendo para releerlas a mano.
4. **"Leer ahora" por CLI:** `craftech-os read-now <título de planilla>` inserta un `read_request` si no hay otro pendiente para esa planilla (idempotente: si lo hay, lo dice y termina en 0). El worker lo atiende en la próxima vuelta sin esperar la calma y marca `served_at`. La web lo expone en T-006 sobre esta misma tabla.
5. **Dump diario:** una vez por día (a la primera vuelta después de las 03:00 hora local, o si no hay dump de las últimas 24 horas) el worker corre `pg_dump -Fc` con el cliente 16 ya instalado en la imagen (T-001) hacia `/backups/craftech-os-AAAA-MM-DD.dump`, carpeta montada desde `~/.config/craftech-os/backups/` (variable `BACKUPS_DIR` en `infra/.env`). Conserva los últimos 14 archivos y borra los más viejos. Cada dump deja un `system_event` tipo `dump` con tamaño y duración; un fallo deja un `system_event` de error y no detiene el worker. `craftech-os dump` lo corre a mano. La fecha del último dump la muestra la web en T-006 (alerta si supera 48 horas).
6. **Compose:** servicio `worker` con la imagen de T-001, `restart: unless-stopped`, montajes de solo lectura para la clave y de escritura para `/backups`, dependencia de `postgres`. El worker corre con el usuario de aplicación `craftech_app`.
7. **Métricas en `system_event`** (las lee la pantalla Fuentes en T-006): `worker_tick` (duración, planillas chequeadas, planillas leídas, snapshots nuevos), `version_changed` (planilla, versión anterior y nueva), `calm_wait` (segundos esperados, si llegó al tope), `tab_read` (ya existe), `dump`, `api_retry`.
8. **Tests:** unitarios del bucle con el reloj y el cliente de Google simulados (una planilla cambia de versión → se espera la calma → se leen solo las pestañas `CARGA`/`DERIVADA` → se guarda solo lo que cambió de hash); del tope de 10 minutos; de `read-now` idempotente; de la retención de 14 dumps sobre un directorio temporal. Integración contra el PostgreSQL del Compose para `read_request`.

**Descartado:** cola de tareas en PostgreSQL o Redis (ADR, cambio 2: un worker, una tarea); `cron` del sistema (propuesta 2.2: no sirve igual en la laptop y en AWS); frecuencia distinta por planilla (recién si una lectura medida en T-002 supera 60 segundos).

## Acceptance criteria

- [x] `docker compose up -d` levanta `postgres` y `worker`; `docker compose logs worker` muestra una vuelta cada 5 minutos (±10 segundos) con planillas chequeadas y sin valores de celdas.
- [ ] Al editar una celda en una planilla de prueba propia de Ariel configurada en un `sources.yaml` de prueba (nunca en las planillas de Finanzas), en menos de 8 minutos aparece un `system_event` `version_changed`, luego un `calm_wait`, y un `snapshot` nuevo solo de la pestaña editada; las pestañas no tocadas no suman snapshots.
- [ ] Una pestaña `HISTORICA`, `IGNORAR` o `A_CONFIRMAR` de esa planilla de prueba, editada, no genera snapshot nuevo en la lectura continua; `craftech-os import --source` sí la relee.
- [x] `craftech-os read-now "<título>"` dos veces seguidas deja una sola fila pendiente en `read_request`; en la siguiente vuelta tiene `served_at` y la planilla fue leída aunque su versión no haya cambiado.
- [x] En test, el tope de calma de 10 minutos corta la espera y lee igual, dejando un `calm_wait` que lo indica.
- [x] Un 429 simulado en el chequeo de versión produce `api_retry` y la vuelta termina; el worker sigue vivo en la siguiente.
- [x] `craftech-os dump` deja un archivo `.dump` en `~/.config/craftech-os/backups/` restaurable con `pg_restore --list`; con 15 archivos presentes, el siguiente dump deja 14. `system_event` tiene el evento `dump` con tamaño.
- [x] Matar el worker a mitad de una lectura y volverlo a levantar no deja snapshots parciales ni duplicados: la pestaña se vuelve a leer y se guarda una sola vez (verificar por `content_hash`).
- [x] `uv run pytest` y `ruff check` en limpio; ningún test llama a Google ni necesita red.

## Out of scope

- Cálculo de diferencias entre snapshots (T-004): acá solo se guardan versiones.
- Drive Activity (T-005).
- Botón "leer ahora" en la web y pantalla Fuentes (T-006): solo la CLI.
- Subir el dump a S3 o a otro destino (pregunta abierta 1 del ADR, la decide Ariel).
- Alertas por Slack o correo (etapa D).
- Correr siempre prendido: la laptop dormida pierde vueltas; aceptado por Ariel durante la v0.

## Implementation

- `app/migrations/0003_read_request.sql`: tabla `read_request` con un índice único parcial (`source_id` donde `served_at` es nulo). Así "una sola fila pendiente por planilla" la garantiza la base, y `read-now` inserta con `ON CONFLICT DO NOTHING`.
- `app/craftech_os/worker.py`: tiene `tick` (una vuelta), `run` (el bucle; duerme `300 - duración`), `dump`, `dump_due` y `_wait_until_quiet`. El reloj entra como dos funciones (`now`, `sleep`), y así los tests no esperan.
  - La versión conocida de cada planilla es el `drive_version` del último evento `source_read`, que se guarda solo si se leyeron todas las pestañas. No hay tabla nueva para esto. Al reiniciar, el worker no relee lo que ya tenía. Si una pestaña falló o el proceso murió a mitad de una lectura, la versión no queda registrada y la planilla se relee en la vuelta siguiente; el hash evita guardar duplicados.
  - La primera vuelta sobre una base que nunca tuvo worker ve "cambio" en todas las planillas. Lee una vez sus pestañas `CARGA` y `DERIVADA` (no guarda snapshots si el hash es el mismo) y registra la versión.
  - Calma: la planilla está quieta si pasaron 2 minutos desde su `modifiedTime`. Si no, vuelve a preguntar cada 30 segundos, y a los 10 minutos de empezar la espera corta y la lee igual (`capped: true`). Cada planilla que cambió deja un `calm_wait`, aunque haya esperado 0 segundos.
  - Una planilla pedida con `read-now` se procesa primero, se lee sin esperar la calma y aunque su versión no haya cambiado, y queda `served_at` recién cuando se leyeron todas sus pestañas. Si Google falla, el pedido sigue pendiente y se reintenta en la vuelta siguiente.
  - Errores: un error de Google (los mismos que contempla el importador, `READ_ERRORS`) en el chequeo de versión de una planilla se registra como `source_failed` y la vuelta sigue con las demás. Un error no previsto se propaga y el proceso sale con código distinto de 0.
  - Dump: `pg_dump --format=custom` escribe un archivo `.partial` que después se renombra a `craftech-os-AAAA-MM-DD.dump` (fecha local), y se conservan los 14 más nuevos de ese patrón; los demás archivos de la carpeta no se tocan. Si falla, `dump_failed` guarda solo la última línea de stderr de `pg_dump`. Se usa la excepción propia `DumpFailed`, porque el mensaje de `CalledProcessError` incluye la línea de comando, con la URL y la contraseña.
- `app/craftech_os/ingest/importer.py`: `import_source` acepta `classes`, que filtra las pestañas por clase después de registrarlas, y `drive_version`. `_retry_logger` y `_error` pasan a ser públicas (`retry_logger`, `error_details`) porque el worker las usa.
- Evento `google_retry` → `api_retry` en todo el código, que es el nombre del ticket. Los eventos viejos de la base de desarrollo quedan con el nombre anterior.
- `app/craftech_os/cli.py`: tres comandos nuevos.
  - `worker`.
  - `read-now TITLE`: si el título no existe o la planilla no tiene `drive_id`, sale con 1.
  - `dump [--dir]`.
- `infra/docker-compose.yml`:
  - Servicio `worker`: con `restart: unless-stopped`, la clave montada de solo lectura y `BACKUPS_DIR` montado como `/backups`, que por defecto es `~/.config/craftech-os/backups`.
  - `TZ` en `America/Argentina/Buenos_Aires`, en `worker` y en `app`; en la prueba de humo, sin esto el dump hecho a mano salía con la fecha UTC.
  - `app` pasa al perfil `cli`, para que `docker compose up -d` levante solo `postgres` y `worker`; `docker compose run --rm app …` sigue igual.
- `infra/.env.example` tiene `BACKUPS_DIR`, y el README tiene la sección "Lectura continua (worker)".
- Prueba de humo, en un proyecto de Compose aparte (`craftech-os-t003`, con su volumen propio y sin puerto, sin tocar la base de desarrollo):
  - `migrate`.
  - `up -d`: levanta `postgres` y `worker`; la vuelta 1 dejó una línea en el log y el dump se hizo enseguida.
  - `pg_restore --list` del dump: lista 18 tablas.
  - Con 16 archivos presentes, `craftech-os dump` dejó 14.
  - `read-now` dos veces: "read requested" y después "already pending".
  - `read-now "Nope"`: sale con 1.
  - Una planilla falsa con un `drive_id` inexistente quedó en `source_failed`, con el pedido pendiente.
- Sin verificar: los criterios 2 y 3 (editar la planilla de prueba propia de Ariel). En esta máquina no hay un `sources.yaml` de prueba con esa planilla, y no leí ninguna planilla de Finanzas.

## Test plan

1. `docker compose up -d`: deben quedar solo `postgres` y `worker`. En `docker compose logs -f worker`, una línea `tick:` cada 5 minutos (±10 segundos), sin valores de celdas.
2. Con un `sources.yaml` de prueba que apunte a la planilla propia de Ariel, editar una celda de una pestaña `CARGA`. En menos de 8 minutos tienen que aparecer `version_changed`, `calm_wait` (con `waited_s` de 120 o más), y un `snapshot` nuevo solo para esa pestaña.
3. Editar una pestaña `HISTORICA`, `IGNORAR` o `A_CONFIRMAR` de la misma planilla: no aparece ningún snapshot nuevo. Después, `craftech-os import --source "<título>"` sí la relee.
4. Editar sin parar durante más de 10 minutos: queda un `calm_wait` con `capped: true` y la planilla se lee igual.
5. Correr `read-now "<título>"` dos veces: queda una sola fila pendiente. En la vuelta siguiente tiene `served_at` y `snapshot_count`, aunque no se haya editado nada.
6. `read-now` con un título inexistente, o con una planilla sin `drive_id`: sale con 1 y no inserta ninguna fila.
7. `craftech-os dump`, después `pg_restore --list` del archivo. Con 15 archivos `craftech-os-*.dump` presentes, después del dump quedan 14.
8. `docker compose kill worker` mientras lee una planilla y después `up -d`: esa planilla se relee y no hay `content_hash` duplicados por pestaña.
9. Una carpeta de backups sin permiso de escritura: aparece `dump_failed` y el worker sigue haciendo sus vueltas.

**Blast radius:**
- `importer.import_source`: los parámetros nuevos son opcionales, y `craftech-os import` sigue igual.
- El evento de reintento de `import` y de `sources resolve` ahora se llama `api_retry`.
- `docker-compose.yml`: `app` tiene perfil, y `docker compose up -d` ya no lo levanta (antes salía enseguida).
- `test_db` ahora incluye la migración 0003.

## Post-merge

En `main`, con `infra/.env` cargado:

1. Opcional: agregar a `infra/.env` la línea `BACKUPS_DIR=/Users/arielvinas/.config/craftech-os/backups`, con ruta absoluta. Si la variable queda vacía, se usa esa misma carpeta.
2. `mkdir -p ~/.config/craftech-os/backups`.
3. `docker compose -f infra/docker-compose.yml build app worker`.
4. `docker compose -f infra/docker-compose.yml run --rm app craftech-os migrate`. Debe imprimir `applied 0003_read_request.sql`.
5. `docker compose -f infra/docker-compose.yml up -d`. Verificar con `docker compose -f infra/docker-compose.yml logs worker`: tiene que aparecer una línea `tick:` (la primera vuelta lee una vez las pestañas `CARGA` y `DERIVADA` de las 20 planillas) y un `dumped craftech-os-AAAA-MM-DD.dump`.
6. Verificar el dump con `ls ~/.config/craftech-os/backups`.
7. Nota: en la base de desarrollo, los reintentos anteriores a este cambio se llaman `google_retry` en `system_event`, y los nuevos `api_retry`.
