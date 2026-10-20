-- Invoices, payments and churn interpreted from Pagos and Pagos ARG (ADR-002), and the totals
-- of those tabs to check them against. The state of an invoice is the color of its cell
-- (rule R29). Payments and state changes point at cell_change, never copy its date or author:
-- the attribution arrives after the read and the views show it as soon as it does.

CREATE FUNCTION a1_column(ref text) RETURNS integer LANGUAGE sql IMMUTABLE AS $$
    SELECT sum((ascii(ch) - 64) * 26 ^ (length(x.letters) - n))::integer - 1
    FROM (SELECT regexp_replace(upper(ref), '[^A-Z]', '', 'g') AS letters) x,
         LATERAL unnest(string_to_array(x.letters, NULL)) WITH ORDINALITY AS u (ch, n)
$$;

COMMENT ON FUNCTION a1_column(text) IS 'Columna de una celda en notación A1, contada desde 0 (A = 0, AA = 26).';

CREATE FUNCTION shows_amount(shown text) RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
    SELECT coalesce(shown ~ '[1-9]' AND regexp_replace(shown, 'USD|ARS', '', 'g') !~ '[[:alpha:]]',
                    false)
$$;

COMMENT ON FUNCTION shows_amount(text) IS 'Si el valor mostrado de una celda es un monto distinto de 0 (ej. "USD $1,200"), o sea una factura según la regla R30; falso si está vacía, es 0 o es un texto.';

CREATE FUNCTION invoice_state(color text) RETURNS text LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE lower(coalesce(color, '#ffffff'))
        WHEN '#ffffff' THEN 'a facturar'
        WHEN '#00ffff' THEN 'a confirmar'
        WHEN '#4a86e8' THEN 'confirmada'
        WHEN '#ff9900' THEN 'enviada'
        WHEN '#d9ead3' THEN 'pagada'
        WHEN '#ff00ff' THEN 'retraso'
        ELSE 'color desconocido'
    END
$$;

COMMENT ON FUNCTION invoice_state(text) IS 'Estado de una factura según el color de fondo de su celda (regla R29): sin color o blanco = a facturar, cian = a confirmar, azul = confirmada, naranja = enviada, verde #d9ead3 = pagada, magenta = retraso; cualquier otro, color desconocido.';

CREATE TABLE invoice (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_tab_id      bigint NOT NULL REFERENCES source_tab (id),
    block              text NOT NULL,
    row_key            text NOT NULL,
    series_order       integer NOT NULL CHECK (series_order >= 1),
    month              date NOT NULL CHECK (extract(day FROM month) = 1),
    legal_entity       text NOT NULL REFERENCES legal_entity (name),
    state              text NOT NULL CHECK (state IN
        ('a facturar', 'a confirmar', 'confirmada', 'enviada', 'pagada', 'retraso')),
    amount             numeric NOT NULL,
    currency           text NOT NULL CHECK (currency IN ('USD', 'ARS')),
    net_ars            numeric,
    fx_rate            numeric,
    fx_rate_type       text CHECK (fx_rate_type IN ('mep', 'oficial', 'tipeada')),
    fx_rate_to_confirm boolean NOT NULL,
    inferred_usd       numeric,
    sent_change_id     bigint REFERENCES cell_change (id),
    alias_source       text NOT NULL,
    alias_text         text NOT NULL,
    snapshot_id        bigint NOT NULL REFERENCES snapshot (id),
    cell_ref           text NOT NULL,
    rules_version      text NOT NULL,
    -- The text and its order, not row_key: a row typed "x (2)" is not the second "x".
    UNIQUE (source_tab_id, block, alias_text, series_order, month),
    CHECK ((currency = 'ARS') = (net_ars IS NOT NULL))
);

