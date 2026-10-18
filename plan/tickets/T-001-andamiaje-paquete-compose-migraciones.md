---
id: T-001
title: Andamiaje: paquete Python, Compose con PostgreSQL, migraciones SQL, CLI y carga de sources.yaml
status: qa
priority: high
lane: core
depends_on: []
effort: M
milestone: A
branch: arielvinas/t-001-andamiaje
---

## Context

Primer ticket de la etapa A ("espejo") de Craftech OS. Origen: `plan/adr/ADR-001-espejo-de-planillas-en-postgres.md` (corte sugerido, unidad 1, partida en dos: este ticket no toca Google; la lectura e importación inicial es T-002) y `docs/03-proposal.md` secciones 2.1, 2.2, 2.5 y anexo A. La propuesta está aprobada por Ariel el 18-oct-2026; el ADR la ajusta sin reabrirla.

Verificado en el repo (18-oct-2026): no hay código. Solo `docs/`, `plan/adr/`, `README.md` de una línea, `.gitignore` (ya ignora `.env`, `*service-account*.json`, `secrets/`, `data/`, `*.dump`) e `infra/.env` (ignorado por git, existe en la máquina de Ariel). No existen `app/`, `config/` ni `infra/docker-compose.yml`. La rama `spike/stage-a` está descartada por decisión de Ariel: no se lee ni se reutiliza nada de ahí (ver `CLAUDE.md`).

Decisiones de Ariel para este ticket (18-oct-2026, sesión de tickets):
- Las pestañas marcadas "A confirmar" en el anexo A tienen clase propia `A_CONFIRMAR`: se importan una vez y no se vuelven a leer hasta que Finanzas confirme.

Reglas fijas del proyecto: código, comentarios, tests y commits en inglés con los términos de Craftech en español; nada de datos de clientes ni sueldos en el repo; la clave de la service account nunca entra al repo ni a la imagen.

## Scope

**Dónde vive** (propuesta, sección 2.5): `app/craftech_os/` (paquete), `app/migrations/` (SQL numerado), `app/tests/`, `config/sources.yaml`, `infra/Dockerfile`, `infra/docker-compose.yml`, `infra/.env.example`.

1. **Paquete `craftech_os`** en Python 3.12 con `pyproject.toml` y lockfile de `uv` (`uv.lock`). Dependencias de este ticket: `psycopg[binary]` 3 (sin ORM, SQL explícito), `pyyaml`. Desarrollo: `pytest`, `ruff`. Punto de entrada de consola `craftech-os` con `argparse` (stdlib; sin `click`/`typer`).
2. **Imagen Docker única** (`infra/Dockerfile`, base `python:3.12-slim`) que instala el paquete y deja `craftech-os` en el `PATH`. Incluye `postgresql-client` 16 (lo usa el dump de T-003; se instala acá para no reconstruir la base de la imagen después).
3. **Compose** (`infra/docker-compose.yml`) con dos servicios: `postgres` (imagen `postgres:16`, volumen nombrado, puerto publicado solo en `127.0.0.1:5432`, `default_toast_compression=lz4` por argumento de arranque) y `app` (la imagen del punto 2, sin comando por defecto: se usa con `docker compose run --rm app craftech-os ...`). Contraseñas y nombres de base en `infra/.env` (ignorado); `infra/.env.example` con los nombres de las variables y valores vacíos. Usuario de aplicación `craftech_app` distinto del superusuario, creado por un script de inicialización del contenedor de PostgreSQL.
4. **Aplicador de migraciones** `craftech-os migrate`: aplica en orden los archivos `app/migrations/NNNN_descripcion.sql` que no estén registrados en `schema_migration` (nombre, aplicada a las, hash del archivo), cada uno en una transacción. Rechaza con error un archivo ya aplicado cuyo hash cambió. Idempotente.
5. **Migración `0001_sources.sql`** con `source` (id, `drive_id` nulo hasta T-002, título, unidad compartida, entidad que la carga), `source_tab` (id, source, `sheet_id` de Google nulo hasta T-002, nombre, clase, `schema` jsonb nulo, activa) y `system_event` (id, momento, tipo, source y source_tab opcionales, `details` jsonb, duración ms opcional). Clases permitidas: `CARGA`, `DERIVADA`, `HISTORICA`, `IGNORAR`, `A_CONFIRMAR`, `SIN_CLASIFICAR`. Cada tabla y columna lleva `COMMENT ON` en español con el término del glosario de Craftech (ADR, cambio 6); el catálogo del servidor MCP (T-007) se lee de ahí.
6. **`config/sources.yaml`** con las 20 planillas del anexo A por título completo (por ejemplo "Facturación - Craftech Total", nunca una sigla) y sus pestañas con clase. Para las planillas donde el anexo dice "todas DERIVADA" sin nombrar pestañas (los siete P&L por unidad de negocio, "P&L Completo Craftech", "Costos - Escenario 1") se usa `all_tabs: DERIVADA` y las pestañas se dan de alta al leer (T-002). El archivo tiene nombres de pestañas y títulos de planillas, nunca datos.
7. **`craftech-os sources load`**: carga el YAML en `source` y `source_tab` por título y nombre (upsert; una pestaña que desaparece del YAML queda `activa = false`, nunca se borra). **`craftech-os sources list`**: imprime planillas y conteo de pestañas por clase.
8. **Tests** con `pytest`: unitarios del parser del YAML y del orden de migraciones; de integración contra el PostgreSQL del Compose (`TEST_DATABASE_URL`, base de prueba recreada por sesión) para `migrate` y `sources load`. Sin datos reales.
9. **`README.md`**: cómo levantar Compose, correr migraciones y cargar fuentes, en español.

