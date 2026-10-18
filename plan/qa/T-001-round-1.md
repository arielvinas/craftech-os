# QA T-001 — Ronda 1

**Verdict: FAIL**
**Branch:** arielvinas/t-001-andamiaje @ fbf3101
**Gates:** typecheck — (el proyecto no tiene; ruff no tipa) · lint ✓ (`ruff check`, `ruff format --check`) · tests ✓ (sin `TEST_DATABASE_URL`: 25 pasan, 9 se saltean con el motivo; con la base de prueba: 34 pasan) · build ✓ (`docker compose build app`)
**Criteria:** 7/8 verificados tal como están escritos; el del `git grep` no se puede cumplir literalmente (ver F5) y su intención se verificó sobre lo que agrega el ticket.
**Mutation:** 15 mutantes a mano sobre `migrate.py`, `sources.py`, `cli.py`, `0001_sources.sql` y `config/sources.yaml`: 14 matan la suite. El único que sobrevive (sacar el primer `if f.name in applied: continue` de `migrate`) es equivalente: el chequeo dentro del `LOCK` hace lo mismo. Harness: `/tmp/qa-t001/mutants.py` (falla fuerte si falta un archivo o el patrón no aparece exactamente una vez).

No hay UI en este ticket: la parte de "navegador real" se reemplazó por ejercitar la CLI (dentro del contenedor y con `uv run`) y consultar PostgreSQL directamente. No se hizo ninguna llamada a Google.

## Criterios, uno por uno

1. **PostgreSQL 16 solo en 127.0.0.1 con lz4.** Volumen recreado (`down -v` + `up -d postgres`). `docker compose port postgres 5432` → `127.0.0.1:5432`; `lsof -nP -iTCP:5432 -sTCP:LISTEN` muestra solo `127.0.0.1:5432` (IPv4, ninguna otra interfaz); `SHOW default_toast_compression` → `lz4`; `version()` → PostgreSQL 16.15. `craftech_app`: `rolsuper=f`, `rolcreaterole=f`, `rolcreatedb=f`, dueño de `craftech` y `craftech_test`. ✓
2. **`migrate`.** Primera corrida "applied 0001_sources.sql", segunda "nothing to apply", ambas salida 0. Con una línea agregada a `0001_sources.sql` y `build app`: salida 1, `error: migration 0001_sources.sql changed after it was applied`. Revertido: vuelve a "nothing to apply". ✓
3. **Comentarios en español.** `col_description` de las 23 columnas de las cuatro tablas (incluida `schema_migration`) devuelve texto en español; `obj_description('source'::regclass)` también. El test `test_every_table_and_column_has_a_comment` lo cubre y muere si se borra un comentario. ✓
4. **`sources load`.** Dos corridas en el contenedor: `source` 20 filas, `source_tab` 244 (todas activas), 12 `A_CONFIRMAR`. Conté el anexo A a mano: 47+34+5+13+42+23+6+10+25+21+18 = 244 pestañas nombradas y 1+2+5+4 = 12 "A confirmar"; los conteos por clase de cada planilla en `sources list` coinciden con el anexo. `drive_id` y `sheet_id` todos nulos. Los títulos del YAML difieren del anexo donde el anexo abrevia (P&L por unidad, "Base informe Craftech " con espacio final): está respaldado por la lectura de metadatos registrada en `## Decisions`; no lo recontrasté contra Drive (fuera de lo que QA debe tocar). ✓
5. **`sources list`.** 20 planillas, conteo por clase en el orden del glosario, las nueve `all_tabs` dicen "all tabs DERIVADA", termina en "20 sources". ✓
6. **`uv run pytest` y `uv run ruff check`.** Ver Gates. El motivo del salteo es claro ("TEST_DATABASE_URL is not set: skipping integration tests (see README.md)"). ✓
7. **`git grep` de secretos.** Ver F5. Sobre `app config infra pyproject.toml README.md uv.lock`: vacío. `infra/.env` ignorado (`git check-ignore -v` → `.gitignore:2:.env`); `infra/.env.example` tiene las cuatro variables vacías. La imagen solo copia `app/` y `config/`: `infra/.env` no entra. Intención ✓, literal ✗.
8. **Dentro y fuera del contenedor.** `uv run craftech-os sources list` con `DATABASE_URL` a `127.0.0.1` y la misma corrida en el contenedor: `diff` vacío. En el contenedor el comando corre como usuario `craftech` (no root) y `pg_dump --version` da 16.15. ✓

## Findings