COMMENT ON TABLE invoice IS 'Factura: una celda con monto de la grilla de meses de Pagos o Pagos ARG, en el bloque del encabezado, con el estado que dice su color (regla R29). Una celda vacía, un 0 o una celda de color desconocido no son factura (regla R30). Se reemplaza entera en cada lectura nueva de la pestaña.';
COMMENT ON COLUMN invoice.id IS 'Identificador interno; cambia en cada reinterpretación.';
COMMENT ON COLUMN invoice.source_tab_id IS 'Pestaña de la que sale.';
COMMENT ON COLUMN invoice.block IS 'Bloque de la pestaña donde está la fila: el del encabezado (Cliente en Pagos, Mes en Pagos ARG).';
COMMENT ON COLUMN invoice.row_key IS 'Texto de la columna clave, normalizado; si se repite en el bloque lleva el orden como sufijo, ej. "cliente x (2)" (regla R26).';
COMMENT ON COLUMN invoice.series_order IS 'Orden de la fila entre las que tienen el mismo texto en el bloque: 1 si no se repite.';
COMMENT ON COLUMN invoice.month IS 'Mes de la factura, el primer día del mes, sacado del encabezado de la columna.';
COMMENT ON COLUMN invoice.legal_entity IS 'Sociedad que factura (regla R25): Craftech S.A. en Pagos ARG, Craftech-io Inc. en el resto.';
COMMENT ON COLUMN invoice.state IS 'Estado según el color de la celda (regla R29): a facturar, a confirmar, confirmada, enviada, pagada o retraso.';
COMMENT ON COLUMN invoice.amount IS 'Monto tal como está en la celda, en la moneda de la columna currency; en Pagos ARG es el bruto con IVA.';
COMMENT ON COLUMN invoice.currency IS 'Moneda del monto: USD en Pagos, ARS en Pagos ARG.';
COMMENT ON COLUMN invoice.net_ars IS 'Solo Pagos ARG: neto en pesos, bruto / 1,21 redondeado a centavos (regla R14). Nulo en USD.';
COMMENT ON COLUMN invoice.fx_rate IS 'Solo Pagos ARG: pesos por dólar de la factura, el de la celda que referencia su fórmula o el número tipeado en ella (regla R10). Nulo si la fórmula no lo deja leer.';
COMMENT ON COLUMN invoice.fx_rate_type IS 'Tipo de esa cotización: mep o oficial según la fila referenciada, tipeada si está escrita a mano en la fórmula (hay un problema cotizacion_tipeada); nulo si la fila referenciada no es de cotización conocida o no hay cotización.';
COMMENT ON COLUMN invoice.fx_rate_to_confirm IS 'Verdadero si no está confirmado qué cotización es: la fila "Dólar oficial" (pregunta F-01 a Emi) o una fila referenciada que no es MEP ni oficial.';
COMMENT ON COLUMN invoice.inferred_usd IS 'Solo Pagos ARG: monto base en dólares inferido de la fórmula, ej. 7200 en =7200*1.21*M1; nulo si la fórmula no lo deja leer.';
COMMENT ON COLUMN invoice.sent_change_id IS 'Último cambio de celda que la pintó de naranja (enviada), del que sale la fecha de envío; nulo si nunca se vio ese cambio.';
COMMENT ON COLUMN invoice.alias_source IS 'Fuente con la que se busca el alias del cliente: "planilla / pestaña", normalizada.';
COMMENT ON COLUMN invoice.alias_text IS 'Texto con el que se busca el alias del cliente: el de la columna clave, normalizado y sin sufijo.';
COMMENT ON COLUMN invoice.snapshot_id IS 'Lectura de la que sale.';
COMMENT ON COLUMN invoice.cell_ref IS 'Celda del monto en notación A1.';
COMMENT ON COLUMN invoice.rules_version IS 'Versión de las reglas con las que se interpretó.';

CREATE TABLE payment (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_tab_id  bigint NOT NULL REFERENCES source_tab (id),
    block          text NOT NULL,
    row_key        text NOT NULL,
    series_order   integer NOT NULL CHECK (series_order >= 1),
    month          date NOT NULL CHECK (extract(day FROM month) = 1),
    legal_entity   text NOT NULL REFERENCES legal_entity (name),
    cell_change_id bigint REFERENCES cell_change (id),
    snapshot_id    bigint NOT NULL REFERENCES snapshot (id),
    rules_version  text NOT NULL,
    UNIQUE (source_tab_id, block, row_key, series_order, month)
);

COMMENT ON TABLE payment IS 'Cobro: uno por cada factura pagada (celda verde, regla R4), con la clave de la factura. La fecha y el autor no se copian: salen del cambio de celda en mcp.cobros. Se reemplaza entero en cada lectura nueva de la pestaña.';
COMMENT ON COLUMN payment.id IS 'Identificador interno; cambia en cada reinterpretación.';
COMMENT ON COLUMN payment.source_tab_id IS 'Pestaña de la factura.';
COMMENT ON COLUMN payment.block IS 'Bloque de la factura.';
COMMENT ON COLUMN payment.row_key IS 'Clave de fila de la factura, con sufijo de orden si se repite.';
COMMENT ON COLUMN payment.series_order IS 'Orden de la fila de la factura entre las que tienen el mismo texto en el bloque.';
COMMENT ON COLUMN payment.month IS 'Mes de la factura.';
COMMENT ON COLUMN payment.legal_entity IS 'Sociedad que facturó.';
COMMENT ON COLUMN payment.cell_change_id IS 'Último cambio de celda que la pintó de verde, buscado por pestaña, bloque, clave de fila, serie y mes (las filas se mueven); nulo si ya estaba verde en la primera lectura o el cambio no se vio.';
COMMENT ON COLUMN payment.snapshot_id IS 'Lectura de la que sale.';
COMMENT ON COLUMN payment.rules_version IS 'Versión de las reglas con las que se interpretó.';

