# QA T-001 — Ronda 2

**Verdict: PASS**
**Branch:** arielvinas/t-001-andamiaje @ 5dc0a41
**Gates:** typecheck — (el proyecto no tiene uno) · lint ✓ (`ruff check`, `ruff format --check`) · tests ✓ (sin `TEST_DATABASE_URL`: 26 pasan, 12 se saltean con el motivo; con la base `_test`: 38 pasan; apuntando a la base principal: 12 errores "its name must end in _test" y la base principal sigue con sus 20 planillas) · build ✓ (`docker compose build app`)
**Criteria:** 8/8 verificados (el del `git grep` en su redacción nueva, acotada a las rutas del ticket)
**Mutation:** 9 mutantes a mano (harness `/tmp/qa2/mutants.py`, falla fuerte si un patrón no aparece exactamente una vez): revertir cada arreglo de la ronda 1 (F1, F2, F3 ×3, F6) pone la suite roja, y cada mutante muere por el test nuevo que le corresponde. Sacar el `pg_advisory_lock` hace fallar el test de concurrencia 5 de 5 veces. Sobrevive uno: sacar la guarda `_test` de `conftest.py` (ver F3 abajo).

No hay UI: el paso de "navegador real" se reemplazó por ejercitar la CLI dentro del contenedor y con `uv run` desde la laptop, y por consultar PostgreSQL directamente. Ninguna llamada a Google.

## Criterios, uno por uno (volumen recreado con `down -v`)

1. **PostgreSQL 16 solo en 127.0.0.1 con lz4.** `docker compose port postgres 5432` → `127.0.0.1:5432`; `lsof -nP -iTCP:5432 -sTCP:LISTEN` solo muestra `127.0.0.1:5432`; `SHOW default_toast_compression` → `lz4`; `version()` → 16.15. `craftech_app`: `rolsuper`, `rolcreaterole`, `rolcreatedb` en `f`, dueño de `craftech` y `craftech_test`. ✓
2. **`migrate`.** Primera corrida "applied 0001_sources.sql", segunda "nothing to apply", ambas salida 0. Con una línea agregada a `0001_sources.sql` y `build app`: salida 1, `error: migration 0001_sources.sql changed after it was applied`. Revertido y reconstruido: "nothing to apply". ✓
3. **Comentarios en español.** `col_description` de las 23 columnas de las cuatro tablas y `obj_description` de las cuatro tablas: todos con texto en español, ninguno nulo. ✓
4. **`sources load`.** Dos corridas en el contenedor: `source` 20, `source_tab` 244 (244 activas), 12 `A_CONFIRMAR`; `drive_id` y `sheet_id` todos nulos. ✓
5. **`sources list`.** 20 planillas con conteo por clase, las nueve `all_tabs` dicen "all tabs DERIVADA", termina en "20 sources". ✓
6. **`uv run pytest` y `uv run ruff check`.** Ver Gates. ✓
7. **`git grep` de secretos** sobre `app config infra pyproject.toml README.md uv.lock`: vacío. `git check-ignore -v infra/.env` → `.gitignore:2:.env`; `infra/.env.example` con las cuatro variables vacías. En la imagen no hay ningún `.env` ni archivo `*service-account*`. ✓
8. **Dentro y fuera del contenedor.** `sources list` en el contenedor y con `uv run` desde la laptop (`DATABASE_URL` a `127.0.0.1`): `diff` vacío. En el contenedor corre como `craftech` (no root); `pg_dump --version` → 16.15. ✓

## Re-verificación de la ronda anterior

- **F1 (r1, major): ✓ resuelto.** `A:{CARGA:[x]}` + `B:{CARGA:[y]}` → solo `A`: `B|y|CARGA|f`, `sources list` muestra `'B': ` sin conteos. Volver a poner `B` la reactiva. Test nuevo `test_removed_source_deactivates_all_its_tabs`.
- **F2 (r1, minor): ✓ resuelto.** Base de prueba vacía, dos `uv run craftech-os migrate` en paralelo, 3 de 3: ambos salida 0, uno "applied", el otro "nothing to apply". Con una migración `0002` con SQL roto: la transacción se revierte (la tabla creada antes del error no queda), solo `0001` queda registrada, y el lock asesor se libera (otra conexión lo toma con `pg_try_advisory_lock`).
- **F3 (r1, minor): ✓ resuelto** para los tres casos: `--file /nonexistent.yaml` → `error: [Errno 2] No such file or directory`; `sources: [` → `error: invalid YAML: ...`; `DATABASE_URL=garbage` → `error: DATABASE_URL is not a valid connection string`. Todos salida 1, sin traceback. Además: un directorio como `--file`, contraseña incorrecta, puerto cerrado y una cadena `key=value` inválida también dan `error: ...` de una línea; ninguno imprime la contraseña. Queda un caso de la misma clase: ver F1 abajo.
- **F4 (r1, minor): ✓ resuelto.** `TEST_DATABASE_URL` a la base principal: la fixture falla antes de tocar nada, la base principal sigue con 20 planillas. README lo explica.
- **F5 (r1, minor): ✓ resuelto.** El criterio quedó acotado a las rutas del ticket, con la razón escrita; da vacío.
- **F6 (r1, nit): ✓ resuelto.** `A:{CARGA:[x]}` → `A: all_tabs: DERIVADA`: `sources list` muestra `'A': all tabs DERIVADA; DERIVADA 1`.

