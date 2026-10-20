-- Funding milestones (rule R28): from the AWS blocks of Pagos up to February 2026 and from the
-- FUNDINGS tracker for what was loaded from 25 February 2026. Fundings are never invoices
-- (rule R15): no invoice view reads this table.

CREATE TABLE funding_milestone (
    id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_tab_id        bigint NOT NULL REFERENCES source_tab (id),
    origin               text NOT NULL CHECK (origin IN ('pagos', 'tracker')),
    block                text NOT NULL,
    row_key              text NOT NULL,
    program              text,
    opportunity          text,
    fund_claim_id        text,
    program_order        integer NOT NULL CHECK (program_order >= 1),
    provisional_key      boolean NOT NULL,
    month                date CHECK (extract(day FROM month) = 1),
    amount_usd           numeric NOT NULL,
    status               text,
    business_unit        text,
    load_date            date,
    estimated_signoff    date,
    estimated_collection date,
    invoice_loaded       boolean,
    paid_on              date,
    alias_source         text NOT NULL,
    alias_text           text NOT NULL,
    snapshot_id          bigint NOT NULL REFERENCES snapshot (id),
    cell_ref             text NOT NULL,
    rules_version        text NOT NULL,
    UNIQUE (source_tab_id, cell_ref),
    CHECK ((origin = 'pagos') = (month IS NOT NULL)),
    CHECK (provisional_key = (fund_claim_id IS NULL))
);

COMMENT ON TABLE funding_milestone IS 'Hito de funding de AWS (regla R28): una celda con monto de un bloque de funding de Pagos en un mes hasta febrero de 2026 (origen pagos), o una fila del tracker FUNDINGS con monto cargada desde el 25/2/2026 o todavía sin fecha de carga (origen tracker). Un funding en los dos lados se guarda dos veces y abre funding_duplicado. No es una factura (regla R15). Se reemplaza entero en cada lectura nueva de la pestaña.';
COMMENT ON COLUMN funding_milestone.id IS 'Identificador interno; cambia en cada reinterpretación.';
COMMENT ON COLUMN funding_milestone.source_tab_id IS 'Pestaña de la que sale: Pagos o FUNDINGS.';
COMMENT ON COLUMN funding_milestone.origin IS 'pagos (bloque de funding de Pagos, hasta febrero de 2026) o tracker (pestaña FUNDINGS, cargado desde el 25/2/2026).';
COMMENT ON COLUMN funding_milestone.block IS 'Bloque de la pestaña: en Pagos el bloque de funding ("General", "Funding de AWS confirmados" o "Fundings de AWS"); en el tracker, "EMPRESA".';
COMMENT ON COLUMN funding_milestone.row_key IS 'Texto de la columna clave (la empresa), normalizado; si se repite en el bloque lleva el orden como sufijo, ej. "cliente x (2)".';
COMMENT ON COLUMN funding_milestone.program IS 'Programa de AWS como texto (ej. MAP, POC CASH): columna B en Pagos, "TIPO DE FUNDING" en el tracker. Nulo si la celda está vacía.';
COMMENT ON COLUMN funding_milestone.opportunity IS 'Solo tracker: identificador de la oportunidad ("OPP ID").';
COMMENT ON COLUMN funding_milestone.fund_claim_id IS 'Solo tracker: fund claim ID, si la planilla tiene esa columna y la celda tiene valor. Hoy la columna no existe.';
COMMENT ON COLUMN funding_milestone.program_order IS 'Orden del hito entre los del mismo cliente (texto de la fila) y programa en la pestaña, de arriba abajo y por mes: 1 el primero.';
COMMENT ON COLUMN funding_milestone.provisional_key IS 'Verdadero si el hito no tiene fund claim ID y se identifica por programa + orden.';
COMMENT ON COLUMN funding_milestone.month IS 'Solo Pagos: mes de la columna, el primer día del mes. Nulo en el tracker.';
COMMENT ON COLUMN funding_milestone.amount_usd IS 'Monto en dólares tal como está en la celda ("MONTO A PEDIR" en el tracker).';
COMMENT ON COLUMN funding_milestone.status IS 'Solo tracker: columna STATUS, como texto.';
COMMENT ON COLUMN funding_milestone.business_unit IS 'Solo tracker: columna "Unidad Comercial" (Craftech o SleakOps).';
COMMENT ON COLUMN funding_milestone.load_date IS 'Solo tracker: fecha de carga en el portal de AWS; nula si todavía no se cargó.';
COMMENT ON COLUMN funding_milestone.estimated_signoff IS 'Solo tracker: fecha estimada de firma del sign-off.';
COMMENT ON COLUMN funding_milestone.estimated_collection IS 'Solo tracker: sign-off estimado + 30 días (regla R22). La columna "Fecha Estimada De Cobro" de la planilla no se lee.';
COMMENT ON COLUMN funding_milestone.invoice_loaded IS 'Solo tracker: verdadero si la columna "Invoice cargada" dice "si". Nulo en Pagos.';
COMMENT ON COLUMN funding_milestone.paid_on IS 'Solo tracker: fecha de pago.';
COMMENT ON COLUMN funding_milestone.alias_source IS 'Fuente con la que se busca el alias del cliente: "planilla / pestaña", normalizada.';
COMMENT ON COLUMN funding_milestone.alias_text IS 'Texto con el que se busca el alias del cliente: el de la columna clave, normalizado y sin sufijo.';
COMMENT ON COLUMN funding_milestone.snapshot_id IS 'Lectura de la que sale.';
COMMENT ON COLUMN funding_milestone.cell_ref IS 'Celda del monto en notación A1.';
COMMENT ON COLUMN funding_milestone.rules_version IS 'Versión de las reglas con las que se interpretó.';

