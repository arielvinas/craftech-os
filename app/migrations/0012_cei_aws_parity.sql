-- T-015: the CEI row of "General" in Pagos as funding milestones, and the parity of the
-- "TOTAL PAGOS AWS" row against the interpreted fundings.

CREATE TABLE funding_total (
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

COMMENT ON TABLE funding_total IS 'Total por mes que calcula la planilla para los fundings de AWS: la fila "TOTAL PAGOS AWS" de Pagos (en las planillas reales está arriba del encabezado). Es contra lo que se controla la interpretación en mcp.paridad_fundings_aws. Se reemplaza entero en cada lectura nueva de la pestaña.';
COMMENT ON COLUMN funding_total.id IS 'Identificador interno; cambia en cada reinterpretación.';
COMMENT ON COLUMN funding_total.source_tab_id IS 'Pestaña de la que sale.';
COMMENT ON COLUMN funding_total.row_key IS 'Texto de la fila del total, normalizado.';
COMMENT ON COLUMN funding_total.month IS 'Mes, el primer día del mes.';
COMMENT ON COLUMN funding_total.amount IS 'Total tal como está en la celda, en dólares.';
COMMENT ON COLUMN funding_total.snapshot_id IS 'Lectura de la que sale.';
COMMENT ON COLUMN funding_total.cell_ref IS 'Celda del total en notación A1.';
COMMENT ON COLUMN funding_total.rules_version IS 'Versión de las reglas con las que se interpretó.';

COMMENT ON TABLE funding_milestone IS 'Hito de funding de AWS (regla R28): una celda con monto de un bloque de funding de Pagos en un mes hasta febrero de 2026, o de la fila CEI del bloque "General" de Pagos en un mes hasta septiembre de 2026 (origen pagos; lo de CEI es declaración de Ariel del 20-oct-2026, pendiente de ratificar por Emi y Ro), o una fila del tracker FUNDINGS con monto cargada desde el 25/2/2026 o todavía sin fecha de carga (origen tracker). Un funding en los dos lados se guarda dos veces y abre funding_duplicado. No es una factura (regla R15). Se reemplaza entero en cada lectura nueva de la pestaña.';
COMMENT ON COLUMN funding_milestone.origin IS 'pagos (bloque de funding de Pagos, hasta febrero de 2026; la fila CEI de "General", hasta septiembre de 2026) o tracker (pestaña FUNDINGS, cargado desde el 25/2/2026).';
COMMENT ON VIEW mcp.fundings IS 'Hitos de funding de AWS de la última lectura (regla R28): los de los bloques de funding de Pagos en meses hasta febrero de 2026 y los de la fila CEI del bloque "General" de Pagos hasta septiembre de 2026 (origen pagos; programa CEI), y los del tracker FUNDINGS cargados desde el 25/2/2026 o todavía sin cargar (origen tracker). CEI es un programa de AWS que Craftech recibe sin cliente: no tiene alias ni cliente. Lo de CEI es declaración de Ariel del 20-oct-2026, pendiente de ratificar por Emi y Ro. Un funding que está en los dos lados aparece dos veces y tiene un problema funding_duplicado. No son facturas: no se suman con mcp.facturas (regla R15). El cliente sale del alias vigente; nulo si el texto no tiene alias.';
COMMENT ON COLUMN mcp.fundings.origen IS 'pagos (bloque de funding de Pagos, hasta febrero de 2026; la fila CEI de "General", hasta septiembre de 2026) o tracker (pestaña FUNDINGS, desde el 25/2/2026).';

-- The tracker has no sheet of its own to check against: its milestones go to the Pagos
-- tab of their business unit, the one whose sheet title names SleakOps or the other.
CREATE VIEW mcp.paridad_fundings_aws AS
WITH totals AS (
    SELECT p.source_tab_id, p.month, p.amount FROM funding_total p
    JOIN (
        SELECT DISTINCT ON (source_tab_id) id
        FROM snapshot
        ORDER BY source_tab_id, read_at DESC, id DESC
    ) n ON n.id = p.snapshot_id
), units AS (
    SELECT DISTINCT t.source_tab_id,
           CASE WHEN lower(s.title) LIKE '%sleakops%' THEN 'sleakops' ELSE 'craftech' END AS unit
    FROM totals t
    JOIN source_tab st ON st.id = t.source_tab_id
    JOIN source s ON s.id = st.source_id
), milestones AS (
    SELECT pestaña_id AS source_tab_id, mes AS month, monto_usd AS amount
    FROM mcp.fundings WHERE origen = 'pagos'
    UNION ALL
    SELECT u.source_tab_id, date_trunc('month', coalesce(f.fecha_pago, f.cobro_estimado))::date,
           f.monto_usd
    FROM mcp.fundings f
    JOIN units u ON u.unit = lower(f.unidad_negocio)
    WHERE f.origen = 'tracker'
      AND coalesce(f.fecha_pago, f.cobro_estimado) >= DATE '2026-03-01'
), sums AS (
    SELECT source_tab_id, month, sum(amount) AS amount FROM milestones GROUP BY 1, 2
)
SELECT s.title AS planilla, t.name AS pestaña, t.id AS pestaña_id, month AS mes,
       totals.amount AS total_planilla, coalesce(sums.amount, 0) AS suma_fundings,
       -- Sheets adds in binary floating point: noise below a cent is not a difference.
       round(coalesce(totals.amount, 0) - coalesce(sums.amount, 0), 2) AS diferencia
FROM totals FULL JOIN sums USING (source_tab_id, month)
JOIN source_tab t ON t.id = source_tab_id AND t.active
JOIN source s ON s.id = t.source_id;

COMMENT ON VIEW mcp.paridad_fundings_aws IS 'Control de la interpretación de los fundings de AWS: por planilla y mes, la fila "TOTAL PAGOS AWS" de Pagos contra la suma de los hitos interpretados. Hasta febrero de 2026 suma los hitos de Pagos; desde marzo de 2026, los de la fila CEI de "General" (hasta septiembre de 2026) más los del tracker FUNDINGS de la unidad comercial de la planilla, por mes de pago o, si no tiene, por mes de cobro estimado. Los hitos del tracker sin ninguna de las dos fechas no se suman. Declaración de Ariel del 20-oct-2026, pendiente de ratificar por Emi y Ro. Una diferencia distinta de 0 delata un hito mal leído, un hito con otra fecha que la que usa la planilla o celdas que el total suma y no son fundings.';
COMMENT ON COLUMN mcp.paridad_fundings_aws.planilla IS 'Nombre de la planilla de Google Sheets.';
COMMENT ON COLUMN mcp.paridad_fundings_aws.pestaña IS 'Nombre de la pestaña: Pagos.';
COMMENT ON COLUMN mcp.paridad_fundings_aws.pestaña_id IS 'Identificador de la pestaña (mcp.tabs.id).';
COMMENT ON COLUMN mcp.paridad_fundings_aws.mes IS 'Mes (primer día del mes).';
COMMENT ON COLUMN mcp.paridad_fundings_aws.total_planilla IS 'Total de "TOTAL PAGOS AWS" para ese mes; nulo si la fila no tiene número en ese mes.';
COMMENT ON COLUMN mcp.paridad_fundings_aws.suma_fundings IS 'Suma de los montos de los hitos de funding interpretados de ese mes.';
COMMENT ON COLUMN mcp.paridad_fundings_aws.diferencia IS 'Total de la planilla menos suma de fundings, redondeada al centavo; 0 si la interpretación cierra.';

GRANT SELECT ON mcp.paridad_fundings_aws TO mcp_reader;

-- The CEI row was the opener of "General" and every cell with an amount opened a
-- fila_sin_interpretar. It is now a milestone: those problems are resolved, not ignored.
-- A cell after September 2026 opens a new problem, with a reason, which is left open.
INSERT INTO issue_resolution (issue_id, action, author, reason)
SELECT v.id, 'resuelto', 'T-015 (decisión de Ariel del 20-oct-2026)',
       'La fila CEI del bloque "General" de Pagos ahora es un hito de funding hasta septiembre de 2026 (declaración de Ariel del 20-oct-2026, pendiente de ratificar por Emi y Ro).'
FROM v_issue v
JOIN source_tab t ON t.id = v.source_tab_id AND t.name = 'Pagos'
WHERE v.issue_type = 'fila_sin_interpretar' AND v.status IN ('abierto', 'reabierto')
  AND v.stable_key LIKE '%:General:general:%' AND NOT v.details ? 'reason';
