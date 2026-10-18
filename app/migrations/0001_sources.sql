CREATE TABLE source (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    drive_id      text UNIQUE,
    title         text NOT NULL UNIQUE,
    shared_drive  text,
    loaded_by     text,
    default_class text CHECK (default_class IN
        ('CARGA', 'DERIVADA', 'HISTORICA', 'IGNORAR', 'A_CONFIRMAR', 'SIN_CLASIFICAR'))
);

COMMENT ON TABLE source IS 'Fuente: una planilla de Google Sheets de Finanzas que Craftech OS lee (por ejemplo "Facturación - Craftech Total"). Se carga desde config/sources.yaml.';
COMMENT ON COLUMN source.id IS 'Identificador interno de la fuente.';
COMMENT ON COLUMN source.drive_id IS 'Identificador del archivo en Google Drive. Nulo hasta la importación inicial.';
COMMENT ON COLUMN source.title IS 'Título completo de la planilla tal como aparece en Google Drive, nunca una sigla.';
COMMENT ON COLUMN source.shared_drive IS 'Unidad compartida de Google Drive donde vive la planilla.';
COMMENT ON COLUMN source.loaded_by IS 'Quién carga la planilla (persona o área de Finanzas).';
COMMENT ON COLUMN source.default_class IS 'Clase que reciben todas las pestañas de la planilla cuando config/sources.yaml no las nombra una por una (por ejemplo, los P&L: todas DERIVADA). Nula si las pestañas se clasifican de a una.';

CREATE TABLE source_tab (
    id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id bigint NOT NULL REFERENCES source (id),
    sheet_id  bigint,
    name      text NOT NULL,
    class     text NOT NULL CHECK (class IN
        ('CARGA', 'DERIVADA', 'HISTORICA', 'IGNORAR', 'A_CONFIRMAR', 'SIN_CLASIFICAR')),
    schema    jsonb,
    active    boolean NOT NULL DEFAULT true,
    UNIQUE (source_id, name)
);

COMMENT ON TABLE source_tab IS 'Pestaña de una planilla fuente, con su clase. Una pestaña que sale de config/sources.yaml queda inactiva, nunca se borra.';
COMMENT ON COLUMN source_tab.id IS 'Identificador interno de la pestaña.';
COMMENT ON COLUMN source_tab.source_id IS 'Planilla fuente a la que pertenece la pestaña.';
COMMENT ON COLUMN source_tab.sheet_id IS 'Identificador numérico de la pestaña en Google Sheets (sheetId). Nulo hasta la importación inicial.';
COMMENT ON COLUMN source_tab.name IS 'Nombre de la pestaña tal como aparece en Google Sheets.';
COMMENT ON COLUMN source_tab.class IS 'Clase de la pestaña: CARGA (Finanzas carga datos; se lee continuo y sus cambios se alertan), DERIVADA (fórmulas o vistas; se lee continuo para paridad, sin alertas), HISTORICA (se importa una vez), IGNORAR (se importa una vez y no se interpreta), A_CONFIRMAR (se importa una vez y no se vuelve a leer hasta que Finanzas diga qué es), SIN_CLASIFICAR (apareció al leer y nadie la clasificó todavía).';
COMMENT ON COLUMN source_tab.schema IS 'Esquema de la pestaña (columna clave, bloques) para calcular diferencias celda a celda. Nulo hasta que se define.';
COMMENT ON COLUMN source_tab.active IS 'Falso si la pestaña ya no figura en config/sources.yaml; la fila se conserva por su historia.';

CREATE TABLE system_event (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    occurred_at   timestamptz NOT NULL DEFAULT now(),
    kind          text NOT NULL,
    source_id     bigint REFERENCES source (id),
    source_tab_id bigint REFERENCES source_tab (id),
    details       jsonb NOT NULL DEFAULT '{}',
    duration_ms   integer
);

COMMENT ON TABLE system_event IS 'Evento del sistema: historial de lo operativo (lecturas, importaciones, errores de la API de Google), nunca valores de celdas.';
COMMENT ON COLUMN system_event.id IS 'Identificador interno del evento.';
COMMENT ON COLUMN system_event.occurred_at IS 'Momento en que ocurrió el evento.';
COMMENT ON COLUMN system_event.kind IS 'Tipo de evento (por ejemplo, lectura de una planilla o error de cuota de Google).';
COMMENT ON COLUMN system_event.source_id IS 'Planilla fuente a la que se refiere el evento, si aplica.';
COMMENT ON COLUMN system_event.source_tab_id IS 'Pestaña a la que se refiere el evento, si aplica.';
COMMENT ON COLUMN system_event.details IS 'Detalle del evento: identificadores y conteos, nunca valores de celdas.';
COMMENT ON COLUMN system_event.duration_ms IS 'Duración de la operación en milisegundos, si aplica.';
