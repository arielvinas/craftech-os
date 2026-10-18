---
id: T-001
title: Andamiaje: paquete Python, Compose con PostgreSQL, migraciones SQL, CLI y carga de sources.yaml
status: todo
priority: high
lane: core
depends_on: []
effort: M
milestone: A
branch:
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

- [ ] `docker compose -f infra/docker-compose.yml up -d postgres` levanta PostgreSQL 16 escuchando solo en `127.0.0.1:5432` (`docker compose port` lo muestra; `ss`/`lsof` no lo ve en otra interfaz) y con `default_toast_compression = lz4` (`SHOW default_toast_compression`).
- [ ] `docker compose run --rm app craftech-os migrate` crea `schema_migration`, `source`, `source_tab`, `system_event`; correrlo de nuevo no hace nada y termina en 0; modificar un archivo ya aplicado hace que termine distinto de 0 con un mensaje que nombra el archivo.
- [ ] `SELECT obj_description('source'::regclass)` y `col_description` de cada columna de las tres tablas devuelven texto en español (ninguna columna sin comentario; test que lo verifica).
- [ ] `docker compose run --rm app craftech-os sources load` deja 20 filas en `source` con los títulos exactos del anexo A y una fila en `source_tab` por cada pestaña nombrada en el anexo, con su clase; las 12 pestañas "A confirmar" del anexo quedan con clase `A_CONFIRMAR`. Correrlo dos veces no duplica filas.
- [ ] `craftech-os sources list` imprime las 20 planillas con el conteo por clase.
- [ ] `uv run pytest` y `uv run ruff check` pasan en limpio en la máquina de Ariel; los tests de integración se saltean con un mensaje claro si `TEST_DATABASE_URL` no está definida.
- [ ] `git grep -i -E 'private_key|BEGIN PRIVATE|@gmail|\.iam\.gserviceaccount'` no devuelve nada; `infra/.env` sigue ignorado y `infra/.env.example` no tiene valores.
- [ ] El comando `craftech-os` corre dentro del contenedor y también con `uv run craftech-os` fuera de él (mismo código, misma base por `DATABASE_URL`).

## Out of scope

- Cualquier llamada a Google (T-002). `drive_id` y `sheet_id` quedan nulos.
- Servicios `worker` y `web` en Compose, bucle de lectura, dump diario (T-003), web (T-006), servidor MCP (T-007).
- Esquemas de pestañas (columna clave, bloques) en `sources.yaml` (T-004).
- Terraform, AWS, cualquier cosa fuera de la laptop (etapa D).
- Tablas de etapas B y C (clientes, hechos, paridad): ADR, cambio 10.
