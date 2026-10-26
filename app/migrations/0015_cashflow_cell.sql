-- Monthly cashflow (ADR-003, T-019): the rows of config/cashflow_rows.yaml and the cells of the
-- Resumen tab of "CASH FLOW MENSUAL". Every value of cashflow_cell is computed from
-- cash_movement (decision of 2026-10-26): the Resumen only places rows and months, and its
-- values stay in cashflow_sheet_cell for the parity check (T-020). What has no ratified rule
-- has no value and says why. The MCP views are granted to mcp_reader only.

CREATE TABLE cashflow_row (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    block       text NOT NULL,
    block_order integer NOT NULL,
    label       text NOT NULL,
    row_order   integer NOT NULL,
    unit        text NOT NULL CHECK (unit IN ('ars', 'usd')),
    rubros      text[] NOT NULL DEFAULT '{}',
    agrupadores text[] NOT NULL DEFAULT '{}',
    banks       text[] NOT NULL DEFAULT '{}',
    balance     text CHECK (balance IN ('inicial', 'final')),
    adds        text[] NOT NULL DEFAULT '{}',
    sign        smallint NOT NULL DEFAULT 1 CHECK (sign IN (1, -1)),
    parametro   text,
    UNIQUE (block, label),
    CHECK (balance IS NULL OR cardinality(banks) > 0)
);

COMMENT ON TABLE cashflow_row IS 'Fila del cashflow mensual, tal como la define config/cashflow_rows.yaml (ADR-003): de qué bloque es, en qué unidad se muestra y cómo se calcula desde los movimientos bancarios. Solo etiquetas, ningún monto. Se reemplaza entera cada vez que se proyecta el Resumen.';
COMMENT ON COLUMN cashflow_row.id IS 'Identificador interno; cambia en cada proyección.';
COMMENT ON COLUMN cashflow_row.block IS 'Bloque del cashflow, por ejemplo «Craftech Inc. en dólares».';
COMMENT ON COLUMN cashflow_row.block_order IS 'Orden del bloque en el cashflow, desde 0.';
COMMENT ON COLUMN cashflow_row.label IS 'Fila, con el texto de la pestaña Resumen, por ejemplo «Saldo Final».';
COMMENT ON COLUMN cashflow_row.row_order IS 'Orden de la fila dentro del bloque, desde 0.';
COMMENT ON COLUMN cashflow_row.unit IS 'Unidad del bloque: ars (pesos, solo movimientos en ARS) o usd (dólares, solo movimientos en USD).';
COMMENT ON COLUMN cashflow_row.rubros IS 'Rubros cuyos movimientos suma la fila; vacío si no filtra por rubro.';
COMMENT ON COLUMN cashflow_row.agrupadores IS 'Agrupadores cuyos movimientos suma la fila; vacío si no filtra por agrupador.';
COMMENT ON COLUMN cashflow_row.banks IS 'Bancos cuyos movimientos suma la fila; vacío si no filtra por banco.';
COMMENT ON COLUMN cashflow_row.balance IS 'Fila de saldo: inicial (todos los movimientos de sus bancos antes del mes) o final (hasta el mes incluido). Nula si no es un saldo.';
COMMENT ON COLUMN cashflow_row.adds IS 'Filas del mismo bloque que suma (subtotal); vacío si no es un subtotal.';
COMMENT ON COLUMN cashflow_row.sign IS '1, o -1 para mostrar positivas las salidas, como en el Resumen.';
COMMENT ON COLUMN cashflow_row.parametro IS 'Si la fila es la que el software llena en los meses proyectados para cerrar el mes con 4.000.000 de pesos (parámetro ratificado), qué representa; nula en las demás.';

CREATE TABLE cashflow_sheet_cell (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_tab_id bigint NOT NULL REFERENCES source_tab (id),
    snapshot_id   bigint NOT NULL REFERENCES snapshot (id),
    block         text NOT NULL,
    label         text NOT NULL,
    month         date NOT NULL CHECK (extract(day FROM month) = 1),
    value         numeric,
    cell_ref      text NOT NULL,
    has_formula   boolean NOT NULL,
    UNIQUE (source_tab_id, block, label, month)
);

