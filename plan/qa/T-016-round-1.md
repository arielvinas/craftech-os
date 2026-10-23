# QA T-016 — Ronda 1

**Verdict: PASS**
**Branch:** arielvinas/t-016-fundings-corte-por-cobro @ 57d12db
**Gates:** lint ✓ (`ruff check`) formato ✓ (`ruff format --check`) tests ✓ (314 passed, 0 skipped, con `TEST_DATABASE_URL`) · sin typecheck ni build configurados en el repo
**Criteria:** 8/8 verificados
**Mutation:** 9 mutantes, 9 muertos (detalle abajo); revertir el corte a fecha de carga deja la suite roja ✓

## Cómo se probó

- Diff completo leído contra `main` (`interpret/fundings.py`, `mcp/server.py`, `0013_fundings_collection_cut.sql`, tests).
- Datos reales: copia descartable de la base local (`pg_dump` de `craftech_os` a `craftech_qa_t016`, borrada al terminar). Primero `migrate` + `interpret --all` con el código de `main` (exportado con `git archive`), después con el de la rama, dos veces seguidas, y vuelta atrás a `main` para comparar el conjunto de celdas.
- Web: `craftech-os web` contra la copia; `/fundings` responde 200 y muestra las dos filas nuevas. No hay captura de pantalla: con datos reales tendría nombres de clientes y montos, que no pueden entrar a `plan/` (`plan/guidelines/code.md`); el ticket no cambia ninguna pantalla.

## Criterios, uno por uno

1. Fila cargada en enero de 2026 con "Fecha de pago" en junio de 2026 → hito tracker en junio y suma en `mcp.paridad_fundings_aws` de junio: ✓ (test nuevo, fila "Pagado En Junio"; con datos reales, celdas I14 e I19 del log).
2. Cargada en enero, sin "Fecha de pago", sign-off 5/3/2026 → hito con cobro estimado 4/4/2026: ✓ (test).
3. "Fecha de pago" en enero de 2026, cargada el 25/2/2026 y con sign-off en mayo → sin hito: ✓ (test; el mutante que invierte la prioridad pago/sign-off muere).
4. Sin fecha de pago ni sign-off: cargada antes del 25/2/2026 → sin hito y un `fila_sin_interpretar` con `reason` y `cell_ref` en la celda de "Fecha de pago"; cargada el 25/2/2026 o sin fecha de carga → hito: ✓ (test; los tres mutantes de esta rama mueren). Bordes 28/2 (sin hito) y 1/3 (hito) del cobro estimado cubiertos.
5. Datos reales: la diferencia de junio de 2026 de "Facturación - Craftech Total" en `mcp.paridad_fundings_aws` pasa a 0 con la rama; ningún otro mes cambia. El log pasa de 95 a 97 hitos (agrega I14 e I19, no saca ninguno), Pagos sigue con 113. Problemas: un `alias_sin_cliente` más (el texto de esas filas), ningún `funding_duplicado` nuevo, ninguna fila real cae en el problema nuevo `:cobro`. Coincide con lo que dice `## Implementation`. ✓
6. Idempotencia: `interpret --all` dos veces sobre datos reales deja `mcp.fundings` y `mcp.issues` (id, tipo, estado, celda, detalle) idénticos (hash igual); también en el test. ✓
7. `grep -rn "pendiente de ratificar por Emi y Ro" app/` → solo cuatro líneas de `0012_cei_aws_parity.sql`. `obj_description` de `funding_milestone`, `mcp.fundings`, `mcp.paridad_fundings_aws` y `mcp.paridad_fundings` en la copia migrada no contienen "ratificar por Emi". ✓
8. `0012_cei_aws_parity.sql` sin cambios respecto de `main`; su sha256 (`d72df920…`) es el mismo que guarda `schema_migration` en la base local, y `migrate` aplicó solo la 0013 sin quejarse del checksum. ✓

## Mutación

Harness en el scratchpad (`/tmp/qa-t016/mutants.py`; falla si un archivo o patrón no existe y sale con error si sobrevive uno). Corre `test_fundings.py`, `test_mcp.py` y `test_db.py`:

| Mutante | Resultado | Lo mata |
|---|---|---|
| Volver al corte por fecha de carga | muerto | test nuevo del corte |
| Febrero fuera del corte (`<=` → `<`) | muerto | test nuevo (borde 28/2) |
| Sign-off manda sobre "Fecha de pago" | muerto | test nuevo |
| Fila sin fechas cargada antes del corte no abre problema | muerto | test nuevo |
| Esa fila además da hito (sin `continue`) | muerto | test preexistente del 25/2 (con `-x`; el nuevo también la excluye) |
| Filas sin fechas y sin fecha de carga descartadas | muerto | test nuevo |
| Corte solo por "Fecha de pago" | muerto | test nuevo |
| 0013 vacía | muerto | test nuevo de descripciones |
| Glosario con CEI todavía pendiente | muerto | `test_mcp` ajustado |

## Findings

### F1 [minor] "Fecha de pago" escrita como texto decide el lado en silencio
- **Repro (por lectura de `interpret/cells.py:14-24` y `interpret/fundings.py:92-96`):** una fila del log con "Fecha de pago" como texto (por ejemplo `10/06/2026` sin formato de fecha) y sign-off estimado en enero de 2026. `day()` devuelve None para el texto, el cobro sale del sign-off (febrero) y la fila se descarta sin ningún problema abierto.
- **Expected:** que una fecha ilegible en la celda que decide el corte se vea (un problema con la celda), o al menos un test que fije el comportamiento elegido. **Actual:** se trata como vacía, como dice el ítem 7 del `## Test plan`, pero ese ítem no tiene test y no queda rastro. Con los datos reales de hoy no pasa (ninguna fila cambió de lado salvo I14 e I19, que tienen fechas legibles). Es la misma clase que ya existía con "Fecha De Carga En Fp" antes del ticket, por eso no es `major`.

## Re-verificación de la ronda anterior

- Primera ronda: no aplica.

## No verificado

- Captura de la pantalla de fundings: no se guarda por los datos reales (ver arriba); la página respondió 200 y lista las dos filas nuevas.
- Ratificación de Ro del criterio de corte: es de producto, ya registrada como pendiente en la regla R28, el glosario y los COMMENT.

## Split-outs sugeridos (fuera del alcance)

- [silent-data] Fechas del log escritas como texto ("Fecha de pago", "Fecha De Carga En Fp", sign-off) se leen como vacías sin abrir problema; ver F1.
