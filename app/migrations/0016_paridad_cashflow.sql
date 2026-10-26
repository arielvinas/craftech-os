-- Parity of the monthly cashflow against the Resumen (ADR-003, T-020): every recalculada cell
-- next to the same row and month of the Resumen, in the unit of the row. Differences are shown,
-- never corrected. The tolerance (one unit of the row: a thousand pesos or a dollar) is
-- proposed, to be ratified by Emi and Ro. Granted to mcp_reader only.

CREATE VIEW mcp.paridad_cashflow AS
SELECT c.bloque, c.orden_bloque, c.fila, c.orden_fila, c.mes, c.periodo,
       c.valor AS valor_recalculado, s.value AS valor_resumen,
       -- Sheets adds in binary floating point: noise below a cent is not a difference.
       round(coalesce(s.value, 0) - c.valor, 2) AS diferencia,
       c.unidad, t.tolerancia,
       abs(round(coalesce(s.value, 0) - c.valor, 2)) > t.tolerancia AS fuera_de_tolerancia,
       c.planilla, c.pestaña, c.celda, c.pestaña_id, c.lectura_id
FROM mcp.caja_mensual c
JOIN cashflow_sheet_cell s
    ON s.source_tab_id = c.pestaña_id AND s.block = c.bloque AND s.label = c.fila
   AND s.month = c.mes
CROSS JOIN LATERAL (
    SELECT CASE c.unidad WHEN 'ars' THEN 1000 ELSE 1 END::numeric AS tolerancia
) t
WHERE c.origen = 'recalculada';

COMMENT ON VIEW mcp.paridad_cashflow IS 'Control del cashflow recalculado (ADR-003): cada celda de origen recalculada de mcp.caja_mensual contra la misma fila y mes de la pestaña «Resumen mensual Cash Flow ARG-USA», en la unidad de la fila. Las celdas sin_regla y parametro no se comparan (no tienen valor); su cantidad por mes está en mcp.cobertura_cashflow. Las diferencias se muestran, no se corrigen: delatan una regla de fila mal armada, un movimiento con otro mes que el que usa la planilla o una incoherencia de la propia planilla. La tolerancia es propuesta, a ratificar por Emi y Ro.';
COMMENT ON COLUMN mcp.paridad_cashflow.bloque IS 'Bloque del cashflow.';
COMMENT ON COLUMN mcp.paridad_cashflow.orden_bloque IS 'Orden del bloque, desde 0.';
COMMENT ON COLUMN mcp.paridad_cashflow.fila IS 'Fila, con el texto de la pestaña.';
COMMENT ON COLUMN mcp.paridad_cashflow.orden_fila IS 'Orden de la fila dentro del bloque, desde 0.';
COMMENT ON COLUMN mcp.paridad_cashflow.mes IS 'Mes (primer día del mes).';
COMMENT ON COLUMN mcp.paridad_cashflow.periodo IS 'real (mes cerrado) o en_curso (el mes de hoy, con los movimientos que hay: es esperable que no coincida).';
COMMENT ON COLUMN mcp.paridad_cashflow.valor_recalculado IS 'Valor calculado desde los movimientos (mcp.caja_mensual.valor).';
COMMENT ON COLUMN mcp.paridad_cashflow.valor_resumen IS 'Valor de la celda del Resumen, tal como está en la planilla; nulo si está vacía o no es un número. Solo para el control: nunca se muestra como valor del cashflow.';
COMMENT ON COLUMN mcp.paridad_cashflow.diferencia IS 'Valor del Resumen (vacío cuenta como 0) menos valor recalculado, en la unidad de la fila, redondeada al centavo; 0 si coinciden.';
COMMENT ON COLUMN mcp.paridad_cashflow.unidad IS 'ars (pesos) o usd (dólares), en la misma escala que la planilla.';
COMMENT ON COLUMN mcp.paridad_cashflow.tolerancia IS 'Tolerancia propuesta, no ratificada (pregunta abierta para Emi y Ro): una unidad de la fila, 1.000 pesos o 1 dólar.';
COMMENT ON COLUMN mcp.paridad_cashflow.fuera_de_tolerancia IS 'Verdadero si el valor absoluto de la diferencia supera la tolerancia propuesta.';
COMMENT ON COLUMN mcp.paridad_cashflow.planilla IS 'Planilla de la celda: CASH FLOW MENSUAL.';
COMMENT ON COLUMN mcp.paridad_cashflow.pestaña IS 'Pestaña de la celda.';
COMMENT ON COLUMN mcp.paridad_cashflow.celda IS 'Celda del Resumen en notación A1.';
COMMENT ON COLUMN mcp.paridad_cashflow.pestaña_id IS 'Identificador de la pestaña (mcp.tabs.id).';
COMMENT ON COLUMN mcp.paridad_cashflow.lectura_id IS 'Lectura de la pestaña de la que sale el valor del Resumen.';

CREATE VIEW mcp.cobertura_cashflow AS
SELECT mes, periodo,
       count(*) FILTER (WHERE origen = 'recalculada') AS recalculadas,
       count(*) FILTER (WHERE origen = 'sin_regla') AS sin_regla,
       count(*) FILTER (WHERE origen = 'parametro') AS parametro
FROM mcp.caja_mensual
GROUP BY mes, periodo;

COMMENT ON VIEW mcp.cobertura_cashflow IS 'Cuántas celdas del cashflow mensual (mcp.caja_mensual) hay de cada origen, por mes: las recalculada son las que compara mcp.paridad_cashflow; las sin_regla y parametro no tienen valor y no se comparan.';
COMMENT ON COLUMN mcp.cobertura_cashflow.mes IS 'Mes (primer día del mes).';
COMMENT ON COLUMN mcp.cobertura_cashflow.periodo IS 'real, en_curso o proyectado, como en mcp.caja_mensual.';
COMMENT ON COLUMN mcp.cobertura_cashflow.recalculadas IS 'Celdas calculadas desde los movimientos.';
COMMENT ON COLUMN mcp.cobertura_cashflow.sin_regla IS 'Celdas sin valor: fila sin regla ratificada o mes proyectado.';
COMMENT ON COLUMN mcp.cobertura_cashflow.parametro IS 'Celdas sin valor de las filas del parámetro de cerrar el mes con 4.000.000 de pesos, en meses proyectados.';

GRANT SELECT ON mcp.paridad_cashflow, mcp.cobertura_cashflow TO mcp_reader;
