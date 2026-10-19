# QA T-008 — Ronda 1

**Verdict: PASS**
**Branch:** feat/t-008-celdas-en-mcp @ 19ed15a
**Gates:** ruff check ✓ · ruff format --check ✓ (64 archivos) · pytest ✓ (223 passed en 20,3 s, ninguno salteado; `TEST_DATABASE_URL` apuntando a la base `craftech_test` de un PostgreSQL 16 propio de QA creado con los scripts de `infra/postgres-init/`) · build de la imagen ✓ (`docker build -f infra/Dockerfile`). El repo no tiene chequeo de tipos.
**Criteria:** 7/7 verificados. En el criterio 1, la comparación con Google Sheets se hizo sobre celdas de planillas reales de la base local, porque la planilla de prueba de Ariel no está cargada. Lo único sin probar es la interfaz de Claude Desktop.
**Mutation:** 12 mutantes. 9 hacen fallar la suite. Sobreviven 3: dos son huecos de test menores (F1 y F2) y el tercero es una defensa que ya cubre otra capa (ver "Mutación").

## Cómo se probó

- Leí todo el diff: `0007_mcp_cells.sql`, `server.py`, `test_mcp.py`, `test_db.py` y `docs/claude-desktop.md`. Comparé el cálculo de la vista con `build` de `app/craftech_os/ingest/document.py`: `r` y `c` son base 0 y ya incluyen el desplazamiento `startRow`/`startColumn` del bloque. También lo comparé con `a1()` de `app/craftech_os/diff/compare.py`.
- **PostgreSQL 16 propio para QA** (`127.0.0.1:55438`, borrado al terminar): los tests y las sondas con datos sintéticos corrieron ahí.
- **Base local real**, solo lectura en la práctica. Abrí una transacción como superusuario, apliqué la `0007` dentro, pasé a `SET LOCAL ROLE mcp_reader` con `statement_timeout = 10s`, medí y la deshice con `ROLLBACK`. Después verifiqué que `mcp.celdas` no existe en la base.
- **Google Sheets**, leído con la cuenta de servicio y el alcance `spreadsheets.readonly`. No escribí nada. A la consola y a este informe salieron solo coordenadas y hashes MD5, nunca el contenido de una celda.

## Criterios

1. ✓ **Búsqueda por texto y referencia A1 contra Google Sheets.**
   - Con `consultar_sql` sobre datos sintéticos, `texto ILIKE '%ficticio%'` devuelve la celda con `planilla`, `pestaña`, `celda` y `leido_en` (test `test_celdas_has_the_cells_of_the_last_read_with_their_a1_reference`).
   - Contra Google Sheets: tomé al azar 30 celdas con texto de la vista aplicada sobre la base local real. Eran 8 de columnas mayores que Z, entre ellas una de tres letras (`AIO`); 8 de filas mayores que 100, hasta la 19.748; y 14 al azar. Para cada una pedí a la API de Sheets el valor mostrado en esa misma referencia A1 y comparé el MD5 con el de `texto`. **29 de 30 coinciden.**
   - La que no coincide es D12573. Bajé la pestaña entera y la comparé celda por celda contra la última lectura. Sin desplazamiento coinciden 63.159 celdas. Corridas una fila coinciden unas 47.000, en los dos sentidos, por los valores repetidos. Corridas una columna coinciden **0**. La pestaña viva tiene 180 celdas más que la lectura. Conclusión: la celda cambió en la planilla después de la lectura; la referencia A1 está bien. Ver el split-out.
   - Para todas las columnas posibles, de A a ZZZ, la vista da lo mismo que `a1()` (`test_celdas_spells_every_sheets_column_like_google`). En los datos reales hay 25.210 celdas con columnas de tres letras, así que esa rama del `CASE` no es teórica.
