"""Mutant harness T-010 round 2: each mutation of the round-1 fixes must turn red the tests
added for them (attribution: only the five new tests run). Usage: python -I <this> <repo root>."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(sys.argv[1])
NEW = [
    "app/tests/test_interpret.py::test_a_repeated_month_column_is_a_problem_and_the_read_goes_on",
    "app/tests/test_interpret.py::test_a_row_whose_text_ends_like_a_series_suffix_is_its_own_row",
    "app/tests/test_interpret.py::test_an_error_in_a_grid_cell_is_unreadable",
    "app/tests/test_interpret.py::test_a_ventas_tab_without_schema_or_not_carga_is_not_touched",
    "app/tests/test_interpret.py::test_a_header_number_that_is_not_a_date_is_not_a_month",
]
M = [
    # F1: repeated month keeps only its first column
    ("app/craftech_os/interpret/cells.py", " and m not in months.values():", ":"),
    # F1: uniqueness by alias text and series order (back to row_key)
    ("app/migrations/0009_accruals_fx.sql", "UNIQUE (source_tab_id, block, alias_text, series_order, month)", "UNIQUE (source_tab_id, block, row_key, month)"),
    # F2: rate in a column without its own month is a problem, not silently dropped
    ("app/craftech_os/interpret/pagos_arg.py", "    for c in columns:\n        cell = row", "    for c in months:\n        cell = row"),
    # F3: interpreter's own unreadable branch in VENTAS and Pagos ARG
    ("app/craftech_os/interpret/ventas.py", "elif unreadable(cell) and i > 0:", "elif False:"),
    ("app/craftech_os/interpret/pagos_arg.py", "        elif unreadable(cell):", "        elif False:"),
    # F4: guard for tabs without schema / not CARGA
    ("app/craftech_os/interpret/__init__.py", 'tab_class != "CARGA" or not schema', "not schema"),
    ("app/craftech_os/interpret/__init__.py", 'tab_class != "CARGA" or not schema', 'tab_class != "CARGA"'),
    # F5: a header number is a month only when shown with a year
    ("app/craftech_os/interpret/cells.py", ' or "yy" not in (cell.get("format") or "").lower()', ""),
    ("app/craftech_os/interpret/cells.py", "return (EPOCH + timedelta(days=int(serial))).replace(day=1)", "return (EPOCH + timedelta(days=int(serial)))"),
]
survivors = 0
for f, old, new in M:
    p = ROOT / f
    if not p.exists():
        sys.exit(f"MISSING {p}")
    src = p.read_text()
    if src.count(old) != 1:
        sys.exit(f"PATTERN NOT UNIQUE/FOUND in {f}: {old!r}")
    p.write_text(src.replace(old, new))
    try:
        r = subprocess.run(["uv", "run", "pytest", "-q", "-x", *NEW], cwd=ROOT, capture_output=True, text=True)
    finally:
        p.write_text(src)
    killed = r.returncode != 0
    survivors += not killed
    print("KILLED  " if killed else "SURVIVED", f, "::", old.strip()[:70])
sys.exit(1 if survivors else 0)