COMMENT ON COLUMN issue.issue_type IS 'Tipo de problema: color_desconocido (color de fondo en la grilla de meses que no es uno de los cinco de la regla R29), alineacion_ambigua (la cantidad de filas con una misma clave cambió o una fila cambió de clave y de lugar: se compararon por posición), valor_ilegible (texto no numérico en la grilla de meses o en el monto de un funding), pestana_sin_clasificar (pestaña nueva que nadie clasificó en config/sources.yaml), alias_sin_cliente (fila con montos cuyo texto no tiene un alias que diga de qué cliente es), cotizacion_tipeada (factura de Pagos ARG cuya cotización no sale de una celda referenciada sino de un número escrito a mano, regla R38), cotizacion_discrepante (la MEP de control difiere de la operativa en un mes, regla R10), cotizacion_tipo_a_confirmar (se guardó una cotización sin saber de qué tipo es), funding_duplicado (el mismo funding aparece en el tracker FUNDINGS y en un bloque de funding de Pagos: mismo monto y mismo cliente; se guardan los dos, regla R28), identidad_en_revision (el mismo texto en dos filas de un bloque: se toman como dos series, regla R26), fila_sin_interpretar (fila o columna con montos que no se pudo ubicar en un cliente y un mes, o columna del tracker que falta).';
COMMENT ON COLUMN issue.stable_key IS 'Clave que identifica al problema entre lecturas, según el tipo: color_desconocido = pestaña + color; alineacion_ambigua = pestaña + bloque + clave de fila; valor_ilegible = pestaña + bloque + clave de fila + columna; pestana_sin_clasificar = planilla + sheetId; alias_sin_cliente = pestaña + texto; identidad_en_revision = pestaña + bloque + clave de fila; fila_sin_interpretar = pestaña + bloque + clave o número de fila (+ columna), o pestaña + "falta:" + encabezado; cotizacion_discrepante = pestaña + mes; cotizacion_tipo_a_confirmar = pestaña + tipo o fila referenciada; cotizacion_tipeada = pestaña + bloque + clave de fila + columna; funding_duplicado = pestaña del tracker + clave de fila del tracker + pestaña de Pagos + bloque + clave de fila + mes. Las pestañas van por su identificador interno.';
COMMENT ON COLUMN mcp.issues.tipo IS 'Tipo: color_desconocido (color de fondo en la grilla de meses que no es uno de los cinco de la regla R29), alineacion_ambigua (filas con la misma clave que no se pudieron alinear entre lecturas), valor_ilegible (texto no numérico donde va un monto), pestana_sin_clasificar (pestaña nueva que nadie clasificó), alias_sin_cliente (fila con montos cuyo texto no tiene alias que diga de qué cliente es), cotizacion_tipeada (factura de Pagos ARG con la cotización escrita a mano en vez de referenciada, regla R38), cotizacion_discrepante (la MEP de control difiere de la operativa en un mes, regla R10), cotizacion_tipo_a_confirmar (cotización guardada sin saber de qué tipo es), identidad_en_revision (el mismo texto en dos filas de un bloque: dos series, regla R26), fila_sin_interpretar (fila o columna con montos que no se pudo ubicar en un cliente y un mes, o columna del tracker que falta), funding_duplicado (el mismo funding en el tracker FUNDINGS y en Pagos, con el mismo monto y cliente: se guardan los dos, regla R28).';