CREATE TABLE client_churn (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_tab_id    bigint NOT NULL REFERENCES source_tab (id),
    block            text NOT NULL,
    row_key          text NOT NULL,
    series_order     integer NOT NULL CHECK (series_order >= 1),
    month            date NOT NULL CHECK (extract(day FROM month) = 1),
    color            text NOT NULL,
    color_to_confirm boolean NOT NULL,
    alias_source     text NOT NULL,
    alias_text       text NOT NULL,
    snapshot_id      bigint NOT NULL REFERENCES snapshot (id),
    cell_ref         text NOT NULL,
    rules_version    text NOT NULL,
    UNIQUE (source_tab_id, block, alias_text, series_order, month)
);

COMMENT ON TABLE client_churn IS 'Baja: una celda pintada sin monto (vacía o 0) en la grilla de Pagos de SleakOps (regla R31). Se reemplaza entera en cada lectura nueva de la pestaña.';
COMMENT ON COLUMN client_churn.id IS 'Identificador interno; cambia en cada reinterpretación.';
COMMENT ON COLUMN client_churn.source_tab_id IS 'Pestaña de la que sale.';
COMMENT ON COLUMN client_churn.block IS 'Bloque de la pestaña donde está la fila.';
COMMENT ON COLUMN client_churn.row_key IS 'Texto de la columna clave, normalizado; con sufijo de orden si se repite en el bloque.';
COMMENT ON COLUMN client_churn.series_order IS 'Orden de la fila entre las que tienen el mismo texto en el bloque: 1 si no se repite.';
COMMENT ON COLUMN client_churn.month IS 'Mes de la celda, el primer día del mes.';
COMMENT ON COLUMN client_churn.color IS 'Color de fondo de la celda en hexadecimal (#rrggbb).';
COMMENT ON COLUMN client_churn.color_to_confirm IS 'Verdadero mientras Emi no confirme qué color marca una baja (pregunta F-05).';
COMMENT ON COLUMN client_churn.alias_source IS 'Fuente con la que se busca el alias del cliente: "planilla / pestaña", normalizada.';
COMMENT ON COLUMN client_churn.alias_text IS 'Texto con el que se busca el alias del cliente: el de la columna clave, normalizado y sin sufijo.';
COMMENT ON COLUMN client_churn.snapshot_id IS 'Lectura de la que sale.';
COMMENT ON COLUMN client_churn.cell_ref IS 'Celda en notación A1.';
COMMENT ON COLUMN client_churn.rules_version IS 'Versión de las reglas con las que se interpretó.';

CREATE TABLE payment_total (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_tab_id bigint NOT NULL REFERENCES source_tab (id),
    row_key       text NOT NULL,
    month         date NOT NULL CHECK (extract(day FROM month) = 1),
    amount        numeric NOT NULL,
    snapshot_id   bigint NOT NULL REFERENCES snapshot (id),
    cell_ref      text NOT NULL,
    rules_version text NOT NULL,
    UNIQUE (source_tab_id, month)
);

COMMENT ON TABLE payment_total IS 'Total por mes que calcula la planilla para las facturas del bloque del encabezado: la primera fila "Total pagos USA" en Pagos y la primera "Total Ingresos" en Pagos ARG. Es contra lo que se controla la interpretación en mcp.paridad_pagos. Se reemplaza entero en cada lectura nueva de la pestaña.';
COMMENT ON COLUMN payment_total.id IS 'Identificador interno; cambia en cada reinterpretación.';
COMMENT ON COLUMN payment_total.source_tab_id IS 'Pestaña de la que sale.';
COMMENT ON COLUMN payment_total.row_key IS 'Texto de la fila del total, normalizado.';
COMMENT ON COLUMN payment_total.month IS 'Mes, el primer día del mes.';
COMMENT ON COLUMN payment_total.amount IS 'Total tal como está en la celda, en la moneda de la pestaña.';
COMMENT ON COLUMN payment_total.snapshot_id IS 'Lectura de la que sale.';
COMMENT ON COLUMN payment_total.cell_ref IS 'Celda del total en notación A1.';
COMMENT ON COLUMN payment_total.rules_version IS 'Versión de las reglas con las que se interpretó.';