**Descartado:** Alembic u ORM (propuesta 2.2 y ADR: SQL legible por el equipo); `click`/`typer` (argparse alcanza para una decena de subcomandos); declarar `worker` y `web` en Compose ahora (no tienen código hasta T-003 y T-006).

## Acceptance criteria

- [x] `docker compose -f infra/docker-compose.yml up -d postgres` levanta PostgreSQL 16 escuchando solo en `127.0.0.1:5432` (`docker compose port` lo muestra; `ss`/`lsof` no lo ve en otra interfaz) y con `default_toast_compression = lz4` (`SHOW default_toast_compression`).
- [x] `docker compose run --rm app craftech-os migrate` crea `schema_migration`, `source`, `source_tab`, `system_event`; correrlo de nuevo no hace nada y termina en 0; modificar un archivo ya aplicado hace que termine distinto de 0 con un mensaje que nombra el archivo.
- [x] `SELECT obj_description('source'::regclass)` y `col_description` de cada columna de las tres tablas devuelven texto en español (ninguna columna sin comentario; test que lo verifica).
- [x] `docker compose run --rm app craftech-os sources load` deja 20 filas en `source` con los títulos exactos del anexo A y una fila en `source_tab` por cada pestaña nombrada en el anexo, con su clase; las 12 pestañas "A confirmar" del anexo quedan con clase `A_CONFIRMAR`. Correrlo dos veces no duplica filas.
- [x] `craftech-os sources list` imprime las 20 planillas con el conteo por clase.
- [x] `uv run pytest` y `uv run ruff check` pasan en limpio en la máquina de Ariel; los tests de integración se saltean con un mensaje claro si `TEST_DATABASE_URL` no está definida.
- [ ] `git grep -i -E 'private_key|BEGIN PRIVATE|@gmail|\.iam\.gserviceaccount'` no devuelve nada; `infra/.env` sigue ignorado y `infra/.env.example` no tiene valores. — **Sin tildar:** sobre todo el repo no puede dar vacío, porque `docs/01-understanding.md`, `docs/02-questions.md`, `docs/03-proposal.md` y este mismo ticket ya contenían el correo de la cuenta de servicio o la expresión antes de este ticket. Verificado sobre lo que agrega el ticket (`git grep ... -- app config infra pyproject.toml README.md`): vacío. `infra/.env` sigue ignorado (`git check-ignore`) y `infra/.env.example` tiene las cuatro variables vacías.
- [x] El comando `craftech-os` corre dentro del contenedor y también con `uv run craftech-os` fuera de él (mismo código, misma base por `DATABASE_URL`).

