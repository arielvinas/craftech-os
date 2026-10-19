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

PostgreSQL 16 queda escuchando solo en `127.0.0.1:5432`. Al crear el volumen por primera vez, `infra/postgres-init/01-app-user.sh` crea el usuario de aplicación `craftech_app` (no es superusuario), le da la base `POSTGRES_DB` y crea la base de prueba `<POSTGRES_DB>_test`, y `02-mcp-roles.sh` crea los usuarios `mcp_reader` y `mcp_writer` del servidor MCP. Si cambiás `infra/.env` después, esos scripts no vuelven a correr: borrá el volumen (`docker compose -f infra/docker-compose.yml down -v`) o cambiá la contraseña a mano. `02-mcp-roles.sh` se puede correr a mano sobre un volumen existente (crea los usuarios o les actualiza la contraseña):

```bash
docker compose -f infra/docker-compose.yml up -d postgres   # recrea el contenedor con las variables nuevas de infra/.env
docker compose -f infra/docker-compose.yml exec postgres sh /docker-entrypoint-initdb.d/02-mcp-roles.sh
```

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

   Guarda una foto (`snapshot`) por pestaña, ocultas incluidas, salvo que el contenido sea idéntico a la última foto. Registra en `source_tab` el identificador de cada pestaña y las que Google tiene y el archivo no (como `SIN_CLASIFICAR`, con un problema `pestana_sin_clasificar`). Cada lectura, reintento y error queda en `system_event`, con identificadores y conteos, nunca valores. Al final imprime un resumen por planilla y las diez pestañas más lentas; si alguna lectura falló, termina con error.

## Lectura continua (worker)

```bash
mkdir -p ~/.config/craftech-os/backups   # o la carpeta de BACKUPS_DIR en infra/.env
docker compose -f infra/docker-compose.yml up -d    # postgres y worker
docker compose -f infra/docker-compose.yml logs -f worker
```

Cada 5 minutos el worker pide a Drive el número de versión de cada planilla con `drive_id`. Si cambió desde la última lectura completa, espera a que pasen 2 minutos sin ediciones (consulta cada 30 segundos, como mucho 10 minutos) y lee solo las pestañas `CARGA` y `DERIVADA`; guarda una foto solo de las que cambiaron. Las demás clases se releen a mano con `craftech-os import --source "<título>"`. Cada vuelta imprime una línea con planillas chequeadas, leídas y fotos nuevas, y deja en `system_event` los eventos `worker_tick`, `version_changed`, `calm_wait`, `source_failed` y `api_retry`. Un error en una planilla no frena a las demás; un error no previsto termina el proceso y Compose lo reinicia.

Para que lea una planilla en la próxima vuelta, sin esperar la calma y aunque su versión no haya cambiado:

```bash
docker compose -f infra/docker-compose.yml run --rm app craftech-os read-now "<título>"
```

### Dump diario

En la primera vuelta después de las 03:00 (hora de Buenos Aires), o si no hay un dump de las últimas 24 horas, el worker corre `pg_dump` hacia `BACKUPS_DIR` (por defecto `~/.config/craftech-os/backups/`) con el nombre `craftech-os-AAAA-MM-DD.dump` y conserva los últimos 14. Cada dump deja un evento `dump` con tamaño y duración; si falla, un `dump_failed`, y el worker sigue. A mano:

```bash
docker compose -f infra/docker-compose.yml run --rm app craftech-os dump
```

Para revisar el contenido de un dump:

```bash
docker compose -f infra/docker-compose.yml run --rm app pg_restore --list /backups/craftech-os-AAAA-MM-DD.dump
```

## Cambios y problemas

Cada foto nueva de una pestaña se compara con la anterior en la misma transacción que la guarda (en `import` y en el worker). Los cambios van a `cell_change`: `value`, `formula_overridden` (había fórmula y ahora hay un valor tipeado), `formula`, `color`, `emptied`, `row_inserted`, `row_deleted`, `row_moved`, `column_inserted`, y los de pestaña `tab_added`, `tab_deleted`, `tab_renamed`. Cada comparación deja un evento `tab_diffed` con la cantidad por tipo; los valores anterior y nuevo solo están en `cell_change`, que se lee desde la base.