COMMENT ON COLUMN issue.issue_type IS 'Tipo de problema: color_desconocido (color de fondo en la grilla de meses que no es uno de los cinco de la regla R29), alineacion_ambigua (la cantidad de filas con una misma clave cambió o una fila cambió de clave y de lugar: se compararon por posición), valor_ilegible (texto no numérico en la grilla de meses), pestana_sin_clasificar (pestaña nueva que nadie clasificó en config/sources.yaml), alias_sin_cliente (fila con montos cuyo texto no tiene un alias que diga de qué cliente es), cotizacion_tipeada (factura de Pagos ARG cuya cotización no sale de una celda referenciada sino de un número escrito a mano, regla R38), cotizacion_discrepante (la MEP de control difiere de la operativa en un mes, regla R10), cotizacion_tipo_a_confirmar (se guardó una cotización sin saber de qué tipo es), funding_duplicado (todavía no se usa), identidad_en_revision (el mismo texto en dos filas de un bloque: se toman como dos series, regla R26), fila_sin_interpretar (fila o columna con montos que no se pudo ubicar en un cliente y un mes).';
COMMENT ON COLUMN issue.stable_key IS 'Clave que identifica al problema entre lecturas, según el tipo: color_desconocido = pestaña + color; alineacion_ambigua = pestaña + bloque + clave de fila; valor_ilegible = pestaña + bloque + clave de fila + columna; pestana_sin_clasificar = planilla + sheetId; alias_sin_cliente = pestaña + texto; identidad_en_revision = pestaña + bloque + clave de fila; fila_sin_interpretar = pestaña + bloque + clave o número de fila (+ columna); cotizacion_discrepante = pestaña + mes; cotizacion_tipo_a_confirmar = pestaña + tipo o fila referenciada; cotizacion_tipeada = pestaña + bloque + clave de fila + columna. Las pestañas van por su identificador interno.';
COMMENT ON COLUMN mcp.issues.tipo IS 'Tipo: color_desconocido (color de fondo en la grilla de meses que no es uno de los cinco de la regla R29), alineacion_ambigua (filas con la misma clave que no se pudieron alinear entre lecturas), valor_ilegible (texto no numérico donde va un monto), pestana_sin_clasificar (pestaña nueva que nadie clasificó), alias_sin_cliente (fila con montos cuyo texto no tiene alias que diga de qué cliente es), cotizacion_tipeada (factura de Pagos ARG con la cotización escrita a mano en vez de referenciada, regla R38), cotizacion_discrepante (la MEP de control difiere de la operativa en un mes, regla R10), cotizacion_tipo_a_confirmar (cotización guardada sin saber de qué tipo es), identidad_en_revision (el mismo texto en dos filas de un bloque: dos series, regla R26), fila_sin_interpretar (fila o columna con montos que no se pudo ubicar en un cliente y un mes), funding_duplicado (todavía no se usa).';
COMMENT ON COLUMN cell_change.old_color IS 'Color de fondo anterior en hexadecimal (#rrggbb). En color, emptied y value (en value, desde T-011).';
COMMENT ON COLUMN cell_change.new_color IS 'Color de fondo nuevo en hexadecimal (#rrggbb). En color y value (en value, desde T-011): un monto tipeado en una celda vacía es el único registro de su color.';

-- The latest snapshot of each tab: facts of older reads are not shown.
CREATE VIEW mcp.facturas AS
SELECT s.title AS planilla, t.name AS pestaña, t.id AS pestaña_id, i.snapshot_id AS lectura_id,
       n.read_at AS leido_en, i.cell_ref AS celda, i.block AS bloque, i.row_key AS clave_fila,
       i.series_order AS serie, i.month AS mes, i.legal_entity AS entidad_legal,
       i.state AS estado, i.amount AS monto, i.currency AS moneda, i.net_ars AS neto_ars,
       i.fx_rate AS cotizacion, i.fx_rate_type AS tipo_cotizacion,
       i.fx_rate_to_confirm AS cotizacion_a_confirmar, i.inferred_usd AS usd_inferido,
       coalesce(sc.attributed_at, sc.window_end) AS enviada_en,
       coalesce(pt.days, 10) AS plazo_dias,
       (coalesce(sc.attributed_at, sc.window_end))::date + coalesce(pt.days, 10) AS vencimiento,
       i.sent_change_id AS cambio_envio_id, c.id AS cliente_id, c.name AS cliente,
       i.rules_version AS version_reglas
FROM invoice i
JOIN (
    SELECT DISTINCT ON (source_tab_id) id, read_at
    FROM snapshot
    ORDER BY source_tab_id, read_at DESC, id DESC
) n ON n.id = i.snapshot_id
JOIN source_tab t ON t.id = i.source_tab_id AND t.active
JOIN source s ON s.id = t.source_id
LEFT JOIN cell_change sc ON sc.id = i.sent_change_id
LEFT JOIN LATERAL (
    SELECT x.client_id FROM client_alias x
    WHERE x.source = i.alias_source AND x.text = i.alias_text
    ORDER BY x.created_at DESC, x.id DESC
    LIMIT 1
) al ON true
LEFT JOIN client c ON c.id = al.client_id
LEFT JOIN LATERAL (
    SELECT min(r.payment_terms_days) AS days
    FROM client_legal_entity r JOIN legal_entity e ON e.billing_system = r.source_system
    WHERE r.client_id = al.client_id AND e.name = i.legal_entity
) pt ON true;

