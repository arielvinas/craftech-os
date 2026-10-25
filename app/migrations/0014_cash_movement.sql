-- Bank movements of the Consolidado tab of "Base informe Craftech " (ADR-003): one row per row
-- of the tab, replaced as a whole on every new read. Rubro "01. Sueldos" and Tipo Mov "Sueldos"
-- keep no Detalle, Subdetalle or Equipo: they can hold names of people. craftech_app owns the
-- table; nothing is granted to mcp_reader yet (the MCP views are T-019).

CREATE TABLE cash_movement (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_tab_id bigint NOT NULL REFERENCES source_tab (id),
    snapshot_id   bigint NOT NULL REFERENCES snapshot (id),
    rules_version text NOT NULL,
    row_key       text NOT NULL,
    cell_ref      text NOT NULL,
    month         date NOT NULL CHECK (extract(day FROM month) = 1),
    bank          text,
    legal_entity  text REFERENCES legal_entity (name),
    historical    boolean NOT NULL,
    adjustment    boolean NOT NULL,
    currency      text CHECK (currency IN ('ARS', 'USD', 'USDC')),
    amount        numeric,
    fx_rate       numeric,
    amount_usd    numeric,
    movement_type text CHECK (movement_type IN
        ('Egresos', 'Sueldos', 'Ingresos', 'Impuestos', 'Ingresos financieros', 'Dividendos',
         'Interno')),
    rubro         text,
    agrupador     text,
    detalle       text,
    subdetalle    text,
    equipo        text,
    UNIQUE (source_tab_id, row_key),
    CHECK (legal_entity IS NULL OR NOT (historical OR adjustment)),
    CONSTRAINT cash_movement_sueldos_without_detail CHECK (
        (rubro IS DISTINCT FROM '01. Sueldos' AND movement_type IS DISTINCT FROM 'Sueldos')
        OR (detalle IS NULL AND subdetalle IS NULL AND equipo IS NULL))
);

COMMENT ON TABLE cash_movement IS 'Movimiento bancario: una fila de la pestaña Consolidado de «Base informe Craftech », que junta las pestañas de cada banco y las de ajuste (ADR-003). Se reemplaza entero en cada lectura nueva de la pestaña; una lectura con otros encabezados no se interpreta y quedan los movimientos de la anterior. En el rubro «01. Sueldos» y en el tipo de movimiento Sueldos no se guardan Detalle, Subdetalle ni Equipo, porque pueden traer nombres de personas: los sueldos van solo como total.';
COMMENT ON COLUMN cash_movement.id IS 'Identificador interno.';
COMMENT ON COLUMN cash_movement.source_tab_id IS 'Pestaña de la que sale.';
COMMENT ON COLUMN cash_movement.snapshot_id IS 'Lectura de la que sale.';
COMMENT ON COLUMN cash_movement.rules_version IS 'Versión de las reglas con las que se interpretó.';
COMMENT ON COLUMN cash_movement.row_key IS 'Número de fila en la pestaña ("fila 2"): Consolidado no tiene otra clave estable.';
COMMENT ON COLUMN cash_movement.cell_ref IS 'Celda de "Amount" de la fila en notación A1.';
COMMENT ON COLUMN cash_movement.month IS 'Mes del movimiento ("Mes Corriente"), el primer día del mes.';
COMMENT ON COLUMN cash_movement.bank IS 'Banco ("Bank"), tal como está en la celda.';
COMMENT ON COLUMN cash_movement.legal_entity IS 'Sociedad dueña de la cuenta, según el banco (regla ratificada de cuentas): Craftech S.A. para Galicia, Macro, Credicoop y Caja Córdoba; Craftech-io Inc. para Mercury y Mesh. Nula en las cuentas históricas, en los ajustes y en un banco desconocido (problema cash_unknown_bank).';
COMMENT ON COLUMN cash_movement.historical IS 'Verdadero si la cuenta es histórica: VETA y cripto.';
COMMENT ON COLUMN cash_movement.adjustment IS 'Verdadero si la fila viene de una pestaña de ajuste: banco CLIENTES o AFIP.';
COMMENT ON COLUMN cash_movement.currency IS 'Moneda ("Moneda"): ARS, USD o USDC. Nula si la celda trae otra cosa (problema fila_sin_interpretar).';
COMMENT ON COLUMN cash_movement.amount IS 'Monto en su moneda ("Amount"), con su signo. Nulo si la celda está vacía o no es un número (problema valor_ilegible).';
COMMENT ON COLUMN cash_movement.fx_rate IS 'Tipo de cambio de la fila ("TC"), tal como está en la celda.';
COMMENT ON COLUMN cash_movement.amount_usd IS 'Monto en dólares ("Amount USD"), tal como está en la celda.';
COMMENT ON COLUMN cash_movement.movement_type IS 'Tipo de movimiento ("Tipo Mov"): Egresos, Sueldos, Ingresos, Impuestos, Ingresos financieros o Dividendos; Interno para la transferencia de Mercury a Mesh (rubro «CAJA. Mesh», agrupador MESH), que no se cuenta dos veces porque el gasto se registra en Mesh. Nulo si la celda trae otra cosa (problema fila_sin_interpretar).';
COMMENT ON COLUMN cash_movement.rubro IS 'Rubro ("Rubro"), tal como está en la celda; config/cashflow_rows.yaml dice en qué fila del cashflow suma.';
COMMENT ON COLUMN cash_movement.agrupador IS 'Agrupador ("Agrupador"), tal como está en la celda; en «01. Sueldos», CCSS son las cargas sociales.';
COMMENT ON COLUMN cash_movement.detalle IS 'Detalle ("Detalle"); siempre nulo en el rubro «01. Sueldos» y en el tipo de movimiento Sueldos.';
COMMENT ON COLUMN cash_movement.subdetalle IS 'Subdetalle ("Subdetalle"); siempre nulo en el rubro «01. Sueldos» y en el tipo de movimiento Sueldos.';
COMMENT ON COLUMN cash_movement.equipo IS 'Equipo ("Equipo"); siempre nulo en el rubro «01. Sueldos» y en el tipo de movimiento Sueldos.';

