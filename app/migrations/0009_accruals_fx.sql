-- Facts interpreted from the last read of a tab (ADR-002): accruals from VENTAS and exchange
-- rates from Pagos ARG. Each reinterpretation of a tab deletes its facts and inserts the new
-- ones in one transaction. Facts carry no client: the views resolve it through client_alias.

CREATE TABLE accrual (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_tab_id bigint NOT NULL REFERENCES source_tab (id),
    block         text NOT NULL,
    row_key       text NOT NULL,
    series_order  integer NOT NULL CHECK (series_order >= 1),
    month         date NOT NULL CHECK (extract(day FROM month) = 1),
    amount_usd    numeric NOT NULL,
    business_unit text,
    pod           text,
    alias_source  text NOT NULL,
    alias_text    text NOT NULL,
    snapshot_id   bigint NOT NULL REFERENCES snapshot (id),
    cell_ref      text NOT NULL,
    rules_version text NOT NULL,
    UNIQUE (source_tab_id, block, row_key, month)
);

COMMENT ON TABLE accrual IS 'Devengado: lo que se le vende a un cliente en un mes, una fila de cliente por una columna de mes de VENTAS, con el monto tal como está en la celda. Se reemplaza entero en cada lectura nueva de la pestaña.';
COMMENT ON COLUMN accrual.id IS 'Identificador interno; cambia en cada reinterpretación.';
COMMENT ON COLUMN accrual.source_tab_id IS 'Pestaña de la que sale.';
COMMENT ON COLUMN accrual.block IS 'Bloque de la pestaña donde está la fila (el del encabezado, ej. Cliente o Mes, o uno declarado como General).';
COMMENT ON COLUMN accrual.row_key IS 'Texto de la columna clave, normalizado; si se repite en el bloque lleva el orden como sufijo, ej. "cliente x (2)" (regla R26).';
COMMENT ON COLUMN accrual.series_order IS 'Orden de la fila entre las que tienen el mismo texto en el bloque: 1 si no se repite.';
COMMENT ON COLUMN accrual.month IS 'Mes devengado, el primer día del mes, sacado del encabezado de la columna.';
COMMENT ON COLUMN accrual.amount_usd IS 'Monto en dólares tal como está en la celda: ya prorrateado por días (regla R1) y neto de IVA (regla R14).';
COMMENT ON COLUMN accrual.business_unit IS 'Unidad de negocio de la fila, como texto (columna "U. Negocio"); nula si la pestaña no la tiene.';
COMMENT ON COLUMN accrual.pod IS 'POD de la fila, como texto (columna "POD"); nulo si la pestaña no lo tiene.';
COMMENT ON COLUMN accrual.alias_source IS 'Fuente con la que se busca el alias del cliente: "planilla / pestaña", normalizada.';
COMMENT ON COLUMN accrual.alias_text IS 'Texto con el que se busca el alias del cliente: el de la columna clave, normalizado y sin sufijo.';
COMMENT ON COLUMN accrual.snapshot_id IS 'Lectura de la que sale.';
COMMENT ON COLUMN accrual.cell_ref IS 'Celda del monto en notación A1.';
COMMENT ON COLUMN accrual.rules_version IS 'Versión de las reglas con las que se interpretó.';

CREATE TABLE fx_rate (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rate_type       text NOT NULL CHECK (rate_type IN ('mep', 'oficial', 'tipeada')),
    month           date NOT NULL CHECK (extract(day FROM month) = 1),
    source_tab_id   bigint NOT NULL REFERENCES source_tab (id),
    value           numeric NOT NULL,
    type_to_confirm boolean NOT NULL,
    snapshot_id     bigint NOT NULL REFERENCES snapshot (id),
    cell_ref        text NOT NULL,
    rules_version   text NOT NULL,
    UNIQUE (rate_type, month, source_tab_id)
);

COMMENT ON TABLE fx_rate IS 'Cotización del dólar en pesos de un mes, de las filas de cotización de Pagos ARG. Se reemplaza entera en cada lectura nueva de la pestaña.';
COMMENT ON COLUMN fx_rate.id IS 'Identificador interno; cambia en cada reinterpretación.';
COMMENT ON COLUMN fx_rate.rate_type IS 'Tipo: mep (la fila MEP operativa), oficial (la fila "Dólar oficial") o tipeada (escrita a mano en una factura; todavía no se usa).';
COMMENT ON COLUMN fx_rate.month IS 'Mes de la cotización, el primer día del mes, sacado del encabezado de la columna.';
COMMENT ON COLUMN fx_rate.source_tab_id IS 'Pestaña de la que sale.';
COMMENT ON COLUMN fx_rate.value IS 'Pesos por dólar, tal como está en la celda.';
COMMENT ON COLUMN fx_rate.type_to_confirm IS 'Verdadero si no está confirmado qué cotización es (el "Dólar oficial", mientras Emi no responda la pregunta F-01).';
COMMENT ON COLUMN fx_rate.snapshot_id IS 'Lectura de la que sale.';
COMMENT ON COLUMN fx_rate.cell_ref IS 'Celda de la cotización en notación A1.';
COMMENT ON COLUMN fx_rate.rules_version IS 'Versión de las reglas con las que se interpretó.';