COMMENT ON VIEW mcp.facturas IS 'Facturas de Pagos y Pagos ARG de la última lectura de cada pestaña, con el estado que dice el color de la celda (regla R29). Una celda vaciada deja de ser factura; su historia está en mcp.cambios_de_estado_de_factura. El cliente sale del alias vigente; nulo si el texto no tiene alias. Planilla, pestaña, celda y lectura llevan a la celda de origen.';
COMMENT ON COLUMN mcp.facturas.planilla IS 'Nombre de la planilla de Google Sheets.';
COMMENT ON COLUMN mcp.facturas.pestaña IS 'Nombre de la pestaña: Pagos o Pagos ARG.';
COMMENT ON COLUMN mcp.facturas.pestaña_id IS 'Identificador de la pestaña (mcp.tabs.id).';
COMMENT ON COLUMN mcp.facturas.lectura_id IS 'Lectura de la que sale (mcp.snapshots.id); la celda está en mcp.celdas.';
COMMENT ON COLUMN mcp.facturas.leido_en IS 'Momento de esa lectura.';
COMMENT ON COLUMN mcp.facturas.celda IS 'Celda del monto en notación A1.';
COMMENT ON COLUMN mcp.facturas.bloque IS 'Bloque de la pestaña donde está la fila.';
COMMENT ON COLUMN mcp.facturas.clave_fila IS 'Texto de la fila (el cliente como figura en la planilla), normalizado; con sufijo " (2)" si se repite en el bloque.';
COMMENT ON COLUMN mcp.facturas.serie IS 'Orden de la fila entre las que tienen el mismo texto en el bloque: 1 si no se repite; más de una es otra serie del mismo cliente (regla R26).';
COMMENT ON COLUMN mcp.facturas.mes IS 'Mes de la factura (primer día del mes).';
COMMENT ON COLUMN mcp.facturas.entidad_legal IS 'Sociedad que factura: Craftech S.A. (Pagos ARG) o Craftech-io Inc. (regla R25).';
COMMENT ON COLUMN mcp.facturas.estado IS 'a facturar (sin color), a confirmar (cian), confirmada (azul), enviada (naranja), pagada (verde) o retraso (magenta), regla R29.';
COMMENT ON COLUMN mcp.facturas.monto IS 'Monto tal como está en la celda, en la moneda de la columna moneda; en Pagos ARG es el bruto con IVA.';
COMMENT ON COLUMN mcp.facturas.moneda IS 'USD (Pagos) o ARS (Pagos ARG).';
COMMENT ON COLUMN mcp.facturas.neto_ars IS 'Solo Pagos ARG: bruto / 1,21 (regla R14).';
COMMENT ON COLUMN mcp.facturas.cotizacion IS 'Solo Pagos ARG: pesos por dólar de la factura, de la celda que referencia su fórmula o tipeado en ella (regla R10).';
COMMENT ON COLUMN mcp.facturas.tipo_cotizacion IS 'mep, oficial, tipeada (escrita a mano: hay un problema cotizacion_tipeada) o nulo si la fila referenciada no es de una cotización conocida.';
COMMENT ON COLUMN mcp.facturas.cotizacion_a_confirmar IS 'Verdadero si no está confirmado qué cotización es (el "Dólar oficial", pregunta F-01, u otra fila que no es MEP).';
COMMENT ON COLUMN mcp.facturas.usd_inferido IS 'Solo Pagos ARG: monto base en dólares que aparece en la fórmula, ej. 7200 en =7200*1.21*M1.';
COMMENT ON COLUMN mcp.facturas.enviada_en IS 'Cuándo se pintó de naranja (enviada): el momento de la edición si Drive atribuyó el cambio con certeza, si no el fin de la ventana en que se detectó. Nulo si nunca se vio ese cambio.';
COMMENT ON COLUMN mcp.facturas.plazo_dias IS 'Plazo de pago en días de la razón social del cliente con esta sociedad (el menor si hay varias); 10 si no se conoce.';
COMMENT ON COLUMN mcp.facturas.vencimiento IS 'Fecha de envío más el plazo de pago; nula si no se vio el envío.';
COMMENT ON COLUMN mcp.facturas.cambio_envio_id IS 'Cambio de celda que la pintó de naranja (mcp.changes.id).';
COMMENT ON COLUMN mcp.facturas.cliente_id IS 'Cliente según el alias vigente (mcp.clientes.id); nulo si no hay alias.';
COMMENT ON COLUMN mcp.facturas.cliente IS 'Nombre de fantasía del cliente; nulo si no hay alias.';
COMMENT ON COLUMN mcp.facturas.version_reglas IS 'Versión de las reglas con las que se interpretó.';

CREATE VIEW mcp.cobros AS
SELECT f.planilla, f.pestaña, f.pestaña_id, f.lectura_id, f.celda, f.bloque, f.clave_fila, f.mes,
       f.entidad_legal, f.monto, f.moneda, f.cliente_id, f.cliente,
       coalesce(c.attributed_at, c.window_end) AS fecha,
       CASE WHEN c.attributed_at IS NOT NULL THEN 'editor'
            WHEN c.id IS NOT NULL THEN 'ventana de detección'
            ELSE 'fecha desconocida' END AS origen_fecha,
       c.attribution_certainty AS certeza,
       ARRAY(
           SELECT e.label FROM unnest(c.attributed_editor_ids) WITH ORDINALITY AS a (actor_id, n)
           JOIN v_editor e USING (actor_id) ORDER BY a.n
       ) AS editores,
       p.cell_change_id AS cambio_id, p.rules_version AS version_reglas
