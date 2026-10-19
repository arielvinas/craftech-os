CREATE TABLE drive_activity (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id    bigint NOT NULL REFERENCES source (id),
    activity_at  timestamptz NOT NULL,
    actor_id     text NOT NULL,
    action_type  text NOT NULL,
    raw          jsonb NOT NULL,
    content_hash text NOT NULL UNIQUE CHECK (content_hash ~ '^[0-9a-f]{64}$')
);

CREATE INDEX drive_activity_source_at ON drive_activity (source_id, activity_at);

COMMENT ON TABLE drive_activity IS 'Actividad de Google Drive sobre una planilla (Drive Activity API): quién hizo qué y cuándo, tal como lo informa Google. Es la base de la atribución de cada cambio. Trae identificadores de editor, nunca nombres ni valores de celdas. Solo se agregan filas; cada actividad se guarda una sola vez.';
COMMENT ON COLUMN drive_activity.id IS 'Identificador interno de la actividad. Su orden define la numeración de los editores sin identificar (ver v_editor).';
COMMENT ON COLUMN drive_activity.source_id IS 'Planilla sobre la que ocurrió la actividad.';
COMMENT ON COLUMN drive_activity.activity_at IS 'Momento de la actividad según Google. Google agrupa ediciones seguidas en tandas de unos tres minutos y les pone una hora uno o dos minutos posterior a la modificación.';
COMMENT ON COLUMN drive_activity.actor_id IS 'Quién la hizo: el identificador opaco de Google (people/...), o deletedUser para cualquier cuenta eliminada (todas cuentan como un único actor). Otros tipos de actor sin identificador (unknownUser, administrator, anonymous, system) se guardan con ese nombre.';
COMMENT ON COLUMN drive_activity.action_type IS 'Tipo de acción según Google: edit (edición del contenido), permissionChange, rename, comment, create, move, etc. Solo edit cuenta para la atribución.';
COMMENT ON COLUMN drive_activity.raw IS 'La actividad tal como la devolvió Google.';
COMMENT ON COLUMN drive_activity.content_hash IS 'SHA-256 de la actividad (JSON canónico): leer de nuevo la misma actividad no la duplica.';
COMMENT ON INDEX drive_activity_source_at IS 'Busca la actividad de una planilla dentro de la ventana de un cambio.';