ALTER TABLE issue DROP CONSTRAINT issue_issue_type_check;
ALTER TABLE issue ADD CONSTRAINT issue_issue_type_check CHECK (issue_type IN
    ('color_desconocido', 'alineacion_ambigua', 'valor_ilegible', 'pestana_sin_clasificar',
     'alias_sin_cliente', 'cotizacion_tipeada', 'cotizacion_discrepante',
     'cotizacion_tipo_a_confirmar', 'funding_duplicado', 'identidad_en_revision',
     'fila_sin_interpretar'));

COMMENT ON COLUMN issue.issue_type IS 'Tipo de problema: color_desconocido (color de fondo en la grilla de meses que no es uno de los cinco de la regla R29), alineacion_ambigua (la cantidad de filas con una misma clave cambió o una fila cambió de clave y de lugar: se compararon por posición), valor_ilegible (texto no numérico en la grilla de meses), pestana_sin_clasificar (pestaña nueva que nadie clasificó en config/sources.yaml), alias_sin_cliente (fila con montos cuyo texto no tiene un alias que diga de qué cliente es), cotizacion_tipeada (cotización escrita a mano; todavía no se usa), cotizacion_discrepante (la MEP de control difiere de la operativa en un mes, regla R10), cotizacion_tipo_a_confirmar (se guardó una cotización sin saber de qué tipo es), funding_duplicado (todavía no se usa), identidad_en_revision (el mismo texto en dos filas de un bloque: se toman como dos series, regla R26), fila_sin_interpretar (fila o columna con montos que no se pudo ubicar en un cliente y un mes).';
COMMENT ON COLUMN issue.stable_key IS 'Clave que identifica al problema entre lecturas, según el tipo: color_desconocido = pestaña + color; alineacion_ambigua = pestaña + bloque + clave de fila; valor_ilegible = pestaña + bloque + clave de fila + columna; pestana_sin_clasificar = planilla + sheetId; alias_sin_cliente = pestaña + texto; identidad_en_revision = pestaña + bloque + clave de fila; fila_sin_interpretar = pestaña + bloque + clave o número de fila (+ columna); cotizacion_discrepante = pestaña + mes; cotizacion_tipo_a_confirmar = pestaña + tipo. Las pestañas van por su identificador interno.';

COMMENT ON COLUMN mcp.issues.tipo IS 'Tipo: color_desconocido (color de fondo en la grilla de meses que no es uno de los cinco de la regla R29), alineacion_ambigua (filas con la misma clave que no se pudieron alinear entre lecturas), valor_ilegible (texto no numérico donde va un monto), pestana_sin_clasificar (pestaña nueva que nadie clasificó), alias_sin_cliente (fila con montos cuyo texto no tiene alias que diga de qué cliente es), cotizacion_discrepante (la MEP de control difiere de la operativa en un mes, regla R10), cotizacion_tipo_a_confirmar (cotización guardada sin saber de qué tipo es), identidad_en_revision (el mismo texto en dos filas de un bloque: dos series, regla R26), fila_sin_interpretar (fila o columna con montos que no se pudo ubicar en un cliente y un mes), cotizacion_tipeada y funding_duplicado (todavía no se usan).';

COMMENT ON COLUMN client_alias.source IS 'Fuente donde aparece el texto: "planilla / pestaña", normalizada (minúsculas, sin acentos, espacios simples), ej. "facturacion - craftech total / ventas".';

CREATE VIEW mcp.devengados AS
SELECT s.title AS planilla, t.name AS pestaña, t.id AS pestaña_id, a.snapshot_id AS lectura_id,
       n.read_at AS leido_en, a.cell_ref AS celda, a.block AS bloque, a.row_key AS clave_fila,
       a.series_order AS serie, a.month AS mes, a.amount_usd AS monto_usd,
       a.business_unit AS unidad_negocio, a.pod, c.id AS cliente_id, c.name AS cliente,
       a.rules_version AS version_reglas
FROM accrual a
JOIN snapshot n ON n.id = a.snapshot_id
JOIN source_tab t ON t.id = a.source_tab_id AND t.active
JOIN source s ON s.id = t.source_id
LEFT JOIN LATERAL (
    SELECT x.client_id FROM client_alias x
    WHERE x.source = a.alias_source AND x.text = a.alias_text
    ORDER BY x.created_at DESC, x.id DESC
    LIMIT 1
) al ON true
LEFT JOIN client c ON c.id = al.client_id;

