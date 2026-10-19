-- Canonical clients: Craftech's two legal entities, the clients with their razones sociales,
-- and the aliases that tie a text in a spreadsheet to a client. The loaders and the MCP
-- server only INSERT; an alias is never changed, a newer decision replaces it.

CREATE TABLE legal_entity (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name           text NOT NULL UNIQUE,
    country        text NOT NULL,
    billing_system text NOT NULL UNIQUE CHECK (billing_system IN ('bejerman', 'zoho'))
);

COMMENT ON TABLE legal_entity IS 'Las dos sociedades de Craftech que facturan, cada una con su sistema de facturación.';
COMMENT ON COLUMN legal_entity.id IS 'Identificador interno de la sociedad.';
COMMENT ON COLUMN legal_entity.name IS 'Nombre de la sociedad.';
COMMENT ON COLUMN legal_entity.country IS 'País de la sociedad.';
COMMENT ON COLUMN legal_entity.billing_system IS 'Sistema con el que factura: bejerman (Craftech S.A.) o zoho (Craftech-io Inc.).';

INSERT INTO legal_entity (name, country, billing_system) VALUES
    ('Craftech S.A.', 'Argentina', 'bejerman'),
    ('Craftech-io Inc.', 'Estados Unidos', 'zoho');

CREATE TABLE client (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name       text NOT NULL UNIQUE CHECK (btrim(name) <> ''),
    hubspot_id text UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE client IS 'Cliente de Craftech por su nombre de fantasía, el que se usa en las planillas.';
COMMENT ON COLUMN client.id IS 'Identificador interno del cliente.';
COMMENT ON COLUMN client.name IS 'Nombre de fantasía del cliente.';
COMMENT ON COLUMN client.hubspot_id IS 'Identificador del cliente en HubSpot, si se conoce.';
COMMENT ON COLUMN client.created_at IS 'Momento en que se dio de alta.';

CREATE TABLE client_legal_entity (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    client_id          bigint NOT NULL REFERENCES client (id),
    legal_name         text NOT NULL CHECK (btrim(legal_name) <> ''),
    country            text,
    tax_id_type        text,
    tax_id             text,
    source_system      text NOT NULL REFERENCES legal_entity (billing_system),
    payment_terms_days integer NOT NULL DEFAULT 10 CHECK (payment_terms_days >= 0),
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now()
);

-- The natural key of a load: the tax ID within one billing system.
CREATE UNIQUE INDEX client_legal_entity_tax_id ON client_legal_entity (source_system, tax_id)
    WHERE tax_id IS NOT NULL;

COMMENT ON TABLE client_legal_entity IS 'Razón social con la que se le factura a un cliente; un cliente puede tener varias.';
COMMENT ON COLUMN client_legal_entity.id IS 'Identificador interno de la razón social.';
COMMENT ON COLUMN client_legal_entity.client_id IS 'Cliente al que pertenece.';
COMMENT ON COLUMN client_legal_entity.legal_name IS 'Razón social.';
COMMENT ON COLUMN client_legal_entity.country IS 'País de facturación, tal como viene del sistema de origen.';
COMMENT ON COLUMN client_legal_entity.tax_id_type IS 'Tipo de identificación fiscal (EIN, RFC, RUT, CUIT, etc.), tal como viene.';
COMMENT ON COLUMN client_legal_entity.tax_id IS 'Número de identificación fiscal.';
COMMENT ON COLUMN client_legal_entity.source_system IS 'Sistema del que viene: bejerman (Craftech S.A.) o zoho (Craftech-io Inc.).';
COMMENT ON COLUMN client_legal_entity.payment_terms_days IS 'Plazo de pago en días (10 por defecto; 0 es al recibir la factura).';
COMMENT ON COLUMN client_legal_entity.created_at IS 'Momento del alta.';
COMMENT ON COLUMN client_legal_entity.updated_at IS 'Momento de la última carga que la cambió.';

CREATE TABLE client_alias (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source     text NOT NULL CHECK (btrim(source) <> ''),
    text       text NOT NULL CHECK (btrim(text) <> ''),
    client_id  bigint NOT NULL REFERENCES client (id),
    author     text NOT NULL,
    reason     text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT client_alias_author_reason_present CHECK (btrim(author) <> '' AND btrim(reason) <> '')
);

CREATE INDEX client_alias_source_text ON client_alias (source, text, created_at DESC, id DESC);

COMMENT ON TABLE client_alias IS 'Decisiones de quién es el cliente detrás de un texto de una fuente. Solo se agregan filas: la decisión más reciente de cada fuente y texto es la vigente.';
COMMENT ON COLUMN client_alias.id IS 'Identificador interno de la decisión.';
COMMENT ON COLUMN client_alias.source IS 'Fuente o pestaña donde aparece el texto.';
COMMENT ON COLUMN client_alias.text IS 'Texto normalizado (minúsculas, sin acentos, espacios simples).';
COMMENT ON COLUMN client_alias.client_id IS 'Cliente que se decidió.';
COMMENT ON COLUMN client_alias.author IS 'Quién lo decidió.';
COMMENT ON COLUMN client_alias.reason IS 'Por qué.';
COMMENT ON COLUMN client_alias.created_at IS 'Momento de la decisión.';

CREATE VIEW mcp.clientes AS
SELECT c.id, c.name AS nombre, c.hubspot_id,
       (SELECT count(*) FROM client_legal_entity e WHERE e.client_id = c.id) AS razones_sociales,
       c.created_at AS creado_en
FROM client c;

COMMENT ON VIEW mcp.clientes IS 'Clientes de Craftech por su nombre de fantasía. Las razones sociales están en mcp.razones_sociales y los textos de las planillas que los nombran, en mcp.aliases.';
COMMENT ON COLUMN mcp.clientes.id IS 'Identificador del cliente.';
COMMENT ON COLUMN mcp.clientes.nombre IS 'Nombre de fantasía, el que se usa en las planillas.';
COMMENT ON COLUMN mcp.clientes.hubspot_id IS 'Identificador en HubSpot, si se conoce.';
COMMENT ON COLUMN mcp.clientes.razones_sociales IS 'Cantidad de razones sociales con las que se le factura.';
COMMENT ON COLUMN mcp.clientes.creado_en IS 'Momento del alta.';

CREATE VIEW mcp.razones_sociales AS
SELECT e.id, e.client_id AS cliente_id, c.name AS cliente, e.legal_name AS razon_social,
       e.country AS pais, e.tax_id_type AS tipo_tax_id, e.tax_id, e.source_system AS sistema,
       l.name AS sociedad_craftech, e.payment_terms_days AS plazo_pago_dias,
       e.updated_at AS actualizado_en
FROM client_legal_entity e
JOIN client c ON c.id = e.client_id
JOIN legal_entity l ON l.billing_system = e.source_system;

COMMENT ON VIEW mcp.razones_sociales IS 'Razones sociales de cada cliente, con su identificación fiscal y su plazo de pago, tal como vienen de Zoho o Bejerman.';
COMMENT ON COLUMN mcp.razones_sociales.id IS 'Identificador de la razón social.';
COMMENT ON COLUMN mcp.razones_sociales.cliente_id IS 'Cliente (mcp.clientes.id).';
COMMENT ON COLUMN mcp.razones_sociales.cliente IS 'Nombre de fantasía del cliente.';
COMMENT ON COLUMN mcp.razones_sociales.razon_social IS 'Razón social.';
COMMENT ON COLUMN mcp.razones_sociales.pais IS 'País de facturación, tal como viene del sistema de origen.';
COMMENT ON COLUMN mcp.razones_sociales.tipo_tax_id IS 'Tipo de identificación fiscal (EIN, RFC, RUT, CUIT, etc.), tal como viene.';
COMMENT ON COLUMN mcp.razones_sociales.tax_id IS 'Número de identificación fiscal.';
COMMENT ON COLUMN mcp.razones_sociales.sistema IS 'Sistema del que viene: bejerman o zoho.';
COMMENT ON COLUMN mcp.razones_sociales.sociedad_craftech IS 'Sociedad de Craftech que le factura: Craftech S.A. (bejerman) o Craftech-io Inc. (zoho).';
COMMENT ON COLUMN mcp.razones_sociales.plazo_pago_dias IS 'Plazo de pago en días (10 por defecto; 0 es al recibir la factura).';
COMMENT ON COLUMN mcp.razones_sociales.actualizado_en IS 'Momento de la última carga que la cambió.';

CREATE VIEW mcp.aliases AS
SELECT a.source AS fuente, a.text AS texto, a.client_id AS cliente_id, c.name AS cliente,
       a.author AS decidio, a.reason AS motivo, a.created_at AS decidido_en,
       d.n - 1 AS decisiones_anteriores
FROM (SELECT source, text, count(*) AS n FROM client_alias GROUP BY source, text) d
CROSS JOIN LATERAL (
    SELECT * FROM client_alias x
    WHERE x.source = d.source AND x.text = d.text
    ORDER BY x.created_at DESC, x.id DESC
    LIMIT 1
) a
JOIN client c ON c.id = a.client_id;

COMMENT ON VIEW mcp.aliases IS 'Qué cliente hay detrás de cada texto de una fuente: solo la decisión vigente (la más reciente). Las anteriores se conservan y se cuentan.';
COMMENT ON COLUMN mcp.aliases.fuente IS 'Fuente o pestaña donde aparece el texto.';
COMMENT ON COLUMN mcp.aliases.texto IS 'Texto normalizado (minúsculas, sin acentos, espacios simples).';
COMMENT ON COLUMN mcp.aliases.cliente_id IS 'Cliente decidido (mcp.clientes.id).';
COMMENT ON COLUMN mcp.aliases.cliente IS 'Nombre de fantasía del cliente decidido.';
COMMENT ON COLUMN mcp.aliases.decidio IS 'Quién tomó la decisión vigente.';
COMMENT ON COLUMN mcp.aliases.motivo IS 'Por qué.';
COMMENT ON COLUMN mcp.aliases.decidido_en IS 'Momento de la decisión vigente.';
COMMENT ON COLUMN mcp.aliases.decisiones_anteriores IS 'Decisiones anteriores para la misma fuente y texto, reemplazadas por esta.';

GRANT SELECT ON mcp.clientes TO mcp_reader;
GRANT SELECT ON mcp.razones_sociales TO mcp_reader;
GRANT SELECT ON mcp.aliases TO mcp_reader;

-- client has no author: its write event records the tool only.
CREATE OR REPLACE FUNCTION record_mcp_write() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    IF session_user = 'mcp_writer' THEN
        INSERT INTO system_event (kind, details)
        VALUES ('mcp_write',
                jsonb_build_object('herramienta', TG_ARGV[0], 'autor', to_jsonb(NEW)->>'author'));
    END IF;
    RETURN NULL;
END
$$;

CREATE TRIGGER client_mcp_write AFTER INSERT ON client
    FOR EACH ROW EXECUTE FUNCTION record_mcp_write('vincular_alias');
CREATE TRIGGER client_alias_mcp_write AFTER INSERT ON client_alias
    FOR EACH ROW EXECUTE FUNCTION record_mcp_write('vincular_alias');

-- Identity columns need no sequence privilege for INSERT.
GRANT INSERT ON client, client_alias TO mcp_writer;
