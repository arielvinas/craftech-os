# craftech-os

Registro de los compromisos financieros de Craftech, espejado desde sus planillas de Google Sheets. El índice de la documentación está en `CLAUDE.md`.

## Requisitos

- Docker con Compose.
- [uv](https://docs.astral.sh/uv/) para correr el código y los tests fuera del contenedor (`brew install uv`). uv baja Python 3.12 solo.

## Levantar la base

```bash
cp infra/.env.example infra/.env   # completar: contraseñas solo con letras y números
docker compose -f infra/docker-compose.yml up -d postgres
```

PostgreSQL 16 queda escuchando solo en `127.0.0.1:5432`. Al crear el volumen por primera vez, `infra/postgres-init/01-app-user.sh` crea el usuario de aplicación `craftech_app` (no es superusuario), le da la base `POSTGRES_DB` y crea la base de prueba `<POSTGRES_DB>_test`. Si cambiás `infra/.env` después, ese script no vuelve a correr: borrá el volumen (`docker compose -f infra/docker-compose.yml down -v`) o cambiá la contraseña a mano.

## Migraciones y fuentes

Dentro del contenedor (la imagen se construye sola la primera vez; después de cambiar código, `docker compose -f infra/docker-compose.yml build app`):

```bash
docker compose -f infra/docker-compose.yml run --rm app craftech-os migrate
docker compose -f infra/docker-compose.yml run --rm app craftech-os sources load
docker compose -f infra/docker-compose.yml run --rm app craftech-os sources list
```

- `migrate` aplica en orden los archivos `app/migrations/NNNN_descripcion.sql` que falten, cada uno en su transacción, y los registra en `schema_migration`. Un archivo ya aplicado no se edita: si su contenido cambió, `migrate` falla nombrándolo. Para cambiar el esquema se agrega un archivo nuevo.
- `sources load` carga `config/sources.yaml` (planillas y clase de cada pestaña). Se puede correr las veces que haga falta: actualiza por título y nombre, y una pestaña que se saca del archivo queda inactiva, no se borra.
- `sources list` muestra cada planilla con la cantidad de pestañas activas por clase.

Fuera del contenedor es el mismo código, contra la misma base:

```bash
set -a; . infra/.env; set +a
export DATABASE_URL="postgresql://craftech_app:${APP_DB_PASSWORD}@127.0.0.1:5432/${POSTGRES_DB}"
uv run craftech-os migrate
```

## Importación inicial desde Google

Requisito: el disco de la laptop cifrado con FileVault (Configuración del Sistema → Privacidad y seguridad → FileVault). La base local guarda copias completas de las planillas de Finanzas.

La clave de la cuenta de servicio (`finance-bot-ingest`, solo lectura) vive en `~/.config/craftech-os/secrets/`, nunca en el repo ni en la imagen. En `infra/.env`, `GOOGLE_SA_KEY_FILE` es el nombre del archivo dentro de esa carpeta; Compose lo monta de solo lectura en el contenedor.

1. Una vez, ubicar cada planilla en Drive por su título exacto y anotar su id en `config/sources.yaml` (corre fuera del contenedor porque escribe ese archivo; commitear el cambio):

   ```bash
   set -a; . infra/.env; set +a
   export DATABASE_URL="postgresql://craftech_app:${APP_DB_PASSWORD}@127.0.0.1:5432/${POSTGRES_DB}"
   GOOGLE_APPLICATION_CREDENTIALS=~/.config/craftech-os/secrets/$GOOGLE_SA_KEY_FILE uv run craftech-os sources resolve
   ```

   Solo busca las planillas que todavía no tienen `drive_id`. Si un título no aparece o aparece más de una vez, lo nombra y termina con error.

2. Leer todas las pestañas (`--source "<título>"` para una sola planilla):

   ```bash
   docker compose -f infra/docker-compose.yml build app
   docker compose -f infra/docker-compose.yml run --rm app craftech-os import
   ```

   Guarda una foto (`snapshot`) por pestaña, ocultas incluidas, salvo que el contenido sea idéntico a la última foto. Registra en `source_tab` el identificador de cada pestaña y las que Google tiene y el archivo no (como `SIN_CLASIFICAR`). Cada lectura, reintento y error queda en `system_event`, con identificadores y conteos, nunca valores. Al final imprime un resumen por planilla y las diez pestañas más lentas; si alguna lectura falló, termina con error.

## Tests

```bash
uv run ruff check
uv run pytest
```

Los tests de integración usan la base de prueba y se saltean si `TEST_DATABASE_URL` no está definida. Cada test vacía el esquema `public` de esa base: nunca la apuntes a la base principal (los tests fallan sin tocar nada si el nombre de la base no termina en `_test`).

```bash
export TEST_DATABASE_URL="postgresql://craftech_app:${APP_DB_PASSWORD}@127.0.0.1:5432/${POSTGRES_DB}_test"
uv run pytest
```
