CREATE TABLE cell_change (
    id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_tab_id         bigint NOT NULL REFERENCES source_tab (id),
    from_snapshot         bigint REFERENCES snapshot (id),
    to_snapshot           bigint REFERENCES snapshot (id),
    change_type           text NOT NULL CHECK (change_type IN
        ('value', 'formula_overridden', 'formula', 'color', 'emptied', 'row_inserted',
         'row_deleted', 'row_moved', 'column_inserted', 'tab_added', 'tab_deleted', 'tab_renamed')),
    block                 text,
    row_key               text,
    row_ordinal           integer,
    cell_ref              text,
    old_value             text,
    new_value             text,
    old_formula           text,
    new_formula           text,
    old_color             text,
    new_color             text,
    detected_at           timestamptz NOT NULL DEFAULT now(),
    window_start          timestamptz,
    window_end            timestamptz,
    attributed_editor_ids text[],
    attribution_certainty text CHECK (attribution_certainty IN ('cierta', 'una_de', 'sin_datos')),
    attributed_at         timestamptz,
    CHECK ((from_snapshot IS NULL) = (change_type LIKE 'tab\_%')),
    CHECK ((to_snapshot IS NULL) = (change_type LIKE 'tab\_%'))
);

CREATE INDEX cell_change_tab_detected_at ON cell_change (source_tab_id, detected_at);

COMMENT ON TABLE cell_change IS 'Cambio detectado entre dos versiones (snapshots) consecutivas de una pestaña, o un cambio de la pestaña misma (agregada, borrada, renombrada). Guarda los valores anterior y nuevo: se lee solo desde la base. Solo se agregan filas.';
COMMENT ON COLUMN cell_change.id IS 'Identificador interno del cambio.';
COMMENT ON COLUMN cell_change.source_tab_id IS 'Pestaña donde ocurrió el cambio.';
COMMENT ON COLUMN cell_change.from_snapshot IS 'Versión anterior de la pestaña. Nula en los cambios de pestaña (agregada, borrada, renombrada).';
COMMENT ON COLUMN cell_change.to_snapshot IS 'Versión nueva de la pestaña, la que trajo el cambio. Nula en los cambios de pestaña.';
COMMENT ON COLUMN cell_change.change_type IS 'Tipo de cambio: value (cambió el valor), formula_overridden (la celda tenía fórmula y ahora tiene un valor tipeado), formula (cambió la fórmula), color (cambió el color de fondo), emptied (la celda tenía valor y quedó vacía), row_inserted, row_deleted, row_moved (fila agregada, borrada o movida, según su clave), column_inserted (encabezado nuevo en la fila de encabezado), tab_added, tab_deleted, tab_renamed (pestaña agregada, borrada o renombrada en Google).';
COMMENT ON COLUMN cell_change.block IS 'Bloque de la pestaña donde está la fila (el texto de la celda clave que lo abre, con " (2)" si se repite). Nulo en pestañas sin esquema.';
COMMENT ON COLUMN cell_change.row_key IS 'Clave de la fila: el texto de la columna clave normalizado (minúsculas, sin acentos, sin espacios dobles), sin pasar por aliases. Nula en pestañas sin esquema y en filas sin clave.';
COMMENT ON COLUMN cell_change.row_ordinal IS 'Orden de aparición de la fila entre las que tienen la misma clave en el mismo bloque (1, 2, ...): dos filas con la misma clave son dos series legítimas (regla R26).';
COMMENT ON COLUMN cell_change.cell_ref IS 'Celda en notación A1 (por ejemplo D17), en las coordenadas de la versión nueva. Nula en cambios de fila o de pestaña, y en celdas de una columna que ya no existe.';
COMMENT ON COLUMN cell_change.old_value IS 'Valor anterior tal como se ve en la planilla (texto formateado). En row_moved y row_deleted, el número de fila anterior; en tab_renamed, el nombre anterior de la pestaña.';
COMMENT ON COLUMN cell_change.new_value IS 'Valor nuevo tal como se ve en la planilla (texto formateado). En row_moved y row_inserted, el número de fila nuevo; en column_inserted, el encabezado nuevo; en tab_added y tab_renamed, el nombre de la pestaña.';
COMMENT ON COLUMN cell_change.old_formula IS 'Fórmula anterior, si la celda tenía.';
COMMENT ON COLUMN cell_change.new_formula IS 'Fórmula nueva, si la celda tiene.';
COMMENT ON COLUMN cell_change.old_color IS 'Color de fondo anterior en hexadecimal (#rrggbb).';
COMMENT ON COLUMN cell_change.new_color IS 'Color de fondo nuevo en hexadecimal (#rrggbb).';
COMMENT ON COLUMN cell_change.detected_at IS 'Momento en que Craftech OS leyó la versión nueva (o vio el cambio de pestaña).';
COMMENT ON COLUMN cell_change.window_start IS 'Última modificación del archivo según Google Drive en la versión anterior: el cambio ocurrió después.';
COMMENT ON COLUMN cell_change.window_end IS 'Última modificación del archivo según Google Drive en la versión nueva: el cambio ocurrió antes.';
COMMENT ON COLUMN cell_change.attributed_editor_ids IS 'Quién hizo el cambio según Google (identificadores de editor). Nulo hasta que la atribución lo procese.';
COMMENT ON COLUMN cell_change.attribution_certainty IS 'Certeza de la atribución: cierta (un solo editor en la ventana), una_de (uno de varios editores), sin_datos (Google no informó a nadie). Nula = todavía sin procesar.';
COMMENT ON COLUMN cell_change.attributed_at IS 'Momento en que se atribuyó el cambio. Nulo hasta que la atribución lo procese.';
COMMENT ON INDEX cell_change_tab_detected_at IS 'Busca los cambios de una pestaña por momento (los de un día, los últimos).';

