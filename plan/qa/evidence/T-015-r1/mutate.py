"""Mutation harness for T-015: each mutant must turn the listed tests red. Exits 1 if one survives."""
import pathlib, subprocess, sys
ROOT = pathlib.Path(sys.argv[1])
F, P, M, I = "app/craftech_os/interpret/fundings.py", "app/craftech_os/interpret/pagos.py", "app/migrations/0012_cei_aws_parity.sql", "app/craftech_os/interpret/__init__.py"
MUTANTS = [
    ("copies skipped on CEI row", F, 'if not cei and ("!" in formula', 'if ("!" in formula'),
    ("cut applies to CEI", F, "if not cei and c in months and months[c] > LAST_PAGOS_MONTH", "if c in months and months[c] > LAST_PAGOS_MONTH"),
    ("no CEI end", F, "if cei and c in months and months[c] > CEI_LAST_MONTH", "if False"),
    ("CEI end off by one (>=)", F, "months[c] > CEI_LAST_MONTH", "months[c] >= CEI_LAST_MONTH"),
    ("opener CEI still a problem", F, "(row is rows[0] and not cei)", "(row is rows[0])"),
    ("any program on General opener is CEI", F, 'cei = cei and normalize(program or "") == "cei"', "pass"),
    ("any block opener with CEI", F, 'cei = row is rows[0] and block.split(" (")[0] == "General"', "cei = row is rows[0]"),
    ("CEI asks for an alias", I, 'if not f.get("program_row")', "if True"),
    ("funding_total from payment row", P, '("funding_total", schema.get("funding_total"))', '("funding_total", total_key)'),
    ("funding_total not normalized", P, "key = normalize(key)", "pass"),
    ("missing total row silent", P, 'issues.append(("fila_sin_interpretar", f"falta:{key}", {"row": key}))', "pass"),
    ("tracker only by payment date", M, "date_trunc('month', coalesce(f.fecha_pago, f.cobro_estimado))", "date_trunc('month', f.fecha_pago)"),
    ("tracker from any date", M, "AND coalesce(f.fecha_pago, f.cobro_estimado) >= DATE '2026-03-01'", ""),
    ("units swapped", M, "THEN 'sleakops' ELSE 'craftech'", "THEN 'craftech' ELSE 'sleakops'"),
    ("no tracker in parity", M, "WHERE f.origen = 'tracker'", "WHERE false"),
    ("no rounding", M, "round(coalesce(totals.amount, 0) - coalesce(sums.amount, 0), 2)", "coalesce(totals.amount, 0) - coalesce(sums.amount, 0) + 0.001"),
    ("migration resolves CEI-after-end too", M, "AND NOT v.details ? 'reason'", ""),
    ("migration resolves nothing", M, "INSERT INTO issue_resolution (issue_id, action, author, reason)\nSELECT", "INSERT INTO issue_resolution (issue_id, action, author, reason)\nSELECT * FROM (SELECT"),
]
survived = []
TESTS = ["uv", "run", "--no-sync", "pytest", "-q", "-x", "app/tests/test_fundings.py", "app/tests/test_mcp.py", "app/tests/test_invoices.py"]
base = subprocess.run(TESTS, cwd=ROOT, capture_output=True, text=True)
if base.returncode != 0 or " passed" not in base.stdout:
    sys.exit("baseline not green: " + base.stdout[-500:])
print("baseline:", base.stdout.strip().splitlines()[-1])
for name, path, old, new in MUTANTS:
    f = ROOT / path
    if not f.exists():
        sys.exit(f"missing file {f}")
    src = f.read_text()
    if src.count(old) != 1:
        sys.exit(f"{name}: pattern found {src.count(old)} times in {path}")
    if name == "migration resolves nothing":
        new_src = src.replace("AND NOT v.details ? 'reason';", "AND NOT v.details ? 'reason') q WHERE false;").replace(old, new)
    else:
        new_src = src.replace(old, new)
    f.write_text(new_src)
    try:
        r = subprocess.run(TESTS, cwd=ROOT, capture_output=True, text=True)
    finally:
        f.write_text(src)
    killed = r.returncode == 1 and "FAILED" in r.stdout
    line = [l for l in r.stdout.splitlines() if l.startswith("FAILED")][:1]
    print(("KILLED  " if killed else "SURVIVED"), name, line[0][:110] if line else "")
    if not killed:
        survived.append(name)
sys.exit(1 if survived else 0)