-- The latest snapshot of each tab: facts of older reads are not shown.
CREATE VIEW mcp.fundings AS
SELECT s.title AS planilla, t.name AS pestaña, t.id AS pestaña_id, f.snapshot_id AS lectura_id,
       n.read_at AS leido_en, f.cell_ref AS celda, f.origin AS origen, f.block AS bloque,
       f.row_key AS clave_fila, f.program AS programa, f.opportunity AS oportunidad,
       f.fund_claim_id, f.program_order AS orden_en_programa,
       f.provisional_key AS clave_provisional,
       coalesce(f.fund_claim_id,
                coalesce(f.program, 'sin programa') || ' #' || f.program_order) AS clave_hito,
       f.month AS mes, f.amount_usd AS monto_usd, f.status AS estado,
       f.business_unit AS unidad_negocio, f.load_date AS fecha_carga,
       f.estimated_signoff AS signoff_estimado, f.estimated_collection AS cobro_estimado,
       f.invoice_loaded AS invoice_cargada, f.paid_on AS fecha_pago, c.id AS cliente_id,
       c.name AS cliente, f.rules_version AS version_reglas
FROM funding_milestone f
JOIN (
    SELECT DISTINCT ON (source_tab_id) id, read_at
    FROM snapshot
    ORDER BY source_tab_id, read_at DESC, id DESC
) n ON n.id = f.snapshot_id
JOIN source_tab t ON t.id = f.source_tab_id AND t.active
JOIN source s ON s.id = t.source_id
LEFT JOIN LATERAL (
    SELECT x.client_id FROM client_alias x
    WHERE x.source = f.alias_source AND x.text = f.alias_text
    ORDER BY x.created_at DESC, x.id DESC
    LIMIT 1
) al ON true
LEFT JOIN client c ON c.id = al.client_id;