ALTER TABLE issue DROP CONSTRAINT issue_issue_type_check;
ALTER TABLE issue ADD CONSTRAINT issue_issue_type_check CHECK (issue_type IN
    ('color_desconocido', 'alineacion_ambigua', 'valor_ilegible', 'pestana_sin_clasificar',
     'alias_sin_cliente', 'cotizacion_tipeada', 'cotizacion_discrepante',
     'cotizacion_tipo_a_confirmar', 'funding_duplicado', 'identidad_en_revision',
     'fila_sin_interpretar', 'cash_header_mismatch', 'cash_unknown_bank',
     'cash_unmapped_rubro'));

COMMENT ON COLUMN issue.issue_type IS 'Tipo de problema: color_desconocido (color de fondo en la grilla de meses que no es uno de los cinco de la regla R29), alineacion_ambigua (la cantidad de filas con una misma clave cambió o una fila cambió de clave y de lugar: se compararon por posición), valor_ilegible (texto no numérico en la grilla de meses o en el monto de un funding), pestana_sin_clasificar (pestaña nueva que nadie clasificó en config/sources.yaml), alias_sin_cliente (fila con montos cuyo texto no tiene un alias que diga de qué cliente es), cotizacion_tipeada (factura de Pagos ARG cuya cotización no sale de una celda referenciada sino de un número escrito a mano, regla R38), cotizacion_discrepante (la MEP de control difiere de la operativa en un mes, regla R10), cotizacion_tipo_a_confirmar (se guardó una cotización sin saber de qué tipo es), funding_duplicado (el mismo funding aparece en el tracker FUNDINGS y en un bloque de funding de Pagos: mismo monto y mismo cliente; se guardan los dos, regla R28), identidad_en_revision (el mismo texto en dos filas de un bloque: se toman como dos series, regla R26), fila_sin_interpretar (fila o columna con montos que no se pudo ubicar en un cliente y un mes, o columna del tracker que falta), cash_header_mismatch (los encabezados de la pestaña Consolidado de «Base informe Craftech » no son los 17 esperados: esa lectura no se interpreta y quedan los movimientos de la anterior), cash_unknown_bank (banco de Consolidado que no está en la lista de bancos y entidades del esquema: la fila se guarda sin entidad), cash_unmapped_rubro (rubro o agrupador de Consolidado que ninguna regla de config/cashflow_rows.yaml nombra).';
COMMENT ON COLUMN issue.stable_key IS 'Clave que identifica al problema entre lecturas, según el tipo: color_desconocido = pestaña + color; alineacion_ambigua = pestaña + bloque + clave de fila; valor_ilegible = pestaña + bloque + clave de fila + columna; pestana_sin_clasificar = planilla + sheetId; alias_sin_cliente = pestaña + texto; identidad_en_revision = pestaña + bloque + clave de fila; fila_sin_interpretar = pestaña + bloque + clave o número de fila (+ columna), o pestaña + "falta:" + encabezado; cotizacion_discrepante = pestaña + mes; cotizacion_tipo_a_confirmar = pestaña + tipo o fila referenciada; cotizacion_tipeada = pestaña + bloque + clave de fila + columna; funding_duplicado = pestaña del tracker + clave de fila del tracker + pestaña de Pagos + bloque + clave de fila + mes. cash_header_mismatch = pestaña + "encabezados"; cash_unknown_bank = pestaña + banco; cash_unmapped_rubro = pestaña + rubro (+ agrupador, si alguna regla nombra el rubro). Las pestañas van por su identificador interno.';
COMMENT ON COLUMN mcp.issues.tipo IS 'Tipo: color_desconocido (color de fondo en la grilla de meses que no es uno de los cinco de la regla R29), alineacion_ambigua (filas con la misma clave que no se pudieron alinear entre lecturas), valor_ilegible (texto no numérico donde va un monto), pestana_sin_clasificar (pestaña nueva que nadie clasificó), alias_sin_cliente (fila con montos cuyo texto no tiene alias que diga de qué cliente es), cotizacion_tipeada (factura de Pagos ARG con la cotización escrita a mano en vez de referenciada, regla R38), cotizacion_discrepante (la MEP de control difiere de la operativa en un mes, regla R10), cotizacion_tipo_a_confirmar (cotización guardada sin saber de qué tipo es), identidad_en_revision (el mismo texto en dos filas de un bloque: dos series, regla R26), fila_sin_interpretar (fila o columna con montos que no se pudo ubicar en un cliente y un mes, o columna del tracker que falta), funding_duplicado (el mismo funding en el tracker FUNDINGS y en Pagos, con el mismo monto y cliente: se guardan los dos, regla R28), cash_header_mismatch (la pestaña Consolidado no tiene los 17 encabezados esperados: no se interpretó esa lectura), cash_unknown_bank (banco de Consolidado sin entidad conocida), cash_unmapped_rubro (rubro o agrupador de Consolidado sin regla en el cashflow).';