### F1 [major] Una planilla que se saca de `sources.yaml` deja todas sus pestañas activas
El alcance (punto 7) dice "una pestaña que desaparece del YAML queda `activa = false`". Eso se cumple si se saca una pestaña de una planilla que sigue en el archivo, pero no si se saca la planilla entera: `load` solo recorre las planillas presentes en el YAML.
- **Repro:** base de prueba migrada → `sources load --file` con `A: {CARGA: [x]}` y `B: {CARGA: [y]}` → `sources load --file` con solo `A` → `sources list`.
- **Expected:** la pestaña `y` de `B` queda `active = false` (y `B` deja de contar pestañas activas).
- **Actual:** `B|y|t`; `sources list` sigue mostrando `'B': CARGA 1`.
- **Por qué importa:** es un caso razonable y cercano ("P&L GEN AI - DATA" está en la papelera de Drive y es candidata a salir del archivo). Lo que lea T-002/T-003 a partir de `source_tab.active` seguiría leyendo una planilla dada de baja. No hay test que cubra este caso.

### F2 [minor] Dos `migrate` simultáneos sobre una base vacía: uno se cae con traceback
El `CREATE TABLE IF NOT EXISTS schema_migration` del arranque corre fuera del `LOCK`; dos procesos a la vez chocan en el catálogo.
- **Repro:** base de prueba vacía → dos `uv run craftech-os migrate` en paralelo (3 de 3 intentos).
- **Actual:** uno aplica `0001_sources.sql` y sale 0; el otro sale 1 con traceback `psycopg.errors.UniqueViolation: duplicate key value violates unique constraint "pg_type_typname_nsp_index"`. No queda nada a medias (`schema_migration` con 1 fila) y volver a correr funciona.
- La sección `## Implementation` afirma que dos `migrate` a la vez son seguros; lo son para no aplicar dos veces, no para terminar limpio. En una laptop de un solo usuario es improbable; alcanza con no afirmarlo, o con tomar un `pg_advisory_lock` antes del arranque.

### F3 [minor] Errores esperables que salen como traceback en vez de `error: ...`
`## Implementation` dice que los errores esperables van a stderr con salida 1 y mensaje. Estos tres salen con salida 1 (no se tragan nada) pero con traceback completo:
- YAML con error de sintaxis (`sources: [`): `yaml.YAMLError` no está en la lista del `except`.
- `sources load --file /nonexistent.yaml`: `FileNotFoundError`.
- `DATABASE_URL=garbage`: `psycopg.ProgrammingError`. (Revisé que el mensaje no imprima la contraseña de la URL: no la imprime.)

### F4 [minor] La fixture de integración borra el esquema de cualquier base que diga `TEST_DATABASE_URL`
`app/tests/conftest.py` hace `DROP SCHEMA public CASCADE` sin comprobar a qué base apunta. El README lo advierte, pero un `TEST_DATABASE_URL` copiado de `DATABASE_URL` borra la base principal en el primer `pytest`. Una línea que exija que el nombre de la base termine en `_test` (o `skip` con mensaje) lo evita.

### F5 [minor] El criterio del `git grep` no se puede cumplir tal como está escrito
`docs/01-understanding.md`, `docs/02-questions.md`, `docs/03-proposal.md` (en `main`, antes de este ticket) y el propio ticket contienen el correo de la cuenta de servicio o la expresión de búsqueda. No es una falla de la implementación: lo agregado por el ticket da vacío. Es un problema del criterio; para el coordinador: reformularlo como "`git grep ... -- app config infra pyproject.toml README.md uv.lock` no devuelve nada".

### F6 [nit] Pasar una planilla de `tabs` a `all_tabs` deja sus pestañas nombradas activas con la clase vieja
Repro: `A: {CARGA: [x]}` → `A: all_tabs: DERIVADA` → `sources list` muestra `'A': all tabs DERIVADA; CARGA 1`. Es coherente con la regla elegida (en planillas `all_tabs` no se desactiva nada porque las pestañas las da de alta T-002), pero la salida mezcla dos clasificaciones. Conviene decidirlo junto con F1.

## No verificado
- Títulos y nombres de pestañas contra Google Drive: QA no llama a Google; se confía en la lectura de metadatos de `## Decisions`.
- Typecheck: el proyecto no tiene uno configurado (no es un gate del ticket).

## Estado en que queda la máquina
PostgreSQL del Compose corriendo, con volumen `craftech-os_db` recreado: base principal migrada y cargada (20 planillas, 244 pestañas); la base de prueba quedó con datos de las pruebas manuales (cada test la vacía). Archivos temporales en `/tmp/qa-*` y `/tmp/qa-t001/`, fuera del repo. El repo quedó sin cambios salvo este reporte.

## Split-outs sugeridos (fuera del alcance)
- Ninguno.
