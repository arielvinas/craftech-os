CREATE TABLE snapshot (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_tab_id     bigint NOT NULL REFERENCES source_tab (id),
    drive_version     bigint NOT NULL,
    drive_modified_at timestamptz NOT NULL,
    read_at           timestamptz NOT NULL DEFAULT now(),
    duration_ms       integer NOT NULL,
    origin            text NOT NULL CHECK (origin IN ('lectura', 'revision_google')),
    content_hash      text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    content           jsonb NOT NULL,
    row_count         integer NOT NULL,
    col_count         integer NOT NULL,
    cell_count        integer NOT NULL
);

CREATE INDEX snapshot_tab_read_at ON snapshot (source_tab_id, read_at);

COMMENT ON TABLE snapshot IS 'Versión cruda de una pestaña: la pestaña entera tal como vino de Google Sheets en una lectura (valores, fórmulas, formato efectivo, celdas combinadas). Nunca se borra ni se modifica; solo se agregan filas.';
COMMENT ON COLUMN snapshot.id IS 'Identificador interno de la versión.';
COMMENT ON COLUMN snapshot.source_tab_id IS 'Pestaña de la que es esta versión.';
COMMENT ON COLUMN snapshot.drive_version IS 'Número de versión del archivo en Google Drive al momento de la lectura; cambia con cada guardado de la planilla.';
COMMENT ON COLUMN snapshot.drive_modified_at IS 'Última modificación del archivo según Google Drive al momento de la lectura.';
COMMENT ON COLUMN snapshot.read_at IS 'Momento en que Craftech OS leyó la pestaña.';
COMMENT ON COLUMN snapshot.duration_ms IS 'Duración de la lectura de la pestaña en milisegundos.';
COMMENT ON COLUMN snapshot.origin IS 'De dónde salió la versión: lectura (Craftech OS leyó la pestaña) o revision_google (revisión vieja importada del historial de Google; todavía no se usa).';
COMMENT ON COLUMN snapshot.content_hash IS 'Hash SHA-256 (hexadecimal) del contenido serializado con claves ordenadas; si no cambia, la pestaña no cambió.';
COMMENT ON COLUMN snapshot.content IS 'Contenido de la pestaña: filas con sus celdas no vacías (valor, texto formateado, fórmula, color de fondo, formato numérico), rangos combinados y tamaño. Se guarda lo que vino, sin interpretar.';
COMMENT ON COLUMN snapshot.row_count IS 'Filas usadas: hasta la última fila con alguna celda no vacía.';
COMMENT ON COLUMN snapshot.col_count IS 'Columnas usadas: hasta la última columna con alguna celda no vacía.';
COMMENT ON COLUMN snapshot.cell_count IS 'Cantidad de celdas no vacías.';
COMMENT ON INDEX snapshot_tab_read_at IS 'Busca las versiones de una pestaña por momento de lectura (la última, o la de un día).';

ALTER TABLE source_tab ADD CONSTRAINT source_tab_sheet_id_key UNIQUE (source_id, sheet_id);

COMMENT ON COLUMN source_tab.sheet_id IS 'Identificador numérico de la pestaña en Google Sheets (sheetId): su identidad al leer, porque Google lo mantiene aunque la pestaña se renombre. Nulo hasta que la importación encuentra la pestaña en Google.';
COMMENT ON COLUMN source_tab.active IS 'Falso si la pestaña ya no figura en config/sources.yaml o ya no existe en Google; la fila se conserva por su historia.';