## Out of scope

- Cualquier llamada a Google (T-002). `drive_id` y `sheet_id` quedan nulos.
- Servicios `worker` y `web` en Compose, bucle de lectura, dump diario (T-003), web (T-006), servidor MCP (T-007).
- Esquemas de pestañas (columna clave, bloques) en `sources.yaml` (T-004).
- Terraform, AWS, cualquier cosa fuera de la laptop (etapa D).
- Tablas de etapas B y C (clientes, hechos, paridad): ADR, cambio 10.

## Decisions

- 2026-10-18 — **Títulos exactos de los 7 P&L por unidad de negocio, pestañas agrupadas entre paréntesis y pestañas de Proyeccion sueldos (dudas 1-3)** → Opción (a): una única lectura de solo metadatos (títulos de las 20 planillas y nombres de pestañas, sin valores de celdas) con la cuenta de servicio de solo lectura finance-bot-ingest (clave en ~/.config/craftech-os/secrets/), con un script descartable fuera del repo. Nunca escribir en Google. En config/sources.yaml solo nombres de planillas y pestañas; los IDs de Drive son de T-002.

## Implementation

Archivos:
- `pyproject.toml`, `uv.lock`, `.python-version`: paquete `craftech-os` (Python 3.12, `uv_build` con `module-root = "app"`), dependencias `psycopg[binary]` 3 y `pyyaml`; desarrollo `pytest` y `ruff`. Consola `craftech-os = craftech_os.cli:main`.
- `app/craftech_os/migrate.py`: aplicador. Archivos `NNNN_descripcion.sql` (nombre mal formado o número repetido es error), crea `schema_migration` (nombre, aplicada a las, sha256, con comentarios en español), revisa el hash de **todos** los aplicados antes de aplicar nada, y aplica cada pendiente en su transacción con `LOCK TABLE schema_migration` (dos `migrate` a la vez no aplican el mismo archivo dos veces).
- `app/migrations/0001_sources.sql`: `source`, `source_tab`, `system_event` con `COMMENT ON` en cada tabla y columna. Las clases son un `CHECK` (no un enum: agregar una clase es una migración de una línea). `source.default_class` guarda el `all_tabs` del YAML (nula si las pestañas se nombran una por una). "Entidad que la carga" quedó como `source.loaded_by` (texto nulo; el anexo A no lo trae por planilla, se completa más adelante).
- `app/craftech_os/sources.py`: parser que valida el YAML (claves desconocidas, clases desconocidas, `tabs` y `all_tabs` juntos o ninguno, títulos o pestañas repetidos, nombres vacíos), sin recortar espacios de los nombres. `load` hace upsert por título y por (planilla, nombre) en una transacción y desactiva las pestañas que ya no figuran, salvo en planillas `all_tabs` (ahí las pestañas las da de alta T-002 al leer). `summary` alimenta `sources list`.
- `app/craftech_os/cli.py`: `argparse` con `migrate`, `sources load [--file]`, `sources list`. Lee `DATABASE_URL`; errores esperables (migración modificada, YAML inválido, conexión) van a stderr con salida 1, sin captura genérica.
- `config/sources.yaml`: 20 planillas, 244 pestañas nombradas (12 `A_CONFIRMAR`), 9 planillas `all_tabs: DERIVADA`.
- `infra/Dockerfile` (python:3.12-slim, `postgresql-client-16` del repositorio apt de PostgreSQL, uv, usuario no root), `infra/docker-compose.yml` (proyecto `craftech-os`, volumen `craftech-os_db` para no chocar con los volúmenes viejos del spike), `infra/postgres-init/01-app-user.sh`, `infra/.env.example`.
- `app/tests/`: unitarios del parser (incluye el `sources.yaml` real) y del orden de migraciones; integración contra `TEST_DATABASE_URL` (cada test vacía `public`).
- `README.md` en español.

