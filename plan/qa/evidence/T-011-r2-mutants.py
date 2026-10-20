"""Mutant harness T-011 round 2: each mutation of the interpreter, the migration or the diff must
turn red the tests added by T-011 (attribution: only app/tests/test_invoices.py runs).
Round 1 mutants updated to the fix round 1 code, plus one or more per fix.
Usage: python -I <this> <repo root>, with TEST_DATABASE_URL set. Exits non-zero if one survives
or if a listed file or pattern is missing."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(sys.argv[1])
NEW = ["app/tests/test_invoices.py"]
P = "app/craftech_os/interpret/pagos.py"
SQL = "app/migrations/0010_invoices.sql"
# (label, [(file, old, new), ...]): all replacements of a mutant are applied together.
M = [
    # --- round 1 mutants, updated ---
    ("R29 green is paid", [(P, '"#d9ead3": "pagada"', '"#d9ead3": "enviada"')]),
    ("R29 unknown color", [(P, "if bg not in STATES:\n                # color", "if False:\n                # color")]),
    ("R30 zero with color", [(P, "            if not amount:\n", "            if amount is None:\n")]),
    ("copy of another tab", [(P, 'if "!" in (cell.get("formula") or ""):', "if False:")]),
    ("R25 legal entity", [(P, '"Craftech S.A.", "total ingresos", False)', '"Craftech-io Inc.", "total ingresos", False)')]),
    ("R14 net", [(P, '"net_ars": (amount / IVA).quantize(Decimal("0.01")) if ars else None,', '"net_ars": amount if ars else None,')]),
    ("R10 only MEP firm", [(P, '"fx_rate_to_confirm": rate_type != "mep",', '"fx_rate_to_confirm": False,')]),
    ("R10 unknown row issue", [(P, '            issues.append(("cotizacion_tipo_a_confirmar", where, {"row": where}))', "            pass")]),
    ("R38 typed rate issue", [(P, '    issues.append(("cotizacion_tipeada", where, details))', "    pass")]),
    ("R38 typed rate value", [(P, '"fx_rate": numbers[1],', '"fx_rate": None,')]),
    ("inferred USD", [(P, '"inferred_usd": numbers[0] if numbers and len(numbers) == 1 else None,', '"inferred_usd": None,')]),
    ("R26 series", [(P, "        if n > 1\n", "        if n > 99\n")]),
    ("R31 color to confirm", [(P, '"color_to_confirm": True,', '"color_to_confirm": False,')]),
    ("R31 churn only SleakOps", [(P, 'return _interpret(doc, schema, "Craftech-io Inc.", "total pagos usa", sleakops)', 'return _interpret(doc, schema, "Craftech-io Inc.", "total pagos usa", True)')]),
    ("R4 last change", [(P, "            last[(color, block, key, ordinal, month)] = change_id", "            last.setdefault((color, block, key, ordinal, month), change_id)")]),
    ("R4 typed value counts (colors only)", [(P, "AND (c.change_type = 'color' OR (c.change_type = 'value'\n               AND NOT shows_amount(c.old_value) AND shows_amount(c.new_value)))", "AND c.change_type = 'color'")]),
    ("payment per paid invoice", [(P, '        if invoice["state"] == "pagada":', '        if invoice["state"] == "nunca":')]),
    ("parity total row", [(P, '            if (amount := number(total["cells"].get(c) or {})) is not None:', "            if False:")]),
    ("cobros editor origin", [(SQL, "CASE WHEN c.attributed_at IS NOT NULL THEN 'editor'", "CASE WHEN false THEN 'editor'")]),
    ("cobros date", [(SQL, "coalesce(c.attributed_at, c.window_end) AS fecha,\n       CASE", "c.window_end AS fecha,\n       CASE")]),
    ("history emptied", [(SQL, "CASE WHEN c.change_type = 'emptied'\n                 OR", "CASE WHEN false\n                 OR")]),
    ("parity difference", [(SQL, "round(coalesce(totals.amount, 0) - coalesce(sums.amount, 0), 2) AS diferencia", "0::numeric AS diferencia")]),
    ("diff keeps colors", [("app/craftech_os/diff/compare.py", "**colors, **row))", "**row))")]),
    # --- fix round 1 ---
    ("F1 invoice unique by row_key", [(SQL, "UNIQUE (source_tab_id, block, alias_text, series_order, month),\n    CHECK", "UNIQUE (source_tab_id, block, row_key, month),\n    CHECK")]),
    ("F1 payment unique without series", [(SQL, "UNIQUE (source_tab_id, block, row_key, series_order, month)", "UNIQUE (source_tab_id, block, row_key, month)")]),
    ("F1 link by suffixed key", [
        (P, "            last[(color, block, key, ordinal, month)] = change_id", '            last[(color, block, key if ordinal == 1 else f"{key} ({ordinal})", month)] = change_id'),
        (P, 'where = (invoice["block"], invoice["alias_text"], invoice["series_order"], invoice["month"])', 'where = (invoice["block"], invoice["row_key"], invoice["month"])'),
    ]),
    ("F1 cobros join without series", [(SQL, " AND f.serie = p.series_order\n", "\n")]),
    ("F2 shows_amount accepts 0", [(SQL, "shown ~ '[1-9]'", "shown ~ '[0-9]'")]),
    ("F2 shows_amount accepts text", [(SQL, "shown ~ '[1-9]' AND regexp_replace(shown, 'USD|ARS', '', 'g') !~ '[[:alpha:]]'", "shown ~ '[1-9]'")]),
    ("F2 history filter back to old_value IS NULL", [(SQL, "OR (c.change_type = 'value' AND shows_amount(c.old_value) <> shows_amount(c.new_value)))", "OR (c.change_type = 'value' AND c.old_value IS NULL))")]),
    ("F2 history new state", [(SQL, "\n                 OR (c.change_type = 'value' AND NOT shows_amount(c.new_value)) THEN", " THEN")]),
    ("F2 history old state", [(SQL, "CASE WHEN c.change_type = 'value' AND NOT shows_amount(c.old_value) THEN", "CASE WHEN c.change_type = 'value' THEN")]),
    ("F2 link typed value back to old_value IS NULL", [(P, "AND NOT shows_amount(c.old_value) AND shows_amount(c.new_value)))", "AND c.old_value IS NULL))")]),
    ("F3 references from factors only", [(P, 'references = REFERENCE.findall(cell.get("formula") or "")', 'references = [REFERENCE.fullmatch(f).groups() for f in re.sub(r"[=$()\\s]", "", cell.get("formula") or "").split("*") if REFERENCE.fullmatch(f)]')]),
    ("F3 old regex without $", [(P, r'REFERENCE = re.compile(r"\$?\b([A-Z]+)\$?(\d+)\b")', r'REFERENCE = re.compile(r"([A-Z]+)(\d+)")')]),
    ("F3 two references issue", [(P, '        issues.append(("cotizacion_tipo_a_confirmar", where, details))', "        pass")]),
    ("F3 inferred USD only for a plain product", [(P, "            numbers = None\n            break", "            continue")]),
    ("nit parity rounds to the cent", [(SQL, "round(coalesce(totals.amount, 0) - coalesce(sums.amount, 0), 2) AS diferencia", "coalesce(totals.amount, 0) - coalesce(sums.amount, 0) AS diferencia")]),
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