2. ✓ **Solo la última lectura de cada pestaña activa.** El test arma dos lecturas de la misma pestaña y una pestaña inactiva con el mismo texto, y solo aparece la lectura nueva. Los mutantes que quitan `AND t.active` o invierten el orden de `read_at` hacen fallar la suite. Sobre los datos reales, la vista cubre 342 pestañas distintas, el número esperado según el ticket.
3. ✓ **Tiempo como `mcp_reader` con datos locales**, con `statement_timeout = 10s`:
   - `texto ILIKE '%grego%'`: 165 celdas en 1.405 ms.
   - Un texto que no existe (recorre todo): 0 celdas en 1.455 ms.
   - `count(*)` de la vista: 3.277.546 celdas en 939 ms.
   - Un agregado con filtros sobre toda la vista: 1.638 ms.

   Coincide con lo que anotó implement en `## Implementation`. `consultar_sql` usa un cursor del lado del servidor (`fetchmany(501)`), así que un `SELECT *` sin `LIMIT` no trae los 3,2 millones de filas al proceso.
4. ✓ **Catálogo.** Leí `craftech://catalogo` desde el servidor construido sobre la base de QA: aparece `## mcp.celdas` con el comentario de la vista y las 12 columnas, cada una con su tipo y su comentario en español.
5. ✓ **`mcp_writer` recibe un error de permisos.** El test da `InsufficientPrivilege` al leer `mcp.celdas`. Además, `mcp_writer` no tiene `USAGE` sobre el esquema `mcp`; `mcp_reader` sí lo tiene.
6. ✓ **Instrucciones y documentación.**
   - Las instrucciones del servidor nombran `mcp.celdas` y `consultar_sql`; hay un test, y el mutante que borra la frase lo hace fallar.
   - `docs/claude-desktop.md` usa `<docker>` con el paso `which docker`. `/usr/local/bin/docker` queda solo como un lugar habitual, sin darlo por hecho.
   - El documento agrega la pregunta de ejemplo sobre contenido y la mención de `texto` en las defensas contra instrucciones escondidas.
7. ✓ **Ningún dato real en tests, fixtures ni logs.** Los fixtures son sintéticos ("Proveedor Ficticio", "en AA", "viejo") y el diff no trae archivos de datos. Mis sondas sobre datos reales imprimieron solo coordenadas, conteos y hashes. Los archivos temporales (`/tmp/t008qa`) ya están borrados.

## Pasada adversaria

- **Forma del JSON**: las 598 lecturas de la base local tienen `content->'rows'` como arreglo. No hay ninguna fila con `cells` que no sea un arreglo ni con `r` que no sea un número. El caso que rompería la vista ("cannot extract elements from a scalar") no existe hoy, y `build` no lo genera.
- **`valor`**: en los datos reales, 3.263.190 celdas tienen un objeto y 14.356 tienen NULL de SQL (las celdas que solo tienen color). `jsonb_typeof` las devuelve vacías, no `'null'`, así que el `nullif` funciona sobre datos reales.
- **Inyección por `consultar_sql`**: `SELECT * FROM mcp.celdas; DROP VIEW mcp.celdas` se rechaza con "Una sola sentencia por consulta". Además, `mcp_reader` corre en una transacción de solo lectura (verificado en T-007).
- **Blast radius**: `server.py` cambia solo el texto de las instrucciones (la suite completa pasa) y `test_db.py` lista una migración más. La vista no toca tablas.
- **Complejidad**: nada sobra. Hay una migración, una frase y tests; no se agregaron dependencias ni herramientas.

## Mutación

Apliqué cada mutante a mano, corrí `pytest app/tests/test_mcp.py app/tests/test_db.py` y lo revertí con `git checkout`. Al final, `git status` quedó limpio.