COMMENT ON TABLE cashflow_sheet_cell IS 'Celda de la pestaña «Resumen mensual Cash Flow ARG-USA» de «CASH FLOW MENSUAL» en una fila del cashflow y un mes (ADR-003). Ubica las filas y los meses del cashflow en la pestaña; su valor es solo para el control de paridad, nunca se muestra como valor del cashflow (decisión de Ariel del 26-oct-2026). Se reemplaza entera en cada lectura nueva de la pestaña.';
COMMENT ON COLUMN cashflow_sheet_cell.id IS 'Identificador interno; cambia en cada proyección.';
COMMENT ON COLUMN cashflow_sheet_cell.source_tab_id IS 'Pestaña de la que sale.';
COMMENT ON COLUMN cashflow_sheet_cell.snapshot_id IS 'Lectura de la que sale.';
COMMENT ON COLUMN cashflow_sheet_cell.block IS 'Bloque del cashflow (cashflow_row.block).';
COMMENT ON COLUMN cashflow_sheet_cell.label IS 'Fila del cashflow (cashflow_row.label).';
COMMENT ON COLUMN cashflow_sheet_cell.month IS 'Mes de la columna, el primer día del mes.';
COMMENT ON COLUMN cashflow_sheet_cell.value IS 'Valor tal como está en la celda; nulo si está vacía o no es un número. Solo para la paridad.';
COMMENT ON COLUMN cashflow_sheet_cell.cell_ref IS 'Celda en notación A1.';
COMMENT ON COLUMN cashflow_sheet_cell.has_formula IS 'Verdadero si la celda tiene fórmula; falso si el valor está escrito a mano.';

-- One cell per row of the cashflow and month of the Resumen. Real months are before the
-- current one; the current one is computed with what there is; projected months have no
-- ratified rule yet, so no value.
CREATE VIEW cashflow_cell AS
WITH months AS (
    SELECT DISTINCT month FROM cashflow_sheet_cell
), moves AS (
    SELECT bank, currency, rubro, agrupador, month, sum(amount) AS amount
    FROM cash_movement
    GROUP BY bank, currency, rubro, agrupador, month
), base AS (
    SELECT r.*, m.month,
           CASE
               WHEN r.balance IS NOT NULL THEN (
                   SELECT coalesce(sum(v.amount), 0) FROM moves v
                   WHERE v.bank = ANY (r.banks) AND v.currency = upper(r.unit)
                     AND (v.month < m.month OR (r.balance = 'final' AND v.month = m.month)))
               WHEN cardinality(r.rubros) + cardinality(r.agrupadores) > 0 THEN r.sign * (
                   SELECT coalesce(sum(v.amount), 0) FROM moves v
                   WHERE v.month = m.month AND v.currency = upper(r.unit)
                     AND (cardinality(r.rubros) = 0 OR v.rubro = ANY (r.rubros))
                     AND (cardinality(r.agrupadores) = 0 OR v.agrupador = ANY (r.agrupadores))
                     AND (cardinality(r.banks) = 0 OR v.bank = ANY (r.banks)))
           END AS computed
    FROM cashflow_row r CROSS JOIN months m
), computed AS (
    SELECT b.*,
           CASE WHEN cardinality(b.adds) = 0 THEN b.computed ELSE (
               SELECT sum(a.computed) FROM base a
               WHERE a.block = b.block AND a.month = b.month AND a.label = ANY (b.adds))
           END AS value,
           CASE WHEN b.month < date_trunc('month', current_date) THEN 'real'
                WHEN b.month = date_trunc('month', current_date) THEN 'en_curso'
                ELSE 'proyectado' END AS period
    FROM base b
)
SELECT c.block, c.block_order, c.label, c.row_order, c.month, c.period,
       CASE WHEN c.period <> 'proyectado' THEN c.value END AS value,
       c.unit,
       CASE WHEN c.period = 'proyectado' AND c.parametro IS NOT NULL THEN 'parametro'
            WHEN c.period = 'proyectado' OR c.value IS NULL THEN 'sin_regla'
            ELSE 'recalculada' END AS origin,
       CASE WHEN c.period = 'proyectado' AND c.parametro IS NOT NULL THEN c.parametro
            WHEN c.period = 'proyectado' THEN 'mes proyectado: sin regla de proyección ratificada'
            WHEN c.value IS NULL THEN 'fila sin regla ratificada para calcularla desde los movimientos'
       END AS motivo,
       s.cell_ref, s.snapshot_id, s.source_tab_id