## Findings

### F1 [minor] Un `sources.yaml` que no es UTF-8 sale con traceback
Misma clase que F3 de la ronda 1 (errores esperables con traceback en vez de `error: ...`): `UnicodeDecodeError` es `ValueError`, no `OSError`, y no está en el `except` de `cli.main`.
- **Repro:** `printf 'sources:\n- {title: "Facturaci\xf3n", tabs: {CARGA: [x]}}\n' > /tmp/latin1.yaml` → `uv run craftech-os sources load --file /tmp/latin1.yaml`.
- **Expected:** `error: ...` de una línea, salida 1. **Actual:** salida 1 (no se traga nada, la base no cambia) pero con traceback completo terminando en `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xf3`.
- Es probable si alguien guarda el archivo desde un editor en Latin-1 (los títulos tienen tildes: "Facturación"). Arreglo de una línea: envolverlo como `SourcesError` en `cmd_sources_load` o sumar `UnicodeDecodeError` a la lista. Como es la segunda vez que aparece esta clase, candidata a línea de guideline ("todo error de entrada esperable de la CLI tiene un test que pide `error:` sin traceback").

### F2 [minor] Una planilla `all_tabs` que sale del YAML y vuelve queda con todas sus pestañas inactivas
Efecto lateral del arreglo de F1 (r1). Al sacar la planilla, sus pestañas quedan `active = false` (correcto); al volver a ponerla como `all_tabs`, `load` les actualiza la clase pero no las reactiva. En una planilla con `tabs`, en cambio, las nombradas se reactivan.
- **Repro:** `A: all_tabs: DERIVADA` cargada, con una pestaña dada de alta "al leer" (simulada con un `INSERT` en `source_tab`) → `sources load` sin `A` → `sources load` con `A` otra vez → `A|read-tab|DERIVADA|f` y `sources list` muestra `'A': all tabs DERIVADA` sin conteos.
- **Por qué importa poco hoy:** no se pierde nada (las filas se conservan) y hoy no hay pestañas dadas de alta al leer. El caso concreto es "P&L GEN AI - DATA" (`all_tabs`, en la papelera de Drive): si sale y vuelve, depende de que T-002 reactive las pestañas al leer. Opciones: que `load` reactive las pestañas de una planilla `all_tabs` presente en el YAML, o dejarlo escrito para T-002. Para el runner/coordinador.

### F3 [nit] La guarda `_test` de la fixture no tiene test que la cubra
Sacar el `if not conn.info.dbname.endswith("_test")` de `conftest.py` deja la suite verde. Se verificó a mano que funciona (ver F4 r1). Testear la propia fixture es más ceremonia que valor; se anota para que no se pierda si alguien la refactoriza.

### F4 [nit] `sources load` con `sources: []` desactiva todas las pestañas y termina en 0
Coherente con la regla ("lo que no está en el YAML queda inactivo") y reversible (volver a cargar el archivo real las reactiva), pero un archivo vacío por error apaga todo sin aviso. No pide cambio en este ticket; a lo sumo un aviso cuando la lista está vacía.

## Adversarial (sin hallazgos)
- Nombres con `<script>`, `'; DROP TABLE source; --`, unicode con emoji y 1500 caracteres: se guardan tal cual (consultas parametrizadas), sin efectos laterales.
- Validación del YAML: `tabs` y `all_tabs` juntos, clase inexistente, título repetido, pestaña repetida entre clases, nombre numérico, lista vacía, `all_tabs: null`, clave desconocida, archivo vacío, raíz equivocada, título solo con espacios: todos salida 1 con mensaje claro. Un tag `!!python/object/apply:os.system` se rechaza (`safe_load`).

## No verificado
- Títulos y nombres de pestañas contra Google Drive: QA no llama a Google; se confía en la lectura de metadatos de `## Decisions` (igual que en la ronda 1).
- Typecheck: el proyecto no tiene uno configurado.

## Estado en que queda la máquina
PostgreSQL del Compose corriendo con el volumen `craftech-os_db` recreado: base principal migrada y cargada (20 planillas, 244 pestañas, todas activas); la base de prueba quedó con datos de las pruebas manuales (cada test la vacía). Imagen `craftech-os-app` reconstruida desde el código de la rama. Temporales en `/tmp/qa2/` y `/tmp/qa2-*`, fuera del repo. El repo quedó sin cambios salvo este reporte.

## Split-outs sugeridos (fuera del alcance)
- Ninguno. F2 se puede resolver acá o dejar como nota para T-002.