COMMENT ON VIEW mcp.fundings IS 'Hitos de funding de AWS de la última lectura (regla R28): los de los bloques de funding de Pagos en meses hasta febrero de 2026 (origen pagos) y los del tracker FUNDINGS cargados desde el 25/2/2026 o todavía sin cargar (origen tracker). Un funding que está en los dos lados aparece dos veces y tiene un problema funding_duplicado. No son facturas: no se suman con mcp.facturas (regla R15). El cliente sale del alias vigente; nulo si el texto no tiene alias.';
COMMENT ON COLUMN mcp.fundings.planilla IS 'Nombre de la planilla de Google Sheets.';
COMMENT ON COLUMN mcp.fundings.pestaña IS 'Nombre de la pestaña: Pagos o FUNDINGS.';
COMMENT ON COLUMN mcp.fundings.pestaña_id IS 'Identificador de la pestaña (mcp.tabs.id).';
COMMENT ON COLUMN mcp.fundings.lectura_id IS 'Lectura de la que sale (mcp.snapshots.id); la celda está en mcp.celdas.';
COMMENT ON COLUMN mcp.fundings.leido_en IS 'Momento de esa lectura.';
COMMENT ON COLUMN mcp.fundings.celda IS 'Celda del monto en notación A1.';
COMMENT ON COLUMN mcp.fundings.origen IS 'pagos (bloque de funding de Pagos, hasta febrero de 2026) o tracker (pestaña FUNDINGS, desde el 25/2/2026).';
COMMENT ON COLUMN mcp.fundings.bloque IS 'Bloque de la pestaña donde está la fila.';
COMMENT ON COLUMN mcp.fundings.clave_fila IS 'Texto de la fila (la empresa como figura en la planilla), normalizado; con sufijo " (2)" si se repite en el bloque.';
COMMENT ON COLUMN mcp.fundings.programa IS 'Programa de AWS como texto (ej. MAP, POC CASH); nulo si la planilla no lo dice.';
COMMENT ON COLUMN mcp.fundings.oportunidad IS 'Solo tracker: identificador de la oportunidad (OPP ID).';
COMMENT ON COLUMN mcp.fundings.fund_claim_id IS 'Solo tracker: fund claim ID, cuando la planilla lo tenga; hoy no tiene esa columna.';
COMMENT ON COLUMN mcp.fundings.orden_en_programa IS 'Orden del hito entre los del mismo cliente y programa en la pestaña: 1 el primero.';
COMMENT ON COLUMN mcp.fundings.clave_provisional IS 'Verdadero si el hito no tiene fund claim ID y se identifica por programa + orden.';
COMMENT ON COLUMN mcp.fundings.clave_hito IS 'Clave del hito: el fund claim ID si existe; si no, programa + " #" + orden en el programa, ej. "MAP #2" (provisional).';
COMMENT ON COLUMN mcp.fundings.mes IS 'Solo Pagos: mes de la columna (primer día del mes). Nulo en el tracker.';
COMMENT ON COLUMN mcp.fundings.monto_usd IS 'Monto en dólares tal como está en la celda.';
COMMENT ON COLUMN mcp.fundings.estado IS 'Solo tracker: STATUS del funding, como texto.';
COMMENT ON COLUMN mcp.fundings.unidad_negocio IS 'Solo tracker: unidad comercial (Craftech o SleakOps).';
COMMENT ON COLUMN mcp.fundings.fecha_carga IS 'Solo tracker: fecha de carga en el portal de AWS; nula si todavía no se cargó.';
COMMENT ON COLUMN mcp.fundings.signoff_estimado IS 'Solo tracker: fecha estimada de firma del sign-off.';
COMMENT ON COLUMN mcp.fundings.cobro_estimado IS 'Solo tracker: sign-off estimado + 30 días (regla R22); nulo sin sign-off.';
COMMENT ON COLUMN mcp.fundings.invoice_cargada IS 'Solo tracker: verdadero si "Invoice cargada" dice "si".';
COMMENT ON COLUMN mcp.fundings.fecha_pago IS 'Solo tracker: fecha de pago.';
COMMENT ON COLUMN mcp.fundings.cliente_id IS 'Cliente según el alias vigente (mcp.clientes.id); nulo si no hay alias.';
COMMENT ON COLUMN mcp.fundings.cliente IS 'Nombre de fantasía del cliente; nulo si no hay alias.';
COMMENT ON COLUMN mcp.fundings.version_reglas IS 'Versión de las reglas con las que se interpretó.';