FROM payment p
JOIN mcp.facturas f ON f.pestaña_id = p.source_tab_id AND f.lectura_id = p.snapshot_id
    AND f.bloque = p.block AND f.clave_fila = p.row_key AND f.serie = p.series_order
    AND f.mes = p.month
LEFT JOIN cell_change c ON c.id = p.cell_change_id;

COMMENT ON VIEW mcp.cobros IS 'Cobros: uno por factura pagada (celda verde, regla R4) en la última lectura. La fecha y el autor salen del cambio de celda que la pintó de verde, así que la atribución de Drive que llega después se ve sin reinterpretar.';
COMMENT ON COLUMN mcp.cobros.planilla IS 'Nombre de la planilla de Google Sheets.';
COMMENT ON COLUMN mcp.cobros.pestaña IS 'Nombre de la pestaña: Pagos o Pagos ARG.';
COMMENT ON COLUMN mcp.cobros.pestaña_id IS 'Identificador de la pestaña (mcp.tabs.id).';
COMMENT ON COLUMN mcp.cobros.lectura_id IS 'Lectura de la que sale (mcp.snapshots.id).';
COMMENT ON COLUMN mcp.cobros.celda IS 'Celda de la factura en notación A1, en esa lectura.';
COMMENT ON COLUMN mcp.cobros.bloque IS 'Bloque de la pestaña donde está la fila.';
COMMENT ON COLUMN mcp.cobros.clave_fila IS 'Texto de la fila, normalizado; con sufijo " (2)" si se repite en el bloque.';
COMMENT ON COLUMN mcp.cobros.mes IS 'Mes de la factura cobrada (primer día del mes).';
COMMENT ON COLUMN mcp.cobros.entidad_legal IS 'Sociedad que facturó.';
COMMENT ON COLUMN mcp.cobros.monto IS 'Monto de la factura tal como está en la celda.';
COMMENT ON COLUMN mcp.cobros.moneda IS 'USD (Pagos) o ARS (Pagos ARG).';
COMMENT ON COLUMN mcp.cobros.cliente_id IS 'Cliente según el alias vigente; nulo si no hay alias.';
COMMENT ON COLUMN mcp.cobros.cliente IS 'Nombre de fantasía del cliente; nulo si no hay alias.';
COMMENT ON COLUMN mcp.cobros.fecha IS 'Cuándo se pintó de verde: el momento de la edición si Drive la atribuyó a un solo editor, si no el fin de la ventana en que se detectó; nula si ya estaba verde en la primera lectura.';
COMMENT ON COLUMN mcp.cobros.origen_fecha IS 'De dónde sale la fecha: editor, ventana de detección o fecha desconocida.';
COMMENT ON COLUMN mcp.cobros.certeza IS 'Certeza de la atribución del cambio: cierta, una_de, sin_datos; nula si no se atribuyó todavía o no hay cambio.';
COMMENT ON COLUMN mcp.cobros.editores IS 'Editores que pudieron pintarla de verde según Drive.';
COMMENT ON COLUMN mcp.cobros.cambio_id IS 'Cambio de celda que la pintó de verde (mcp.changes.id); nulo si ya estaba verde en la primera lectura o no se vio el cambio.';
COMMENT ON COLUMN mcp.cobros.version_reglas IS 'Versión de las reglas con las que se interpretó.';

CREATE VIEW mcp.bajas AS
SELECT s.title AS planilla, t.name AS pestaña, t.id AS pestaña_id, b.snapshot_id AS lectura_id,
       b.cell_ref AS celda, b.block AS bloque, b.row_key AS clave_fila, b.series_order AS serie,
       b.month AS mes, b.color, b.color_to_confirm AS color_a_confirmar, c.id AS cliente_id,
       c.name AS cliente, b.rules_version AS version_reglas
FROM client_churn b
JOIN (
    SELECT DISTINCT ON (source_tab_id) id
    FROM snapshot
    ORDER BY source_tab_id, read_at DESC, id DESC
) n ON n.id = b.snapshot_id
JOIN source_tab t ON t.id = b.source_tab_id AND t.active
JOIN source s ON s.id = t.source_id
LEFT JOIN LATERAL (
    SELECT x.client_id FROM client_alias x
    WHERE x.source = b.alias_source AND x.text = b.alias_text
    ORDER BY x.created_at DESC, x.id DESC
    LIMIT 1
) al ON true
LEFT JOIN client c ON c.id = al.client_id;