COMMENT ON VIEW mcp.devengados IS 'Devengados: lo vendido a cada cliente por mes según VENTAS, de la última lectura de cada pestaña, con el monto tal como está en la celda (ya prorrateado por días y neto de IVA). El cliente sale del alias vigente; nulo si el texto todavía no tiene alias (hay un problema alias_sin_cliente). Planilla, pestaña, celda y lectura llevan a la celda de origen.';
COMMENT ON COLUMN mcp.devengados.planilla IS 'Nombre de la planilla de Google Sheets.';
COMMENT ON COLUMN mcp.devengados.pestaña IS 'Nombre de la pestaña.';
COMMENT ON COLUMN mcp.devengados.pestaña_id IS 'Identificador de la pestaña (mcp.tabs.id).';
COMMENT ON COLUMN mcp.devengados.lectura_id IS 'Lectura de la que sale (mcp.snapshots.id); la celda está en mcp.celdas.';
COMMENT ON COLUMN mcp.devengados.leido_en IS 'Momento de esa lectura.';
COMMENT ON COLUMN mcp.devengados.celda IS 'Celda del monto en notación A1 (ej. F30).';
COMMENT ON COLUMN mcp.devengados.bloque IS 'Bloque de la pestaña donde está la fila.';
COMMENT ON COLUMN mcp.devengados.clave_fila IS 'Texto de la fila (el cliente como figura en la planilla), normalizado; con sufijo " (2)" si se repite en el bloque.';
COMMENT ON COLUMN mcp.devengados.serie IS 'Orden de la fila entre las que tienen el mismo texto en el bloque: 1 si no se repite; más de una es otra serie del mismo cliente (regla R26).';
COMMENT ON COLUMN mcp.devengados.mes IS 'Mes devengado (primer día del mes).';
COMMENT ON COLUMN mcp.devengados.monto_usd IS 'Monto en dólares tal como está en la celda.';
COMMENT ON COLUMN mcp.devengados.unidad_negocio IS 'Unidad de negocio de la fila, como texto; nula si la pestaña no la tiene.';
COMMENT ON COLUMN mcp.devengados.pod IS 'POD de la fila, como texto; nulo si la pestaña no lo tiene.';
COMMENT ON COLUMN mcp.devengados.cliente_id IS 'Cliente según el alias vigente (mcp.clientes.id); nulo si no hay alias.';
COMMENT ON COLUMN mcp.devengados.cliente IS 'Nombre de fantasía del cliente; nulo si no hay alias.';
COMMENT ON COLUMN mcp.devengados.version_reglas IS 'Versión de las reglas con las que se interpretó.';

CREATE VIEW mcp.cotizaciones AS
SELECT s.title AS planilla, t.name AS pestaña, t.id AS pestaña_id, f.snapshot_id AS lectura_id,
       n.read_at AS leido_en, f.cell_ref AS celda, f.rate_type AS tipo, f.month AS mes,
       f.value AS valor, f.type_to_confirm AS tipo_a_confirmar, f.rules_version AS version_reglas
FROM fx_rate f
JOIN snapshot n ON n.id = f.snapshot_id
JOIN source_tab t ON t.id = f.source_tab_id AND t.active
JOIN source s ON s.id = t.source_id;

COMMENT ON VIEW mcp.cotizaciones IS 'Cotizaciones del dólar en pesos por mes, de las filas de cotización de Pagos ARG en la última lectura de cada pestaña. Planilla, pestaña, celda y lectura llevan a la celda de origen.';
COMMENT ON COLUMN mcp.cotizaciones.planilla IS 'Nombre de la planilla de Google Sheets.';
COMMENT ON COLUMN mcp.cotizaciones.pestaña IS 'Nombre de la pestaña.';
COMMENT ON COLUMN mcp.cotizaciones.pestaña_id IS 'Identificador de la pestaña (mcp.tabs.id).';
COMMENT ON COLUMN mcp.cotizaciones.lectura_id IS 'Lectura de la que sale (mcp.snapshots.id); la celda está en mcp.celdas.';
COMMENT ON COLUMN mcp.cotizaciones.leido_en IS 'Momento de esa lectura.';
COMMENT ON COLUMN mcp.cotizaciones.celda IS 'Celda de la cotización en notación A1.';
COMMENT ON COLUMN mcp.cotizaciones.tipo IS 'mep (la fila MEP operativa) u oficial (la fila "Dólar oficial").';
COMMENT ON COLUMN mcp.cotizaciones.mes IS 'Mes de la cotización (primer día del mes).';
COMMENT ON COLUMN mcp.cotizaciones.valor IS 'Pesos por dólar, tal como está en la celda.';
COMMENT ON COLUMN mcp.cotizaciones.tipo_a_confirmar IS 'Verdadero si no está confirmado qué cotización es: el "Dólar oficial", mientras Emi no responda la pregunta F-01.';
COMMENT ON COLUMN mcp.cotizaciones.version_reglas IS 'Versión de las reglas con las que se interpretó.';

GRANT SELECT ON mcp.devengados TO mcp_reader;
GRANT SELECT ON mcp.cotizaciones TO mcp_reader;