-- "Pagos confirmados" has one section per business unit: a row with its name in column A,
-- then one row per year with the year in A and January..December in B..M.
CREATE VIEW mcp.paridad_fundings AS
WITH cells AS (
    SELECT planilla, fila, columna, valor FROM mcp.celdas WHERE pestaña = 'Pagos confirmados'
), units AS (
    SELECT planilla, fila, valor ->> 'stringValue' AS unit FROM cells
    WHERE columna = 1 AND valor ? 'stringValue'
), years AS (
    SELECT y.planilla, y.fila, (y.valor ->> 'numberValue')::numeric::integer AS year,
           (SELECT u.unit FROM units u WHERE u.planilla = y.planilla AND u.fila < y.fila
            ORDER BY u.fila DESC LIMIT 1) AS unit
    FROM cells y
    WHERE y.columna = 1 AND (y.valor ->> 'numberValue')::numeric BETWEEN 2000 AND 2100
), totals AS (
    SELECT y.planilla, y.unit, make_date(y.year, m.columna - 1, 1) AS month,
           (m.valor ->> 'numberValue')::numeric AS amount
    FROM years y
    JOIN cells m ON m.planilla = y.planilla AND m.fila = y.fila AND m.columna BETWEEN 2 AND 13
    WHERE m.valor ? 'numberValue'
), sums AS (
    SELECT planilla, unidad_negocio AS unit, date_trunc('month', fecha_pago)::date AS month,
           sum(monto_usd) AS amount
    FROM mcp.fundings
    WHERE origen = 'tracker' AND invoice_cargada AND fecha_pago IS NOT NULL
    GROUP BY 1, 2, 3
)
SELECT coalesce(totals.planilla, sums.planilla) AS planilla,
       coalesce(totals.unit, sums.unit) AS unidad_negocio,
       coalesce(totals.month, sums.month) AS mes, totals.amount AS total_planilla,
       coalesce(sums.amount, 0) AS suma_fundings,
       -- Sheets adds in binary floating point: noise below a cent is not a difference.
       round(coalesce(totals.amount, 0) - coalesce(sums.amount, 0), 2) AS diferencia
FROM totals FULL JOIN sums ON sums.planilla = totals.planilla
    AND lower(sums.unit) = lower(totals.unit) AND sums.month = totals.month;

COMMENT ON VIEW mcp.paridad_fundings IS 'Control de la interpretación del tracker FUNDINGS: por planilla, unidad comercial y mes, el total de la pestaña "Pagos confirmados" (que suma "MONTO A PEDIR" de las filas con "Invoice cargada" = si por mes de "Fecha de pago") contra la suma de los hitos interpretados del tracker con invoice cargada y fecha de pago en ese mes. Los hitos cargados antes del 25/2/2026 están en Pagos y no en el tracker interpretado (regla R28): si alguno se pagó, la diferencia lo muestra.';
COMMENT ON COLUMN mcp.paridad_fundings.planilla IS 'Nombre de la planilla de Google Sheets del tracker.';
COMMENT ON COLUMN mcp.paridad_fundings.unidad_negocio IS 'Unidad comercial: la sección de "Pagos confirmados" (Craftech o SleakOps).';
COMMENT ON COLUMN mcp.paridad_fundings.mes IS 'Mes de pago (primer día del mes).';
COMMENT ON COLUMN mcp.paridad_fundings.total_planilla IS 'Total de "Pagos confirmados" para esa unidad y mes; nulo si la planilla no tiene ese mes.';
COMMENT ON COLUMN mcp.paridad_fundings.suma_fundings IS 'Suma de los montos de los hitos del tracker interpretados, con invoice cargada y pagados en ese mes.';
COMMENT ON COLUMN mcp.paridad_fundings.diferencia IS 'Total de la planilla menos suma de fundings, redondeada al centavo; 0 si la interpretación cierra.';

GRANT SELECT ON mcp.fundings TO mcp_reader;
GRANT SELECT ON mcp.paridad_fundings TO mcp_reader;
