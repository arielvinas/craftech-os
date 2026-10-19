# Improvements

- [ ] [error-handling] sources.yaml que no está en UTF-8 sale con traceback en vez de 'error: …' (misma clase que F3 de la ronda 1: candidata a guía) — QA T-001 r2
- [ ] [data] Planilla all_tabs que sale de sources.yaml y vuelve queda con sus pestañas inactivas hasta que T-002 las relea (caso: 'P&L GEN AI - DATA', en la papelera de Drive) — QA T-001 r2
- [ ] [test] Falta un test para la guarda '_test' de la fixture de base de prueba — QA T-001 r2
- [ ] [ux] 'sources load' con 'sources: []' desactiva todas las pestañas sin aviso — QA T-001 r2
- [ ] [data] Google recalcula fórmulas con ruido de punto flotante (hasta 4e-8, mismo texto formateado, misma versión de Drive): 4 pestañas de 'CASH FLOW MENSUAL' cambian de hash entre dos lecturas seguidas; T-004 debe comparar sin marcar esas celdas como cambios (y T-003 no relee si la versión no cambió) — T-002 implement
- [ ] [data] El rol craftech_app puede hacer DELETE, UPDATE y TRUNCATE sobre snapshot; la capa cruda debería ser solo de inserción — QA T-002 r1 y r2 (split-out)
- [ ] [seguridad] El dump diario pasa la contraseña de Postgres como argumento de pg_dump (visible con ps en el contenedor); usar PGPASSWORD — QA T-003 r1 (F1)
- [ ] [backups] Un archivo ajeno con el patrón craftech-os-*.dump en la carpeta de backups ocupa uno de los 14 lugares y hace borrar un dump real — QA T-003 r1 (F2)