CREATE TABLE issue (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    issue_type    text NOT NULL CHECK (issue_type IN
        ('color_desconocido', 'alineacion_ambigua', 'valor_ilegible', 'pestana_sin_clasificar')),
    stable_key    text NOT NULL,
    source_id     bigint NOT NULL REFERENCES source (id),
    source_tab_id bigint REFERENCES source_tab (id),
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at  timestamptz NOT NULL DEFAULT now(),
    details       jsonb NOT NULL DEFAULT '{}',
    owner         text,
    UNIQUE (issue_type, stable_key)
);

COMMENT ON TABLE issue IS 'Problema: algo que Craftech OS vio en una planilla y no interpreta (un color fuera de la lista, un texto donde va un monto, filas que no sabe alinear, una pestaña nueva sin clasificar). Uno por clave estable: verlo de nuevo actualiza last_seen_at, nunca lo duplica. Nunca se borra; su estado sale de issue_resolution (ver v_issue).';
COMMENT ON COLUMN issue.id IS 'Identificador interno del problema.';
COMMENT ON COLUMN issue.issue_type IS 'Tipo de problema: color_desconocido (color de fondo en la grilla de meses que no es uno de los cinco de la regla R29), alineacion_ambigua (la cantidad de filas con una misma clave cambió o una fila cambió de clave y de lugar: se compararon por posición), valor_ilegible (texto no numérico en la grilla de meses), pestana_sin_clasificar (pestaña nueva que nadie clasificó en config/sources.yaml).';
COMMENT ON COLUMN issue.stable_key IS 'Clave que identifica al problema entre lecturas, según el tipo: color_desconocido = pestaña + color; alineacion_ambigua = pestaña + bloque + clave de fila; valor_ilegible = pestaña + bloque + clave de fila + columna; pestana_sin_clasificar = planilla + sheetId. Las pestañas van por su identificador interno.';
COMMENT ON COLUMN issue.source_id IS 'Planilla donde está el problema.';
COMMENT ON COLUMN issue.source_tab_id IS 'Pestaña donde está el problema, si aplica.';
COMMENT ON COLUMN issue.first_seen_at IS 'Primera vez que Craftech OS vio el problema.';
COMMENT ON COLUMN issue.last_seen_at IS 'Última vez que Craftech OS vio el problema.';
COMMENT ON COLUMN issue.details IS 'Detalle de la última vez que se vio: celdas, cantidades, colores. Nunca montos.';
COMMENT ON COLUMN issue.owner IS 'Persona a cargo de resolverlo. Nulo mientras nadie lo tomó.';

CREATE TABLE issue_resolution (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    issue_id   bigint NOT NULL REFERENCES issue (id),
    action     text NOT NULL CHECK (action IN ('resuelto', 'ignorado')),
    author     text NOT NULL,
    reason     text,
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE issue_resolution IS 'Resolución de un problema: alguien lo dio por resuelto o decidió ignorarlo. Solo se agregan filas; la última manda.';
COMMENT ON COLUMN issue_resolution.id IS 'Identificador interno de la resolución.';
COMMENT ON COLUMN issue_resolution.issue_id IS 'Problema que se resuelve.';
COMMENT ON COLUMN issue_resolution.action IS 'resuelto (se corrigió; si se vuelve a ver, queda reabierto) o ignorado (no hace falta hacer nada; verlo de nuevo no lo reabre).';
COMMENT ON COLUMN issue_resolution.author IS 'Quién resolvió.';
COMMENT ON COLUMN issue_resolution.reason IS 'Por qué, en palabras de quien resolvió.';
COMMENT ON COLUMN issue_resolution.created_at IS 'Momento de la resolución.';

CREATE VIEW v_issue AS
SELECT i.id, i.issue_type, i.stable_key, i.source_id, i.source_tab_id, i.first_seen_at,
       i.last_seen_at, i.details, i.owner,
       CASE
           WHEN r.action IS NULL THEN 'abierto'
           WHEN r.action = 'resuelto' AND i.last_seen_at > r.created_at THEN 'reabierto'
           ELSE r.action
       END AS status,
       r.author AS resolved_by,
       r.reason AS resolution_reason,
       r.created_at AS resolved_at
FROM issue i
LEFT JOIN LATERAL (
    SELECT action, author, reason, created_at FROM issue_resolution
    WHERE issue_id = i.id ORDER BY created_at DESC, id DESC LIMIT 1
) r ON true;

COMMENT ON VIEW v_issue IS 'Problemas con su estado, derivado de la última resolución: abierto (sin resolución), resuelto, ignorado, o reabierto (resuelto y visto de nuevo después). Es lo que leen la web y el servidor MCP.';
COMMENT ON COLUMN v_issue.status IS 'Estado del problema: abierto, resuelto, ignorado o reabierto.';
COMMENT ON COLUMN v_issue.resolved_by IS 'Autor de la última resolución, si hay.';
COMMENT ON COLUMN v_issue.resolution_reason IS 'Motivo de la última resolución, si hay.';
COMMENT ON COLUMN v_issue.resolved_at IS 'Momento de la última resolución, si hay.';

COMMENT ON COLUMN source_tab.schema IS 'Esquema de la pestaña, cargado desde config/sources.yaml: texto de la fila de encabezado (header), columna clave (key), textos que abren cada bloque en la columna clave (blocks) y rango de columnas de la grilla de meses (grid). Con esquema, las filas se alinean por clave dentro de cada bloque; sin esquema (nulo), las diferencias son por posición.';
