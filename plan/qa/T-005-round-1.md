# QA T-005 — Ronda 1

**Verdict: PASS**
**Branch:** arielvinas/t-005 @ 6ac2613
**Gates:** ruff check ✓ · ruff format --check ✓ (57 archivos) · pytest ✓ (188 passed, con `TEST_DATABASE_URL` apuntando a un PostgreSQL 16 descartable de QA en `127.0.0.1:55436`, borrado al final) · ningún test llama a Google
**Criteria:** 9/10 verificados (1, 2, 4, 5, 6, 7, 8, 9, 10). El criterio 3 necesita una edición real de Ariel en su planilla de prueba y es un paso posterior al merge (ver "No verificado").
**Mutation:** 19 mutantes sobre `attribution.py`, `ingest/drive_activity.py`, `ingest/google.py`, `worker.py`, `cli.py` y la migración `0005_drive_activity.sql`. Los 19 hacen fallar la suite, y en cada caso falla el test que corresponde a la regla mutada (detalle abajo). No sobrevive ninguno.

## Cómo se probó

- Leí el diff completo contra `main`: la migración, `attribution.py`, `ingest/drive_activity.py`, `ingest/google.py`, `worker.py`, `cli.py`, `web/queries.py` y `test_drive_activity.py` (21 tests).
- Repetí la importación real yo mismo, en una base descartable de QA (`craftech_qa_real`): migrar, cargar las 20 fuentes, `craftech-os drive import` dos veces. Solo lectura sobre Google: Drive Activity y metadatos de Drive. No escribí en ninguna planilla ni en Drive.
- Escribí una sonda propia, de solo lectura, que compara para cada una de las 20 planillas la hora de última modificación del archivo (`modifiedTime` de Drive) con la hora de su última actividad de edición según Drive Activity. La crucé con las versiones que leyó el worker en la base local de desarrollo (solo lectura; copié 22 pares de identificador de archivo y hora de versión, sin contenido).
- Este reporte muestra solo conteos, horas y números de fuente; nunca nombres, identificadores de persona ni valores de celdas.

## Medido en la importación real (19-oct-2026)

- 20 planillas, **63.159 actividades** (el implementador midió 63.150 horas antes; la diferencia son ediciones nuevas). Primera corrida: 5 min 18 s. **Segunda corrida: 0 actividades nuevas en las 20 planillas, 23 s.**
- "FUNDINGS - Log de status [OFICIAL]": **1.154 actividades**, del 16-mar-2026 al 19-oct-2026, **13 actores distintos**. Coincide con lo anotado en `## Implementation`.
- 23 actores en total. `v_editor` dio el mismo resultado (mismo hash de las filas) en dos consultas seguidas. En FUNDINGS se ven "editor sin identificar #1" a "#3", "#7" a "#15" y "usuario eliminado": 13 etiquetas.
- Tipos de acción: 63.074 `edit`, 25 `rename`, 20 `create`, 14 `permissionChange`, 14 `dlpChange`, 11 `move` y 1 `delete`.
- 0 actividades duplicadas por contenido, 0 con más de un actor y 0 con `timeRange` (todas traen `timestamp`).
- Los 40 `system_event` de tipo `activity_read` tienen solo las claves `inserted`, `through` y `latest`. Ni ellos ni la salida de las dos corridas contienen `@` ni `people/`. La salida de `craftech-os editors` (24 líneas) no contiene direcciones de correo.

## Criterios

1. ✓ La importación termina sobre las 20 planillas reales. FUNDINGS tiene 1.154 filas desde el 16-mar-2026, y la segunda corrida agrega 0.
2. ✓ Hay 13 actores distintos en FUNDINGS. La decisión del 19-oct ajusta el "del orden de 8" a lo medido y pide numerarlos a todos. La numeración es estable en dos consultas seguidas. Como el alcance pide un número global por orden de primera aparición ("un backfill posterior de otra planilla no renumera"), los números de FUNDINGS no son consecutivos; el ticket lo deja documentado.
3. ⚠ No verificado: requiere una edición real en la planilla de prueba (ver "No verificado").
4. ✓ `test_two_editors_are_una_de_and_none_is_sin_datos` pasa: dos actores dan `una_de` con ambos identificadores y `attributed_at` nulo, y ninguno da `sin_datos`. El mutante "un solo editor da `una_de`" lo detecta `test_one_editor_in_the_window_is_cierta_at_their_last_edit`.
5. ✓ `test_the_latest_editor_profile_wins` pasa. El mutante "gana la primera fila" lo hace fallar.
6. ✓ `test_annotation_accepts_only_the_four_entity_types` pasa, con la restricción `CHECK` en la base. El mutante que la quita lo hace fallar.
7. ✓ `test_attribution_stats_per_source_and_day` pasa. La vista calcula el total de cambios y el porcentaje `cierta` por planilla y por día. El mutante que cambia el cálculo del porcentaje lo hace fallar.
8. ✓ La migración no agrega ni cambia columnas de `cell_change`, solo reescribe tres comentarios. Lo verifica `test_cell_change_columns_are_unchanged`.
9. ✓ El test de no filtración pasa. En la corrida real, los eventos y la salida no contienen nombres ni correos (ver arriba).
10. ✓ `uv run pytest` (188) y `ruff check` en limpio. Google está simulado en toda la suite.

## Prueba de mutación

Cada mutante se aplicó solo, con `pytest -x`, y el archivo se restauró después; `git status` quedó limpio. Los 19 mutantes, con el test que los detectó:

- Un solo editor da `una_de`; sin el margen de 5 minutos; contar cualquier tipo de acción; el inicio de la ventana inclusivo; `attributed_at` en la primera edición en vez de la última → `test_one_editor_in_the_window_is_cierta_at_their_last_edit`.
- No esperar a que pase el margen; volver a atribuir lo ya atribuido → `test_a_change_waits_until_activity_after_its_margin_was_read`.
- Mirar la actividad de cualquier planilla → `test_attribution_only_looks_at_the_changes_source`.
- Numerar por `actor_id` en vez de por primera aparición; insertar de la más nueva a la más vieja → `test_every_actor_is_numbered_by_first_appearance_and_stays_numbered`.
- Gana la primera fila de `editor_profile` → `test_the_latest_editor_profile_wins`.
- Sin la restricción de `annotation` → `test_annotation_accepts_only_the_four_entity_types`.
- Porcentaje mal calculado en `v_attribution_stats` → `test_attribution_stats_per_source_and_day`.
- Lectura incremental sin los 10 minutos de margen → `test_a_later_fetch_starts_ten_minutes_before_the_latest_known_activity`.
- Leer solo la primera página → `test_drive_import_reads_every_page_and_a_rerun_adds_nothing`.
- El worker no lee la actividad de las planillas leídas en la vuelta, no lee una vez por hora, o nunca atribuye → `test_the_worker_fetches_activity_and_attributes_once_the_margin_passed`.
- `drive import` no atribuye lo pendiente al final → `test_drive_import_attributes_pending_changes_at_the_end`.

## Findings

### F1 [minor] Una edición real quedó con hora de Drive 10 minutos después de la última modificación del archivo, el doble del margen de 5 minutos
- **Evidencia (sonda de solo lectura, 19-oct-2026):** la fuente 12 tiene `modifiedTime` a las 02:19:32 UTC, y el worker leyó esa versión a las 02:24. Drive Activity registra dos ediciones del mismo actor: una a las 02:19:31 y otra a las 02:29:31, sin ninguna modificación posterior del archivo. Las otras planillas modificadas hace poco muestran desfases de 0 a 3 minutos entre la modificación y la última edición, que coinciden con lo que motivó la decisión del 19-oct.
- **Por qué no rompe nada hoy:** en este caso la edición de las 02:19:31 cae dentro de la ventana y el actor es el mismo, así que el cambio sale `cierta` con la hora correcta. La edición de las 02:29:31 no corresponde a ningún cambio.
- **Riesgo:** la decisión del 19-oct promete que la regla "nunca da cierta a la persona equivocada". Una edición sellada más de 5 minutos tarde cae en la ventana del cambio siguiente. Supongamos que la persona A edita, la persona B edita la misma planilla menos de 10 minutos después, y la edición de B también se sella más de 5 minutos después de su versión. Entonces el cambio de B tiene en su ventana solo la edición tardía de A y sale `cierta` para A. Si la edición de B sí cae a tiempo, el resultado es `una_de`: se pierde precisión, pero no es un error. No pude reproducir el caso de punta a punta: haría falta que dos personas editen en vivo.
- **Esperado:** la implementación cumple la decisión tal como está escrita. Lo que falta saber es si 5 minutos alcanzan.
- **Sugerencia:** después del merge, con el worker y la importación corriendo sobre la base real, medir durante una semana cuántas ediciones quedan con hora más de 5 minutos después de la versión que las contiene. Si no es un caso aislado, preguntarle a Ariel si ensanchar el margen (por ejemplo, a 15 minutos), a cambio de atribuir más tarde.

### F2 [nit] `parse` toma solo el primer actor de cada actividad
- **Evidencia:** `ingest/drive_activity.py` usa `actors[0]`. En las 63.159 actividades reales no hay ninguna con más de un actor, así que hoy no afecta ningún resultado.
- **Esperado:** que la elección quede escrita, con un comentario o un test, para que no sea un supuesto silencioso. La actividad entera queda en `raw`, así que no se pierde nada.

## No verificado

- **Criterio 3 (paso posterior al merge, legítimo):** una edición de Ariel en su planilla de prueba seguida de la vuelta del worker tiene que dejar el `cell_change` en `cierta`, con su identificador y la hora de Drive. Un agente nunca escribe en Sheets. La lógica está cubierta por `test_one_editor_in_the_window_is_cierta_at_their_last_edit` y por el test del worker, y la importación real trae el `actor_id` y la hora de cada edición. Es el paso 5 de `## Post-merge`.
- **Demora de publicación en Drive Activity:** la condición para atribuir es `window_end + 5 min < through`, y `through` es la hora en que empezó la lectura. Si Google publicara una edición varios minutos después de su hora, una lectura hecha justo después del margen no la vería, y el cambio podría salir `sin_datos`, o `cierta` para otra persona si había alguien más en la ventana. La sonda no observó ediciones nuevas mientras corría, así que no pude medir esa demora. Conviene revisarla junto con la medición sugerida en F1.
- **Pantalla Cambios de la web con nombres:** queda para T-006 y T-007, fuera de alcance.

## Split-outs

- Ninguno obligatorio. Sugerido: medir, después del merge, el desfase entre la hora de Drive de cada edición y la versión leída (F1), y la demora de publicación de Drive Activity. Si resulta frecuente, llevar a Ariel la pregunta de ensanchar el margen de 5 minutos.