FROM computed c
LEFT JOIN cashflow_sheet_cell s
    ON s.block = c.block AND s.label = c.label AND s.month = c.month;

COMMENT ON VIEW cashflow_cell IS 'Cashflow mensual: una celda por fila del cashflow y mes de la pestaña Resumen, con el valor calculado desde los movimientos bancarios de Consolidado (decisión de Ariel del 26-oct-2026: ningún valor se toma del Resumen). Lo que no tiene regla ratificada queda sin valor y con su motivo.';
COMMENT ON COLUMN cashflow_cell.block IS 'Bloque del cashflow.';
COMMENT ON COLUMN cashflow_cell.block_order IS 'Orden del bloque, desde 0.';
COMMENT ON COLUMN cashflow_cell.label IS 'Fila del cashflow.';
COMMENT ON COLUMN cashflow_cell.row_order IS 'Orden de la fila dentro del bloque, desde 0.';
COMMENT ON COLUMN cashflow_cell.month IS 'Mes, el primer día del mes.';
COMMENT ON COLUMN cashflow_cell.period IS 'real (antes del mes en curso), en_curso (el mes de hoy, calculado con los movimientos que hay) o proyectado (después).';
COMMENT ON COLUMN cashflow_cell.value IS 'Valor calculado desde los movimientos, en la unidad del bloque; nulo si la fila no tiene regla ratificada o el mes es proyectado.';
COMMENT ON COLUMN cashflow_cell.unit IS 'ars o usd.';
COMMENT ON COLUMN cashflow_cell.origin IS 'recalculada (sale de los movimientos), sin_regla (sin valor: fila sin regla ratificada o mes proyectado) o parametro (fila que se llenará con el parámetro ratificado de cerrar el mes con 4.000.000 de pesos; sin valor hasta que se ratifiquen las reglas de proyección).';
COMMENT ON COLUMN cashflow_cell.motivo IS 'Por qué la celda no tiene valor; nulo si lo tiene.';
COMMENT ON COLUMN cashflow_cell.cell_ref IS 'Celda de la fila y el mes en la pestaña Resumen, en notación A1; nula si la fila no está en la pestaña.';
COMMENT ON COLUMN cashflow_cell.snapshot_id IS 'Lectura del Resumen que ubicó la celda.';
COMMENT ON COLUMN cashflow_cell.source_tab_id IS 'Pestaña Resumen.';

-- Proposed by the ADR, to be ratified by Emi and Ro; the formula goes next to the number.
CREATE VIEW cashflow_indicator AS
WITH now AS (
    SELECT date_trunc('month', current_date)::date AS current_month
), inc AS (
    SELECT month, label, value FROM cashflow_cell WHERE block = 'Craftech Inc. en dólares'
), caja AS (
    SELECT (current_month - interval '1 month')::date AS month,
           (SELECT value FROM inc
            WHERE label = 'Saldo Final' AND month = current_month - interval '1 month') AS value
    FROM now
), outflow AS (
    SELECT CASE WHEN count(total) = 3 THEN avg(total) END AS value
    FROM (
        SELECT CASE WHEN count(value) = 3 THEN sum(value) END AS total
        FROM inc, now
        WHERE label IN ('Sueldos', 'Gastos', 'USD enviados a la S.A.')
          AND month >= current_month - interval '3 months' AND month < current_month
        GROUP BY month
    ) totals
), march AS (
    SELECT make_date(extract(year FROM current_month)::integer
                     + (extract(month FROM current_month) > 3)::integer, 3, 1) AS month
    FROM now
)
SELECT 'caja_hoy' AS indicator, 1 AS position, caja.month, caja.value, 'usd' AS unit,
       'Saldo Final de «Craftech Inc. en dólares» del último mes real cerrado (el anterior al mes en curso).' AS formula,
       true AS proposed