- **Pestañas con esquema** (`schemas:` en `config/sources.yaml`: texto de la fila de encabezado, columna clave, textos que abren cada bloque en esa columna, columnas de la grilla de meses): las filas se alinean por la clave normalizada (minúsculas, sin acentos, sin espacios dobles) dentro de cada bloque, así que insertar una fila arriba es un solo `row_inserted`. Dos filas con la misma clave se siguen por orden; si esa cantidad cambia, o una fila cambia de clave y de lugar a la vez, se comparan por posición y queda un problema `alineacion_ambigua`. Si la fila de encabezado no aparece, la pestaña se compara por posición y queda un evento `schema_mismatch`.
- **Pestañas sin esquema** (todas menos "Pagos", "Pagos ARG" y "VENTAS" de las dos de facturación y "FUNDINGS"): se comparan celda a celda por posición; insertar una fila arriba cambia todas las de abajo. Para alinear otra pestaña por clave se le agrega un esquema en el YAML y `sources load`, sin tocar código.
- **Renombrar una pestaña:** si se renombra solo en Google, el worker la sigue por su identificador y deja `tab_renamed`. Hay que renombrarla también en `config/sources.yaml`; si no, el próximo `sources load` crea una fila nueva con el nombre viejo y la pestaña renombrada vuelve como `SIN_CLASIFICAR`.

Problemas (`issue`, con su estado en la vista `v_issue`): `color_desconocido` (un color en la grilla de meses que no es uno de los cinco de la regla R29, uno por pestaña y color), `valor_ilegible` (texto en la grilla de meses, por pestaña, bloque, fila y columna), `alineacion_ambigua` y `pestana_sin_clasificar`. Verlo de nuevo solo actualiza `last_seen_at`. El estado sale de la última fila de `issue_resolution`: `abierto` sin resolución, `ignorado` (no se reabre), `resuelto`, y `reabierto` si se volvió a ver después de resuelto. Una celda vacía que solo tiene color no se guarda en la foto, así que su color no se detecta.

Para recalcular a mano las diferencias entre las dos últimas fotos de una pestaña (o entre dos fotos dadas), sin guardar nada; imprime solo cantidades:

```bash
docker compose -f infra/docker-compose.yml run --rm app craftech-os diff --tab "Facturación - Craftech Total" "Pagos" [--from <id> --to <id>]
```

## Quién hizo cada cambio

Google no dice quién editó cada celda; la Drive Activity API (alcance `drive.activity.readonly`, de solo lectura) dice quién editó el archivo y cuándo. Cada actividad se guarda una sola vez en `drive_activity`, con el identificador opaco del editor (`people/...`, o `deletedUser` para cualquier cuenta eliminada), nunca su nombre. Un cambio se atribuye a los editores con ediciones entre la versión anterior y cinco minutos después de la nueva (Google registra las ediciones con uno o dos minutos de demora): uno solo es `cierta` (y `attributed_at` es la hora de su última edición), varios es `una_de`, ninguno es `sin_datos`. Los cambios de pestaña no se atribuyen. La vista `v_attribution_stats` da, por planilla y día, cuántos salieron de cada forma.

El worker trae la actividad de cada planilla que leyó, de las que tienen cambios esperando atribución y de las que no se consultan hace una hora, y atribuye al final de la vuelta (eventos `activity_read`, `activity_failed`, `attributed`). Para traer toda la historia la primera vez (`--source "<título>"` para una sola planilla):

```bash
docker compose -f infra/docker-compose.yml run --rm app craftech-os drive import
```

Los editores aparecen como "editor sin identificar #N", numerados por orden de primera aparición (el número no cambia). Para ver cada uno con sus ediciones, planillas, horas habituales y fechas:

```bash
docker compose -f infra/docker-compose.yml run --rm app craftech-os editors
```

Para ponerle nombre, una fila en `editor_profile` (`actor_id`, `person_name`, `author`, `reason`), que se escribe desde Claude Desktop con `asociar_editor`; la última por editor manda y se ve en la vista `v_editor`. Las notas sobre una planilla, pestaña, cambio o problema van a `annotation` (`anotar`).

## Clientes y aliases

Los archivos con datos de clientes viven fuera del repo, en `~/repos/craftech-os-data/`. Se montan solo para la carga, de solo lectura:

```bash
docker compose -f infra/docker-compose.yml run --rm -v ~/repos/craftech-os-data:/data:ro app \
  craftech-os clients load-zoho /data/zoho/Contacts.csv
docker compose -f infra/docker-compose.yml run --rm -v ~/repos/craftech-os-data:/data:ro app \
  craftech-os aliases load /data/aliases.csv
```