| Mutante | Resultado |
|---|---|
| sin `AND t.active` | rojo ✓ |
| `read_at ASC` (la lectura más vieja) | rojo ✓ |
| fila base 0 en `celda` | rojo ✓ |
| letra de dos columnas corrida (`chr(65 + c/26)`) | rojo ✓ |
| primera letra de tres columnas mal calculada | rojo ✓ |
| sin `GRANT ... TO mcp_reader` | rojo ✓ |
| `formula` siempre nula | rojo ✓ |
| sin `COMMENT ON COLUMN mcp.celdas.texto` | rojo ✓ |
| sin la frase de `mcp.celdas` en las instrucciones | rojo ✓ |
| `GRANT SELECT ... TO mcp_reader, mcp_writer` | verde. No es un hueco: `mcp_writer` no tiene `USAGE` sobre el esquema `mcp`, así que igual recibe "permission denied". El criterio se cumple por esa capa. |
| sin `nullif` en `valor` | verde (F1) |
| sin `id DESC` como desempate | verde (F2) |

## Findings

### F1 [minor] Ningún test distingue el `nullif` de `valor`
- **Repro:** cambiar `nullif(cell->'value', 'null')` por `cell->'value'` en `0007_mcp_cells.sql` y correr `pytest app/tests/test_mcp.py`: pasa.
- **Expected:** que un test falle, porque `## Implementation` dice que el `nullif` existe para que `valor IS NULL` funcione. **Actual:** el test lee `valor` desde Python, y psycopg convierte el `null` de JSON en `None` igual que un NULL de SQL. La diferencia solo se ve en SQL: `WHERE valor IS NULL` o `jsonb_typeof(valor)`.
- El comportamiento es correcto sobre los datos reales (ver la pasada adversaria). Falta el test que lo fije, por ejemplo `SELECT count(*) FROM mcp.celdas WHERE valor IS NULL` = 1 en el fixture que ya tiene la celda C1, la que solo tiene color.

### F2 [nit] El desempate por `id` de dos lecturas con el mismo `read_at` no tiene test
- Implement ya lo declaró como punto ciego en `## Test plan`. El mutante que quita `id DESC` sobrevive. El riesgo es bajo, porque el worker no guarda dos lecturas de la misma pestaña en el mismo instante. Se registra para que quede a la vista.

## Re-verificación de la ronda anterior

No aplica: es la ronda 1.

## No verificado

- **Claude Desktop real** (puntos 5 y 7 del `## Test plan`): no hay interfaz de Claude Desktop en este entorno. El catálogo y `consultar_sql` se probaron llamando al servidor directamente. Queda para Ariel después del `## Post-merge`.
- **La planilla de prueba de Ariel**: no está en `config/sources.yaml` ni en la base. La comparación A1 se hizo con 30 celdas de planillas reales, como se describe en el criterio 1.
- **Tiempo con la migración aplicada de verdad en `main`**: se midió con la `0007` aplicada dentro de una transacción que después se deshizo. Con la migración aplicada debería dar lo mismo, porque una vista no materializada no guarda nada.

## Split-outs sugeridos (fuera del alcance)

- [data-integrity] En una pestaña real, la última lectura (18-oct-2026 22:54 UTC) difiere de la planilla viva en unas 11.000 celdas, y la planilla viva tiene 180 celdas más. Aun así, `modifiedTime` en Drive (9-oct-2026) es anterior a esa lectura. O bien la planilla cambió sin que `modifiedTime` se moviera, o bien el worker no está viendo cambios que debería. Hay que investigar cómo decide el worker cuándo releer. No afecta a T-008: la vista muestra fielmente lo que se guardó. Pero `mcp.celdas` dice "contenido actual", así que lo que muestra puede estar más viejo de lo que parece. Repro: comparar celda por celda, con hashes, la última lectura de cada pestaña contra `values.get` de la API de Sheets, y quedarse con las pestañas que difieren aunque su `modifiedTime` sea anterior a `read_at`. Así aparece la pestaña de la celda D12573 de la muestra. No anoto la planilla ni la pestaña para no dejar datos reales en el informe.