FROM caja
UNION ALL
SELECT 'salida_mensual', 2, caja.month, outflow.value, 'usd',
       'Promedio de Sueldos + Gastos + USD enviados a la S.A. de «Craftech Inc. en dólares» en los últimos 3 meses reales cerrados; nulo si falta alguno.',
       true
FROM caja, outflow
UNION ALL
SELECT 'cobertura', 3, caja.month, caja.value / nullif(outflow.value, 0), 'meses',
       'Caja hoy ÷ salida mensual.', true
FROM caja, outflow
UNION ALL
SELECT 'cierre_marzo', 4, march.month,
       (SELECT value FROM cashflow_cell
        WHERE block = 'Craftech Inc. en dólares' AND label = 'Saldo Final' AND month = march.month),
       'usd', 'Saldo Final de «Craftech Inc. en dólares» en el próximo marzo; nulo mientras sea un mes proyectado.',
       true
FROM march
UNION ALL
SELECT 'cierre_marzo_con_pagos_proyectados', 5, march.month,
       (SELECT value FROM cashflow_cell
        WHERE block = 'Craftech Inc. con pagos proyectados' AND label = 'Saldo Final'
          AND month = march.month),
       'usd', 'Saldo Final de «Craftech Inc. con pagos proyectados» en el próximo marzo; nulo mientras sea un mes proyectado.',
       true
FROM march;

COMMENT ON VIEW cashflow_indicator IS 'Indicadores de cabecera del cashflow (ADR-003), solo de Craftech Inc. en dólares (decisión de Ariel del 26-oct-2026). Propuestos, a ratificar por Emi y Ro: cada uno trae su fórmula.';
COMMENT ON COLUMN cashflow_indicator.indicator IS 'caja_hoy, salida_mensual, cobertura, cierre_marzo o cierre_marzo_con_pagos_proyectados.';
COMMENT ON COLUMN cashflow_indicator.position IS 'Orden en la cabecera, desde 1.';
COMMENT ON COLUMN cashflow_indicator.month IS 'Mes al que se refiere: el último mes real cerrado, o el próximo marzo para los cierres.';
COMMENT ON COLUMN cashflow_indicator.value IS 'Valor; nulo si falta algún dato para calcularlo.';
COMMENT ON COLUMN cashflow_indicator.unit IS 'usd o meses.';
COMMENT ON COLUMN cashflow_indicator.formula IS 'Fórmula, en palabras, para mostrar junto al número.';
COMMENT ON COLUMN cashflow_indicator.proposed IS 'Verdadero mientras Emi y Ro no ratifiquen la fórmula.';

CREATE VIEW mcp.caja_mensual AS
SELECT c.block AS bloque, c.block_order AS orden_bloque, c.label AS fila,
       c.row_order AS orden_fila, c.month AS mes, c.period AS periodo, c.value AS valor,
       c.unit AS unidad, c.origin AS origen, c.motivo, s.title AS planilla, t.name AS pestaña,
       c.cell_ref AS celda, c.source_tab_id AS pestaña_id, c.snapshot_id AS lectura_id
FROM cashflow_cell c
LEFT JOIN source_tab t ON t.id = c.source_tab_id
LEFT JOIN source s ON s.id = t.source_id;