COMMENT ON VIEW mcp.bajas IS 'Bajas de clientes de SleakOps: celdas pintadas sin monto en la grilla de Pagos de SleakOps (regla R31), de la última lectura.';
COMMENT ON COLUMN mcp.bajas.planilla IS 'Nombre de la planilla de Google Sheets.';
COMMENT ON COLUMN mcp.bajas.pestaña IS 'Nombre de la pestaña.';
COMMENT ON COLUMN mcp.bajas.pestaña_id IS 'Identificador de la pestaña (mcp.tabs.id).';
COMMENT ON COLUMN mcp.bajas.lectura_id IS 'Lectura de la que sale (mcp.snapshots.id).';
COMMENT ON COLUMN mcp.bajas.celda IS 'Celda en notación A1.';
COMMENT ON COLUMN mcp.bajas.bloque IS 'Bloque de la pestaña donde está la fila.';
COMMENT ON COLUMN mcp.bajas.clave_fila IS 'Texto de la fila, normalizado; con sufijo " (2)" si se repite en el bloque.';
COMMENT ON COLUMN mcp.bajas.serie IS 'Orden de la fila entre las que tienen el mismo texto en el bloque.';
COMMENT ON COLUMN mcp.bajas.mes IS 'Mes de la celda (primer día del mes).';
COMMENT ON COLUMN mcp.bajas.color IS 'Color de fondo de la celda en hexadecimal (#rrggbb).';
COMMENT ON COLUMN mcp.bajas.color_a_confirmar IS 'Verdadero mientras Emi no confirme qué color marca una baja (pregunta F-05).';
COMMENT ON COLUMN mcp.bajas.cliente_id IS 'Cliente según el alias vigente; nulo si no hay alias.';
COMMENT ON COLUMN mcp.bajas.cliente IS 'Nombre de fantasía del cliente; nulo si no hay alias.';
COMMENT ON COLUMN mcp.bajas.version_reglas IS 'Versión de las reglas con las que se interpretó.';

CREATE VIEW mcp.cambios_de_estado_de_factura AS
SELECT c.id, s.title AS planilla, t.name AS pestaña, t.id AS pestaña_id, c.cell_ref AS celda,
       c.block AS bloque,
       c.row_key || CASE WHEN c.row_ordinal > 1 THEN ' (' || c.row_ordinal || ')' ELSE '' END
           AS clave_fila,
       c.row_ordinal AS serie,
       CASE WHEN c.change_type = 'value' AND NOT shows_amount(c.old_value) THEN 'sin factura'
            ELSE invoice_state(c.old_color) END AS estado_anterior,
       CASE WHEN c.change_type = 'emptied'
                 OR (c.change_type = 'value' AND NOT shows_amount(c.new_value)) THEN 'sin factura'
            ELSE invoice_state(c.new_color) END AS estado_nuevo,
       c.old_value AS valor_anterior, c.new_value AS valor_nuevo,
       coalesce(c.attributed_at, c.window_end) AS fecha,
       c.attribution_certainty AS certeza,
       ARRAY(
           SELECT e.label FROM unnest(c.attributed_editor_ids) WITH ORDINALITY AS a (actor_id, n)
           JOIN v_editor e USING (actor_id) ORDER BY a.n
       ) AS editores,
       c.to_snapshot AS lectura_id
FROM cell_change c
JOIN source_tab t ON t.id = c.source_tab_id AND t.class = 'CARGA'
    AND t.name IN ('Pagos', 'Pagos ARG') AND c.block = t.schema ->> 'header'
JOIN source s ON s.id = t.source_id
WHERE (c.change_type IN ('color', 'emptied')
       OR (c.change_type = 'value' AND shows_amount(c.old_value) <> shows_amount(c.new_value)))
  AND a1_column(c.cell_ref) BETWEEN a1_column(split_part(t.schema ->> 'grid', ':', 1))
                                AND a1_column(split_part(t.schema ->> 'grid', ':', 2));

