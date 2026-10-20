"""Mutant harness T-013 round 1: each mutation of vincular_alias, the facts glossary or the
server instructions must turn red the MCP tests (attribution: only app/tests/test_mcp.py runs).
Usage: python -I <this> <repo root>, with TEST_DATABASE_URL set. Exits non-zero if one survives
or if a listed file or pattern is missing."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(sys.argv[1])
NEW = ["app/tests/test_mcp.py"]
S = "app/craftech_os/mcp/server.py"
M = [
    ("problems not resolved", [(S, "            for problem in problems:\n", "            for problem in []:\n")]),
    ("text not normalized", [(S, "            normalize(texto),\n", "            texto,\n")]),
    ("source not validated", [(S, "        if not any(alias_source(f\"{t['planilla']} / {t['pestaña']}\") == source for t in tabs):", "        if False:")]),
    ("client created without crear_cliente", [(S, "        if created and not crear_cliente:", "        if False:")]),
    ("texto and cliente not required", [(S, "_required(fuente=fuente, texto=texto, cliente=cliente, autor=autor, motivo=motivo)", "_required(fuente=fuente, autor=autor, motivo=motivo)")]),
    ("estado filter only abierto", [(S, "AND estado IN ('abierto', 'reabierto') AND detalle", "AND estado IN ('abierto') AND detalle")]),
    ("estado filter dropped", [(S, " AND estado IN ('abierto', 'reabierto') AND detalle", " AND detalle")]),
    ("problem source filter dropped", [(S, "            if alias_source(f\"{p['planilla']} / {p['pestaña']}\") == source\n", "")]),
    ("facts glossary dropped", [(S, 'text.index("\\n## ", start)] + FACTS_GLOSSARY', 'text.index("\\n## ", start)]')]),
    ("instructions sentence dropped", [(S, ' cliente se corrige con vincular_alias."', ' cliente."')]),
    ("tool not registered", [(S, "    server.add_tool(\n        vincular_alias,\n", "    (lambda *a, **k: None)(\n        vincular_alias,\n")]),
    ("similar list empty", [(S, "if key in k or k in key or difflib.SequenceMatcher(None, key, k).ratio() >= 0.6", "if False")]),
    ("author not stored in resolution", [(S, "                    (problem, autor.strip(), motivo.strip()),", "                    (problem, 'x', motivo.strip()),")]),
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