COMMENT ON VIEW mcp.caja_mensual IS 'Cashflow mensual con los bloques y filas de la pestaña «Resumen mensual Cash Flow ARG-USA» de «CASH FLOW MENSUAL» (ADR-003). Cada valor se calcula desde los movimientos bancarios de mcp.movimientos_de_caja; ninguno se toma de la planilla (decisión de Ariel del 26-oct-2026). Los meses proyectados y las filas sin regla ratificada no tienen valor y dicen por qué en motivo. Los sueldos van solo como total.';
COMMENT ON COLUMN mcp.caja_mensual.bloque IS 'Bloque: «Argentina en miles de pesos», «Saldo final en dólares», «Craftech Inc. en dólares», «Craftech Inc. con pagos proyectados» o «Diferencia entre proyectado y real».';
COMMENT ON COLUMN mcp.caja_mensual.orden_bloque IS 'Orden del bloque, desde 0.';
COMMENT ON COLUMN mcp.caja_mensual.fila IS 'Fila, con el texto de la pestaña.';
COMMENT ON COLUMN mcp.caja_mensual.orden_fila IS 'Orden de la fila dentro del bloque, desde 0.';
COMMENT ON COLUMN mcp.caja_mensual.mes IS 'Mes (primer día del mes).';
COMMENT ON COLUMN mcp.caja_mensual.periodo IS 'real (antes del mes en curso), en_curso (el mes de hoy, con los movimientos que hay) o proyectado.';
COMMENT ON COLUMN mcp.caja_mensual.valor IS 'Valor calculado desde los movimientos, en la unidad; nulo si origen no es recalculada.';
COMMENT ON COLUMN mcp.caja_mensual.unidad IS 'ars (pesos) o usd (dólares).';
COMMENT ON COLUMN mcp.caja_mensual.origen IS 'recalculada (sale de los movimientos), sin_regla (fila sin regla ratificada o mes proyectado: sin valor) o parametro (fila del parámetro ratificado de cerrar el mes con 4.000.000 de pesos en un mes proyectado: sin valor hasta que se ratifiquen las reglas de proyección).';
COMMENT ON COLUMN mcp.caja_mensual.motivo IS 'Por qué no hay valor; nulo si lo hay.';
COMMENT ON COLUMN mcp.caja_mensual.planilla IS 'Planilla donde está la celda equivalente: CASH FLOW MENSUAL.';
COMMENT ON COLUMN mcp.caja_mensual.pestaña IS 'Pestaña donde está la celda equivalente.';
COMMENT ON COLUMN mcp.caja_mensual.celda IS 'Celda equivalente en la pestaña, en notación A1; nula si la fila no está en la pestaña.';
COMMENT ON COLUMN mcp.caja_mensual.pestaña_id IS 'Identificador de la pestaña (mcp.tabs.id).';
COMMENT ON COLUMN mcp.caja_mensual.lectura_id IS 'Lectura de la pestaña que ubicó la celda.';

-- Salaries keep no detail: cash_movement_sueldos_without_detail already forbids it.
CREATE VIEW mcp.movimientos_de_caja AS
SELECT m.month AS mes, m.bank AS banco, m.legal_entity AS entidad, m.historical AS historica,
       m.adjustment AS ajuste, m.currency AS moneda, m.amount AS monto, m.fx_rate AS tipo_cambio,
       m.amount_usd AS monto_usd, m.movement_type AS tipo_movimiento, m.rubro, m.agrupador,
       m.detalle, m.subdetalle, m.equipo,
       m.cell_ref AS celda, m.source_tab_id AS pestaña_id, m.snapshot_id AS lectura_id
FROM cash_movement m;

