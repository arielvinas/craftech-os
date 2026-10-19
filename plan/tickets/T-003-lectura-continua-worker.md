---
id: T-003
title: Lectura continua: worker cada 5 minutos por número de versión, ventana de calma, "leer ahora" y dump diario
status: todo
priority: high
lane: core
depends_on: [T-002]
effort: M
milestone: A
branch:
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

- [ ] `docker compose up -d` levanta `postgres` y `worker`; `docker compose logs worker` muestra una vuelta cada 5 minutos (±10 segundos) con planillas chequeadas y sin valores de celdas.
- [ ] Al editar una celda en una planilla de prueba propia de Ariel configurada en un `sources.yaml` de prueba (nunca en las planillas de Finanzas), en menos de 8 minutos aparece un `system_event` `version_changed`, luego un `calm_wait`, y un `snapshot` nuevo solo de la pestaña editada; las pestañas no tocadas no suman snapshots.
- [ ] Una pestaña `HISTORICA`, `IGNORAR` o `A_CONFIRMAR` de esa planilla de prueba, editada, no genera snapshot nuevo en la lectura continua; `craftech-os import --source` sí la relee.
- [ ] `craftech-os read-now "<título>"` dos veces seguidas deja una sola fila pendiente en `read_request`; en la siguiente vuelta tiene `served_at` y la planilla fue leída aunque su versión no haya cambiado.
- [ ] En test, el tope de calma de 10 minutos corta la espera y lee igual, dejando un `calm_wait` que lo indica.
- [ ] Un 429 simulado en el chequeo de versión produce `api_retry` y la vuelta termina; el worker sigue vivo en la siguiente.
- [ ] `craftech-os dump` deja un archivo `.dump` en `~/.config/craftech-os/backups/` restaurable con `pg_restore --list`; con 15 archivos presentes, el siguiente dump deja 14. `system_event` tiene el evento `dump` con tamaño.
- [ ] Matar el worker a mitad de una lectura y volverlo a levantar no deja snapshots parciales ni duplicados: la pestaña se vuelve a leer y se guarda una sola vez (verificar por `content_hash`).
- [ ] `uv run pytest` y `ruff check` en limpio; ningún test llama a Google ni necesita red.

## Out of scope

- Cálculo de diferencias entre snapshots (T-004): acá solo se guardan versiones.
- Drive Activity (T-005).
- Botón "leer ahora" en la web y pantalla Fuentes (T-006): solo la CLI.
- Subir el dump a S3 o a otro destino (pregunta abierta 1 del ADR, la decide Ariel).
- Alertas por Slack o correo (etapa D).
- Correr siempre prendido: la laptop dormida pierde vueltas; aceptado por Ariel durante la v0.