CREATE TABLE editor_profile (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id    text NOT NULL,
    person_name text NOT NULL,
    author      text NOT NULL,
    reason      text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE editor_profile IS 'Asociación de un identificador de editor de Google con una persona, hecha a mano (Google no informa nombres). Solo se agregan filas; la última por actor_id manda.';
COMMENT ON COLUMN editor_profile.id IS 'Identificador interno de la asociación.';
COMMENT ON COLUMN editor_profile.actor_id IS 'Identificador de editor de Google (el de drive_activity.actor_id).';
COMMENT ON COLUMN editor_profile.person_name IS 'Nombre de la persona.';
COMMENT ON COLUMN editor_profile.author IS 'Quién hizo la asociación.';
COMMENT ON COLUMN editor_profile.reason IS 'Por qué se sabe que es esa persona.';
COMMENT ON COLUMN editor_profile.created_at IS 'Momento de la asociación.';

CREATE TABLE annotation (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_type text NOT NULL CHECK (entity_type IN ('source', 'source_tab', 'cell_change', 'issue')),
    entity_key  text NOT NULL,
    body        text NOT NULL,
    author      text NOT NULL,
    reason      text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE annotation IS 'Nota escrita por una persona sobre una planilla, una pestaña, un cambio o un problema. Se guarda, no se interpreta. Solo se agregan filas.';
COMMENT ON COLUMN annotation.id IS 'Identificador interno de la nota.';
COMMENT ON COLUMN annotation.entity_type IS 'Sobre qué es la nota: source (planilla), source_tab (pestaña), cell_change (cambio) o issue (problema).';
COMMENT ON COLUMN annotation.entity_key IS 'Identificador de la planilla, pestaña, cambio o problema (su id interno).';
COMMENT ON COLUMN annotation.body IS 'Texto de la nota.';
COMMENT ON COLUMN annotation.author IS 'Quién escribió la nota.';
COMMENT ON COLUMN annotation.reason IS 'Por qué se escribió.';
COMMENT ON COLUMN annotation.created_at IS 'Momento de la nota.';

CREATE VIEW v_editor AS
WITH actor AS (
    SELECT actor_id, min(id) AS first_activity_id FROM drive_activity GROUP BY actor_id
), numbered AS (
    SELECT actor_id, first_activity_id,
           CASE WHEN actor_id <> 'deletedUser' THEN
               row_number() OVER (PARTITION BY actor_id = 'deletedUser' ORDER BY first_activity_id)
           END AS number
    FROM actor
)
SELECT n.actor_id, n.number, p.person_name,
       coalesce(
           p.person_name,
           CASE WHEN n.actor_id = 'deletedUser' THEN 'usuario eliminado'
                ELSE 'editor sin identificar #' || n.number END
       ) AS label
FROM numbered n
LEFT JOIN LATERAL (
    SELECT person_name FROM editor_profile
    WHERE actor_id = n.actor_id ORDER BY created_at DESC, id DESC LIMIT 1
) p ON true;

COMMENT ON VIEW v_editor IS 'Cada actor de la actividad de Drive con el nombre que se le asoció (la última fila de editor_profile manda) o, si no tiene, "editor sin identificar #N". N sigue el orden en que apareció cada actor por primera vez en drive_activity, así que no cambia entre consultas ni cuando llega actividad nueva. Las cuentas eliminadas son "usuario eliminado".';
COMMENT ON COLUMN v_editor.actor_id IS 'Identificador de editor de Google.';
COMMENT ON COLUMN v_editor.number IS 'Número estable del actor (1, 2, ...). Nulo para deletedUser.';
COMMENT ON COLUMN v_editor.person_name IS 'Nombre asociado en editor_profile, si hay.';
COMMENT ON COLUMN v_editor.label IS 'Cómo mostrar al actor: su nombre, "editor sin identificar #N" o "usuario eliminado".';

CREATE VIEW v_attribution_stats AS
SELECT t.source_id, c.detected_at::date AS day,
       count(*) AS total,
       count(*) FILTER (WHERE c.attribution_certainty = 'cierta') AS cierta,
       count(*) FILTER (WHERE c.attribution_certainty = 'una_de') AS una_de,
       count(*) FILTER (WHERE c.attribution_certainty = 'sin_datos') AS sin_datos,
       count(*) FILTER (WHERE c.attribution_certainty IS NULL) AS pendientes,
       round(100.0 * count(*) FILTER (WHERE c.attribution_certainty = 'cierta') / count(*), 1)
           AS pct_cierta
FROM cell_change c
JOIN source_tab t ON t.id = c.source_tab_id
WHERE c.window_end IS NOT NULL
GROUP BY t.source_id, c.detected_at::date;

COMMENT ON VIEW v_attribution_stats IS 'Qué tan bien se atribuyen los cambios, por planilla y por día: cuántos salieron con un solo editor (cierta), con varios (una_de), sin nadie (sin_datos) o siguen sin procesar. Cuenta los cambios de celdas y filas; los de pestaña (agregada, borrada, renombrada) no tienen ventana y no se atribuyen.';
COMMENT ON COLUMN v_attribution_stats.source_id IS 'Planilla.';
COMMENT ON COLUMN v_attribution_stats.day IS 'Día en que se detectó el cambio.';
COMMENT ON COLUMN v_attribution_stats.total IS 'Cambios detectados ese día.';
COMMENT ON COLUMN v_attribution_stats.cierta IS 'Cambios con un solo editor en la ventana.';
COMMENT ON COLUMN v_attribution_stats.una_de IS 'Cambios con varios editores en la ventana.';
COMMENT ON COLUMN v_attribution_stats.sin_datos IS 'Cambios sin ningún editor en la ventana.';
COMMENT ON COLUMN v_attribution_stats.pendientes IS 'Cambios todavía sin atribuir (falta leer la actividad posterior a la ventana).';
COMMENT ON COLUMN v_attribution_stats.pct_cierta IS 'Porcentaje de cambios con atribución cierta sobre el total del día.';

COMMENT ON COLUMN cell_change.window_end IS 'Última modificación del archivo según Google Drive en la versión nueva: el cambio ocurrió antes. La atribución mira la actividad hasta cinco minutos después, porque Google registra las ediciones con uno o dos minutos de demora.';
COMMENT ON COLUMN cell_change.attributed_editor_ids IS 'Quién hizo el cambio según la actividad de Drive: los identificadores de editor (nunca nombres) con ediciones en la ventana. Vacío si no hubo ninguna. Nulo hasta que la atribución lo procese.';
COMMENT ON COLUMN cell_change.attributed_at IS 'Con atribución cierta, el momento de la última edición de ese editor en la ventana según Google. Nulo en una_de, sin_datos y hasta que la atribución lo procese.';
