"""Mutant harness T-012 round 1: each mutation of the funding interpreter, the migration, the
sources schema or the registry must turn red the tests added by T-012 (attribution: only
app/tests/test_fundings.py runs).
Usage: python -I <this> <repo root>, with TEST_DATABASE_URL set. Exits non-zero if one survives
or if a listed file or pattern is missing."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(sys.argv[1])
NEW = ["app/tests/test_fundings.py"]
F = "app/craftech_os/interpret/fundings.py"
I = "app/craftech_os/interpret/__init__.py"
PG = "app/craftech_os/interpret/pagos.py"
S = "app/craftech_os/sources.py"
SQL = "app/migrations/0011_fundings.sql"
# (label, [(file, old, new), ...]): all replacements of a mutant are applied together.
M = [
    ("R28 Pagos month cut", [(F, "                if months[c] > LAST_PAGOS_MONTH:\n                    continue\n", "")]),
    ("R28 tracker load cut", [(F, "        if load_date is not None and load_date < CUT:\n            continue\n", "")]),
    ("R28 cut date moved", [(F, "CUT = date(2026, 2, 25)", "CUT = date(2026, 2, 1)")]),
    ("R22 sign-off + 30", [(F, "COLLECTION_DAYS = 30", "COLLECTION_DAYS = 0")]),
    ("copied amounts are milestones", [(F, 'if "!" in formula or "IMPORTRANGE" in formula:', "if False:")]),
    ("invoice loaded always", [(F, '"invoice_loaded": normalize(_text(cell("invoice_loaded")) or "") == "si",', '"invoice_loaded": True,')]),
    ("tracker missing column issue", [(F, "    if missing:\n", "    if False:\n")]),
    ("tracker unreadable amount", [(F, "        if amount is None and unreadable(amount_cell):", "        if False:")]),
    ("funding block names ignored", [(F, '        if block.split(" (")[0] not in funding_blocks:', "        if block.split(\" (\")[0] == 'Total Ingresos':")]),
    ("program order shared", [(F, '                order[(row["key"], normalize(program or ""))] += 1\n                milestones.append(', '                order[row["key"]] += 1\n                milestones.append(')]),
    ("duplicate without amount", [(I, "        AND k.amount_usd = p.amount_usd\n", "\n")]),
    ("duplicate without client alias", [(I, "        AND (k.alias_text = p.alias_text OR k.client_id = p.client_id)", "        AND k.alias_text = p.alias_text")]),
    ("duplicate not reported", [(I, '            detect.upsert(conn, "funding_duplicado", key, k_source, k_tab, details)', "            pass")]),
    ("registry FUNDINGS", [(I, '    "FUNDINGS": fundings.interpret,\n', "")]),
    ("Pagos milestones dropped", [(PG, '        "funding_milestone": milestones,', '        "funding_milestone": [],')]),
    ("funding_blocks not validated", [(S, '    if not set(value.get("funding_blocks", [])) <= set(blocks):', "    if False:")]),
    ("columns required not validated", [(S, "        missing = sorted(set(fundings.REQUIRED) - set(columns))", "        missing = []")]),
    ("parity difference", [(SQL, "round(coalesce(totals.amount, 0) - coalesce(sums.amount, 0), 2) AS diferencia", "0::numeric AS diferencia")]),
]
survivors = []
for label, edits in M:
    originals = {}
    for f, old, _ in edits:
        p = ROOT / f
        if not p.exists():
            sys.exit(f"MISSING {p}")
        originals.setdefault(p, p.read_text())
    try:
        for f, old, new in edits:
            p = ROOT / f
            src = p.read_text()
            if src.count(old) != 1:
                sys.exit(f"PATTERN NOT UNIQUE/FOUND in {f} ({label}): {old!r}")
            p.write_text(src.replace(old, new))
        r = subprocess.run(["uv", "run", "pytest", "-q", "-x", *NEW], cwd=ROOT, capture_output=True, text=True)
    finally:
        for p, src in originals.items():
            p.write_text(src)
    killed = r.returncode != 0
    if not killed:
        survivors.append(label)
    print("KILLED  " if killed else "SURVIVED", "::", label)
print(f"{len(M) - len(survivors)}/{len(M)} killed; survivors: {survivors}")
sys.exit(1 if survivors else 0)