Nombres exactos (decisión de Ariel, opción a): una sola lectura de metadatos (títulos y nombres de pestañas, sin celdas) con finance-bot-ingest y un script descartable en `/tmp`, fuera del repo. Todas las pestañas nombradas del YAML se compararon contra esa lectura: coinciden las 244 y los conteos por planilla. Nombres con espacios que hay que respetar: `"Base informe Craftech "` (espacio final) y `" Pagos USA Sleakops(2023)"` (espacio inicial, sin espacio antes del paréntesis). Las agrupaciones entre paréntesis del anexo se expandieron a los nombres reales ("Pagos USA (2021)", …); en "Base informe Craftech " los paréntesis del anexo eran notas ("Ajuste cobros clientes", no "… (cuenta CLIENTES)").

**"P&L GEN AI - DATA" está en la papelera de Drive** (18-oct-2026). Está en el YAML para llegar a las 20 del anexo; T-002 puede no poder leerla.

Prueba rápida: `docker compose -f infra/docker-compose.yml up -d postgres && docker compose -f infra/docker-compose.yml run --rm app craftech-os migrate && docker compose -f infra/docker-compose.yml run --rm app craftech-os sources load && docker compose -f infra/docker-compose.yml run --rm app craftech-os sources list`.

Sin verificar: nada de los criterios salvo lo dicho sobre el `git grep` de todo el repo. `uv` no estaba instalado en la máquina; lo instalé con `brew install uv`.

## Test plan

1. Volumen nuevo: `docker compose -f infra/docker-compose.yml down -v && … up -d postgres`; `docker compose port postgres 5432` da `127.0.0.1:5432`; `lsof -nP -iTCP:5432 -sTCP:LISTEN` solo muestra `127.0.0.1`; `SHOW default_toast_compression` da `lz4`; `craftech_app` tiene `rolsuper = f`.
2. `run --rm app craftech-os migrate` dos veces: la primera "applied 0001_sources.sql", la segunda "nothing to apply", ambas salida 0.
3. Agregar una línea a `app/migrations/0001_sources.sql`, `build app`, `migrate`: salida 1 y "migration 0001_sources.sql changed after it was applied". Revertir.
4. `sources load` dos veces: `source` 20 filas, `source_tab` 244, 12 con `A_CONFIRMAR`; comparar los títulos contra Drive (incluido el espacio final de "Base informe Craftech ").
5. Sacar una pestaña del YAML, `build app`, `sources load`: la fila queda con `active = false`; volver a ponerla la reactiva. Cambiarle la clase la actualiza.
6. YAML inválido (`sources load --file` con una clase inexistente, un título repetido, `tabs` y `all_tabs` juntos): salida 1 con mensaje claro, sin cambios en la base.
7. `sources list`: 20 planillas, conteos por clase en el orden del glosario; las nueve `all_tabs` dicen "all tabs DERIVADA".
8. `uv run craftech-os sources list` desde la laptop con `DATABASE_URL` a `127.0.0.1` da lo mismo que dentro del contenedor; sin `DATABASE_URL`, salida 1.
9. `uv run pytest` sin `TEST_DATABASE_URL`: 25 pasan y 9 se saltean con el motivo; con la variable apuntando a `<POSTGRES_DB>_test`: 34 pasan. `uv run ruff check` limpio.
10. Cada columna de las cuatro tablas tiene comentario en español (`col_description`).

Radio de impacto: no había código; nada preexistente depende de estos archivos. `README.md` se reescribió (tenía una línea).

## Post-merge

1. En `main`, si `infra/.env` no existe o viene del spike: `cp infra/.env.example infra/.env` y completar las cuatro variables (contraseñas solo letras y números). Si el volumen `craftech-os_db` ya existe con otra contraseña, `docker compose -f infra/docker-compose.yml down -v` (es una base nueva, no hay nada que perder).
2. `docker compose -f infra/docker-compose.yml up -d postgres` → `docker compose -f infra/docker-compose.yml port postgres 5432` da `127.0.0.1:5432`.
3. `docker compose -f infra/docker-compose.yml run --rm app craftech-os migrate` → "applied 0001_sources.sql".
4. `docker compose -f infra/docker-compose.yml run --rm app craftech-os sources load` y `… sources list` → "20 sources".
5. Opcional, limpieza del spike: `docker volume rm craftech-os_pgdata craftech-os_pgdata_v1` (ver `CLAUDE.md`).