COMMENT ON VIEW mcp.cambios_de_estado_de_factura IS 'Historia de las celdas de factura de Pagos y Pagos ARG: cada cambio de color, cada celda vaciada, cada monto tipeado donde no había factura y cada 0 o texto tipeado sobre un monto, con el estado anterior y el nuevo según la regla R29, la fecha y quién lo hizo. Sale de los cambios de celda (mcp.changes), así que incluye las facturas que ya no existen.';
COMMENT ON COLUMN mcp.cambios_de_estado_de_factura.id IS 'Identificador del cambio (mcp.changes.id).';
COMMENT ON COLUMN mcp.cambios_de_estado_de_factura.planilla IS 'Nombre de la planilla de Google Sheets.';
COMMENT ON COLUMN mcp.cambios_de_estado_de_factura.pestaña IS 'Nombre de la pestaña: Pagos o Pagos ARG.';
COMMENT ON COLUMN mcp.cambios_de_estado_de_factura.pestaña_id IS 'Identificador de la pestaña (mcp.tabs.id).';
COMMENT ON COLUMN mcp.cambios_de_estado_de_factura.celda IS 'Celda en notación A1, en la lectura que trajo el cambio.';
COMMENT ON COLUMN mcp.cambios_de_estado_de_factura.bloque IS 'Bloque de la pestaña donde está la fila.';
COMMENT ON COLUMN mcp.cambios_de_estado_de_factura.clave_fila IS 'Texto de la fila, normalizado; con sufijo " (2)" si se repite en el bloque, como en mcp.facturas.';
COMMENT ON COLUMN mcp.cambios_de_estado_de_factura.serie IS 'Orden de la fila entre las que tienen el mismo texto en el bloque.';
COMMENT ON COLUMN mcp.cambios_de_estado_de_factura.estado_anterior IS 'Estado antes del cambio según el color (regla R29), "sin factura" si la celda estaba vacía o "color desconocido".';
COMMENT ON COLUMN mcp.cambios_de_estado_de_factura.estado_nuevo IS 'Estado después del cambio, "sin factura" si se vació la celda o "color desconocido".';
COMMENT ON COLUMN mcp.cambios_de_estado_de_factura.valor_anterior IS 'Valor mostrado antes, si el cambio fue de valor o vació la celda.';
COMMENT ON COLUMN mcp.cambios_de_estado_de_factura.valor_nuevo IS 'Valor mostrado después, si el cambio fue de valor.';
COMMENT ON COLUMN mcp.cambios_de_estado_de_factura.fecha IS 'Momento de la edición si Drive la atribuyó a un solo editor, si no el fin de la ventana en que se detectó.';
COMMENT ON COLUMN mcp.cambios_de_estado_de_factura.certeza IS 'Certeza de la atribución: cierta, una_de, sin_datos; nula si todavía no se atribuyó.';
COMMENT ON COLUMN mcp.cambios_de_estado_de_factura.editores IS 'Editores que pudieron hacer el cambio según Drive.';
COMMENT ON COLUMN mcp.cambios_de_estado_de_factura.lectura_id IS 'Lectura que trajo el cambio (mcp.snapshots.id).';

CREATE VIEW mcp.paridad_pagos AS
WITH totals AS (
    SELECT p.source_tab_id, p.month, p.amount FROM payment_total p
    JOIN (
        SELECT DISTINCT ON (source_tab_id) id
        FROM snapshot
        ORDER BY source_tab_id, read_at DESC, id DESC
    ) n ON n.id = p.snapshot_id
), sums AS (
    SELECT pestaña_id AS source_tab_id, mes AS month, sum(monto) AS amount
    FROM mcp.facturas GROUP BY 1, 2
)
SELECT s.title AS planilla, t.name AS pestaña, t.id AS pestaña_id, month AS mes,
       totals.amount AS total_planilla, coalesce(sums.amount, 0) AS suma_facturas,
       -- Sheets adds in binary floating point: noise below a cent is not a difference.
       round(coalesce(totals.amount, 0) - coalesce(sums.amount, 0), 2) AS diferencia
FROM totals FULL JOIN sums USING (source_tab_id, month)
JOIN source_tab t ON t.id = source_tab_id AND t.active
JOIN source s ON s.id = t.source_id;

COMMENT ON VIEW mcp.paridad_pagos IS 'Control de la interpretación: por planilla, pestaña y mes, el total que calcula la planilla (la fila "Total pagos USA" en Pagos, "Total Ingresos" en Pagos ARG) contra la suma de las facturas interpretadas. Una diferencia distinta de 0 delata una factura mal leída o celdas que el total suma y no son facturas.';
COMMENT ON COLUMN mcp.paridad_pagos.planilla IS 'Nombre de la planilla de Google Sheets.';
COMMENT ON COLUMN mcp.paridad_pagos.pestaña IS 'Nombre de la pestaña: Pagos o Pagos ARG.';
COMMENT ON COLUMN mcp.paridad_pagos.pestaña_id IS 'Identificador de la pestaña (mcp.tabs.id).';
COMMENT ON COLUMN mcp.paridad_pagos.mes IS 'Mes (primer día del mes).';
COMMENT ON COLUMN mcp.paridad_pagos.total_planilla IS 'Total de la planilla para ese mes; nulo si la fila del total no tiene número en ese mes.';
COMMENT ON COLUMN mcp.paridad_pagos.suma_facturas IS 'Suma de los montos de las facturas interpretadas de ese mes.';
COMMENT ON COLUMN mcp.paridad_pagos.diferencia IS 'Total de la planilla menos suma de facturas, redondeada al centavo (Sheets suma en punto flotante binario y deja restos de millonésimas); 0 si la interpretación cierra.';

GRANT SELECT ON mcp.facturas TO mcp_reader;
GRANT SELECT ON mcp.cobros TO mcp_reader;
GRANT SELECT ON mcp.bajas TO mcp_reader;
GRANT SELECT ON mcp.cambios_de_estado_de_factura TO mcp_reader;
GRANT SELECT ON mcp.paridad_pagos TO mcp_reader;