COMMENT ON VIEW mcp.movimientos_de_caja IS 'Movimientos bancarios de la pestaña Consolidado de «Base informe Craftech » (ADR-003), de los que sale mcp.caja_mensual. En los sueldos (rubro «01. Sueldos» o tipo de movimiento Sueldos) detalle, subdetalle y equipo son siempre nulos: pueden traer nombres de personas.';
COMMENT ON COLUMN mcp.movimientos_de_caja.mes IS 'Mes del movimiento ("Mes Corriente"), primer día del mes.';
COMMENT ON COLUMN mcp.movimientos_de_caja.banco IS 'Banco, tal como está en la planilla.';
COMMENT ON COLUMN mcp.movimientos_de_caja.entidad IS 'Sociedad dueña de la cuenta: Craftech S.A. (Galicia, Macro, Credicoop, Caja Córdoba) o Craftech-io Inc. (Mercury, Mesh); nula en cuentas históricas, ajustes y bancos desconocidos.';
COMMENT ON COLUMN mcp.movimientos_de_caja.historica IS 'Verdadero si la cuenta es histórica: VETA y cripto.';
COMMENT ON COLUMN mcp.movimientos_de_caja.ajuste IS 'Verdadero si viene de una pestaña de ajuste: banco CLIENTES o AFIP.';
COMMENT ON COLUMN mcp.movimientos_de_caja.moneda IS 'ARS, USD o USDC.';
COMMENT ON COLUMN mcp.movimientos_de_caja.monto IS 'Monto en su moneda, con su signo: negativo es una salida.';
COMMENT ON COLUMN mcp.movimientos_de_caja.tipo_cambio IS 'Tipo de cambio de la fila, tal como está en la planilla.';
COMMENT ON COLUMN mcp.movimientos_de_caja.monto_usd IS 'Monto en dólares, tal como está en la planilla.';
COMMENT ON COLUMN mcp.movimientos_de_caja.tipo_movimiento IS 'Egresos, Sueldos, Ingresos, Impuestos, Ingresos financieros, Dividendos o Interno (transferencia de Mercury a Mesh).';
COMMENT ON COLUMN mcp.movimientos_de_caja.rubro IS 'Rubro; config/cashflow_rows.yaml dice en qué fila del cashflow suma.';
COMMENT ON COLUMN mcp.movimientos_de_caja.agrupador IS 'Agrupador; en «01. Sueldos», CCSS son las cargas sociales.';
COMMENT ON COLUMN mcp.movimientos_de_caja.detalle IS 'Detalle; siempre nulo en los sueldos.';
COMMENT ON COLUMN mcp.movimientos_de_caja.subdetalle IS 'Subdetalle; siempre nulo en los sueldos.';
COMMENT ON COLUMN mcp.movimientos_de_caja.equipo IS 'Equipo; siempre nulo en los sueldos.';
COMMENT ON COLUMN mcp.movimientos_de_caja.celda IS 'Celda del monto en la pestaña Consolidado, en notación A1.';
COMMENT ON COLUMN mcp.movimientos_de_caja.pestaña_id IS 'Identificador de la pestaña (mcp.tabs.id).';
COMMENT ON COLUMN mcp.movimientos_de_caja.lectura_id IS 'Lectura de la que sale.';

CREATE VIEW mcp.indicadores_de_caja AS
SELECT indicator AS indicador, position AS orden, month AS mes, value AS valor, unit AS unidad,
       formula, proposed AS propuesto
FROM cashflow_indicator;

COMMENT ON VIEW mcp.indicadores_de_caja IS 'Indicadores de cabecera del cashflow, solo de Craftech Inc. en dólares: caja hoy, salida mensual, meses de cobertura y los dos cierres de marzo. Propuestos, a ratificar por Emi y Ro; cada uno trae su fórmula.';
COMMENT ON COLUMN mcp.indicadores_de_caja.indicador IS 'caja_hoy, salida_mensual, cobertura, cierre_marzo o cierre_marzo_con_pagos_proyectados.';
COMMENT ON COLUMN mcp.indicadores_de_caja.orden IS 'Orden en la cabecera, desde 1.';
COMMENT ON COLUMN mcp.indicadores_de_caja.mes IS 'Mes al que se refiere: el último mes real cerrado, o el próximo marzo para los cierres.';
COMMENT ON COLUMN mcp.indicadores_de_caja.valor IS 'Valor; nulo si falta algún dato para calcularlo.';
COMMENT ON COLUMN mcp.indicadores_de_caja.unidad IS 'usd o meses.';
COMMENT ON COLUMN mcp.indicadores_de_caja.formula IS 'Fórmula en palabras.';
COMMENT ON COLUMN mcp.indicadores_de_caja.propuesto IS 'Verdadero mientras Emi y Ro no ratifiquen la fórmula.';

GRANT SELECT ON mcp.caja_mensual, mcp.movimientos_de_caja, mcp.indicadores_de_caja TO mcp_reader;