- `clients load-zoho` carga las razones sociales de la Inc (`client_legal_entity` con sistema `zoho`). La clave es el tax ID; sin tax ID, la razón social normalizada. "Net N" es N días, "Due on Receipt" es 0 y cualquier otro plazo (vacío, "Custom") queda en 10. Una razón social nueva va al cliente con su Display Name, que se crea si no existe.
- `aliases load` lee un CSV con las columnas `fuente`, `texto`, `cliente`, `decidió`, `motivo` (todas obligatorias; una fila incompleta frena la carga entera). El texto se guarda normalizado. El cliente se busca por nombre de fantasía o por razón social, normalizados, y se crea con ese nombre si no existe. Solo se agregan filas: la decisión más reciente de cada fuente y texto es la vigente (`mcp.aliases`).
- Las dos cargas se pueden repetir: una fila igual a lo ya guardado se saltea. Imprimen y registran en `system_event` (`clients_loaded`, `aliases_loaded`) solo cantidades: leídas, creadas, actualizadas, salteadas.

## Web local

```bash
docker compose -f infra/docker-compose.yml up -d    # postgres, worker y web
```

Abre en <http://127.0.0.1:8000/> (solo desde esta laptop: no hay login). Es de solo lectura, salvo el botón "leer ahora":

- **Cambios:** los `cell_change` más nuevos primero, de a 100, con filtros por planilla, pestaña, tipo, clave de fila, editor (o "sin atribuir") y fechas, y un resumen por día y por tipo. Cada fila abre su detalle con fórmulas y colores anterior y nuevo. El editor se muestra con el nombre de `editor_profile` si tiene uno.
- **Problemas:** los de `v_issue` con su estado, dueño y última resolución; filtros por tipo, estado y planilla. Se resuelven desde Claude Desktop, no desde la web.
- **Fuentes:** la salud del sistema (última vuelta del worker, intervalo máximo de las últimas 24 horas, último dump con aviso si tiene más de 48 horas, tamaño de la base, reintentos de hoy) y cada planilla con sus pestañas. "Leer ahora" crea un pedido pendiente como `read-now`; si ya hay uno, no crea otro.

Para correrla fuera de Docker: `DATABASE_URL=... uv run craftech-os web`.

## Claude Desktop (servidor MCP)

Las preguntas sobre los datos se hacen desde Claude Desktop, que arranca `craftech-os mcp` dentro del contenedor `web` y le habla por entrada y salida estándar (sin puerto). Configuración y prueba en `docs/claude-desktop.md`.

- **Consultas** (usuario `mcp_reader`, que solo ve las vistas del esquema `mcp`, en transacciones de solo lectura de 10 segundos como máximo): `listar_cambios`, `ver_cambio`, `listar_problemas`, `ver_problema`, `listar_fuentes`, `listar_editores` y `consultar_sql` (un único `SELECT` o `WITH`, hasta 500 filas). Cada fila trae planilla, pestaña, celda y `leido_en`.
- **Escrituras** (usuario `mcp_writer`, que solo puede insertar en `issue_resolution`, `annotation`, `editor_profile`, `client` y `client_alias`): `resolver_problema`, `anotar` y `asociar_editor`, con `autor` y `motivo` obligatorios. Cada una deja un evento `mcp_write` con la herramienta y el autor. Sin `MCP_WRITER_DATABASE_URL`, el servidor arranca sin ellas.
- **Recursos:** `craftech://catalogo` (cada vista y columna del esquema `mcp` con su comentario, leído de la base) y `craftech://glosario` (sección 2 de `docs/v0.9.md`).

## Tests

```bash
uv run ruff check
uv run pytest
```

Los tests de integración usan la base de prueba y se saltean si `TEST_DATABASE_URL` no está definida. Cada test vacía los esquemas `public` y `mcp` de esa base: nunca la apuntes a la base principal (los tests fallan sin tocar nada si el nombre de la base no termina en `_test`).

```bash
export TEST_DATABASE_URL="postgresql://craftech_app:${APP_DB_PASSWORD}@127.0.0.1:5432/${POSTGRES_DB}_test"
export MCP_READER_PASSWORD MCP_WRITER_PASSWORD   # los tests del servidor MCP se conectan con los dos usuarios
uv run pytest
```
