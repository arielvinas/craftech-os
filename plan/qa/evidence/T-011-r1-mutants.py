"""Mutant harness T-011 round 1: each mutation of the interpreter, the migration or the diff must
turn red the tests added by T-011 (attribution: only app/tests/test_invoices.py runs).
Usage: python -I <this> <repo root>, with TEST_DATABASE_URL set. Exits non-zero if one survives."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(sys.argv[1])
NEW = ["app/tests/test_invoices.py"]
P = "app/craftech_os/interpret/pagos.py"
SQL = "app/migrations/0010_invoices.sql"
M = [
    # Rule R29: green is paid
    (P, '"#d9ead3": "pagada"', '"#d9ead3": "enviada"'),
    # Rule R29: an unknown color gives no invoice
    (P, "if bg not in STATES:\n                # color", "if False:\n                # color"),
    # Rule R30: a 0 with color is no invoice
    (P, "            if not amount:\n", "            if amount is None:\n"),
    # A copy of another tab is not an invoice
    (P, 'if "!" in (cell.get("formula") or ""):', "if False:"),
    # Rule R25: legal entity
    (P, '"Craftech S.A.", "total ingresos", False)', '"Craftech-io Inc.", "total ingresos", False)'),
    # Rule R14: net = gross / 1.21
    (P, '"net_ars": (amount / IVA).quantize(Decimal("0.01")) if ars else None,', '"net_ars": amount if ars else None,'),
    # Rule R10: only MEP is a firm rate
    (P, '"fx_rate_to_confirm": rate_type != "mep",', '"fx_rate_to_confirm": False,'),
    # Rule R10: an unknown referenced row opens cotizacion_tipo_a_confirmar
    (P, '            issues.append(("cotizacion_tipo_a_confirmar", where, {"row": where}))', "            pass"),
    # Rule R38: typed rate
    (P, '    issues.append(("cotizacion_tipeada", where, details))', "    pass"),
    (P, '"fx_rate": numbers[1],', '"fx_rate": None,'),
    # Inferred USD
    (P, '"inferred_usd": numbers[0] if len(numbers) == 1 else None,', '"inferred_usd": None,'),
    # Rule R26: repeated series
    (P, "        if n > 1\n", "        if n > 99\n"),
    # Rule R31: churn only in SleakOps, color to confirm
    (P, '"color_to_confirm": True,', '"color_to_confirm": False,'),
    (P, 'return _interpret(doc, schema, "Craftech-io Inc.", "total pagos usa", sleakops)', 'return _interpret(doc, schema, "Craftech-io Inc.", "total pagos usa", True)'),
    # Rule R4: last change, not the first
    (P, "            last[(color, block, row_key, month)] = change_id", "            last.setdefault((color, block, row_key, month), change_id)"),
    # Rule R4: a value typed into an empty cell counts as a repaint
    (P, "AND (c.change_type = 'color' OR (c.change_type = 'value' AND c.old_value IS NULL))", "AND c.change_type = 'color'"),
    # Payment exists per paid invoice
    (P, '        if invoice["state"] == "pagada":', '        if invoice["state"] == "nunca":'),
    # Parity: total row
    (P, '            if (amount := number(total["cells"].get(c) or {})) is not None:', "            if False:"),
    # Views: date origin comes from cell_change at query time
    (SQL, "CASE WHEN c.attributed_at IS NOT NULL THEN 'editor'", "CASE WHEN false THEN 'editor'"),
    (SQL, "coalesce(c.attributed_at, c.window_end) AS fecha,\n       CASE", "c.window_end AS fecha,\n       CASE"),
    # History view: emptied cell
    (SQL, "CASE WHEN c.change_type = 'emptied' THEN 'sin factura' ELSE invoice_state(c.new_color) END", "invoice_state(c.new_color)"),
    # Parity view: difference
    (SQL, "round(coalesce(totals.amount, 0) - coalesce(sums.amount, 0), 2) AS diferencia", "0::numeric AS diferencia"),
    # Diff: a value change keeps the colors
    ("app/craftech_os/diff/compare.py", "**colors, **row))", "**row))"),
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
