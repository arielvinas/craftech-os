"""Mutant harness T-010: each mutation must turn tests/test_interpret.py (+test_clients) red."""
import subprocess, sys, pathlib
ROOT = pathlib.Path(sys.argv[1])
M = [
 ("app/craftech_os/ingest/importer.py", "                interpret.run(conn, snapshot_id)\n", ""),
 ("app/craftech_os/interpret/__init__.py", 'conn.execute(f"DELETE FROM {table} WHERE source_tab_id = %s", (tab_id,))', "pass"),
 ("app/craftech_os/interpret/pagos_arg.py", "stored, *controls = found_rows[::-1]", "stored, *controls = found_rows"),
 ("app/craftech_os/interpret/pagos_arg.py", "round(rate, 4) != round(stored[month][0], 4)", "False"),
 ("app/craftech_os/interpret/pagos_arg.py", '"type_to_confirm": rate_type == "oficial"', '"type_to_confirm": False'),
 ("app/craftech_os/interpret/pagos_arg.py", 'issues.append(("cotizacion_tipo_a_confirmar", rate_type, {"rate_type": rate_type}))', "pass"),
 ("app/craftech_os/interpret/ventas.py", "if n > 1", "if n > 99"),
 ("app/craftech_os/interpret/ventas.py", 'row_key = row["key"] if row["ordinal"] == 1 else f"{row[\'key\']} ({row[\'ordinal\']})"', 'row_key = row["key"]'),
 ("app/craftech_os/interpret/ventas.py", 'SKIPPED_BLOCKS = {"total ingresos"}', "SKIPPED_BLOCKS = set()"),
 ("app/craftech_os/interpret/ventas.py", "elif unreadable(cell) and i > 0:", "elif False:"),
 ("app/craftech_os/interpret/ventas.py", "if any(amounts.values()):", "if False:"),
 ("app/craftech_os/interpret/__init__.py", "unknown = {a[\"alias_text\"] for a in facts.get(\"accrual\", []) if a[\"amount_usd\"]} - known", "unknown = set()"),
 ("app/craftech_os/interpret/__init__.py", 'if interpret is None or tab_class != "CARGA" or not schema:', "if interpret is None:"),
 ("app/craftech_os/clients.py", 'normalize(row["fuente"]),', 'row["fuente"],'),
 ("app/craftech_os/interpret/cells.py", "return (EPOCH + timedelta(days=int(serial))).replace(day=1)", "return (EPOCH + timedelta(days=int(serial)))"),
 ("app/craftech_os/interpret/__init__.py", "            duration_ms=duration_ms,\n            snapshot_id", "            snapshot_id"),
]
survivors = 0
for f, old, new in M:
    p = ROOT / f
    if not p.exists(): sys.exit(f"MISSING {p}")
    src = p.read_text()
    if src.count(old) != 1: sys.exit(f"PATTERN NOT UNIQUE/FOUND in {f}: {old!r}")
    p.write_text(src.replace(old, new))
    try:
        r = subprocess.run(["uv", "run", "pytest", "-q", "-x", "app/tests/test_interpret.py", "app/tests/test_clients.py"], cwd=ROOT, capture_output=True, text=True)
    finally:
        p.write_text(src)
    killed = r.returncode != 0
    survivors += not killed
    print(("KILLED  " if killed else "SURVIVED"), f, "::", old.strip()[:70])
sys.exit(1 if survivors else 0)
