"""Bank movements of the Consolidado tab of "Base informe Craftech " (ADR-003): one per row.

The tab gathers the tab of each bank and the adjustment tabs, so only it is read. Its 17
headers must be the ones of the schema, in order: other headers leave the last movements as
they are. The schema maps each bank to its legal entity (ratified rule of accounts), to
"historical" or to "adjustment". Rubro "01. Sueldos" keeps no Detalle, Subdetalle or Equipo:
they can hold names of people. Problems carry banks, rubros, row numbers and cell references,
never amounts or details.
"""

from pathlib import Path

import yaml

from craftech_os.diff.compare import a1, blocks, normalize, value
from craftech_os.interpret.cells import month, number, unreadable

# Roles of the 17 columns, in the order of the tab.
COLUMNS = (
    "month",
    "origin",
    "bank",
    "tipo_erogacion",
    "frecuencia",
    "movement_type",
    "rubro",
    "agrupador",
    "equipo",
    "currency",
    "amount",
    "fx_rate",
    "amount_usd",
    "detalle",
    "subdetalle",
    "area",
    "tipo_gasto",
)
NUMBERS = ("amount", "fx_rate", "amount_usd")
CURRENCIES = ("ARS", "USD", "USDC")
MOVEMENT_TYPES = (
    "Egresos",
    "Sueldos",
    "Ingresos",
    "Impuestos",
    "Ingresos financieros",
    "Dividendos",
)
SUELDOS = "01. Sueldos"
PRIVATE = ("detalle", "subdetalle", "equipo")
# The transfer from Mercury to Mesh: the expense is recorded again in Mesh, so it is internal.
MESH_TRANSFER = ("MERCURY", "CAJA. Mesh", "MESH")
ROWS_FILE = Path(__file__).resolve().parents[3] / "config" / "cashflow_rows.yaml"


def _texts(node, what: str) -> list[str]:
    """The texts of a list, a list inside it flattened (YAML has no splat)."""
    out = []
    for item in node or []:
        for text in item if isinstance(item, list) else [item]:
            if not isinstance(text, str):
                raise ValueError(f"{what}: {text!r} is not a label")
            out.append(text)
    return out


def rules(path: Path = ROWS_FILE) -> list[dict]:
    """[{block, label, rubros, agrupadores, banks}] of the cashflow rows; empty lists: no rule."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    out = []
    for block in data["blocks"]:
        for row in block["rows"]:
            what = f"{block['name']} / {row['label']}"
            out.append(
                {
                    "block": block["name"],
                    "label": row["label"],
                    **{k: _texts(row.get(k), what) for k in ("rubros", "agrupadores", "banks")},
                }
            )
    return out


def _text(cell: dict | None) -> str | None:
    return (value(cell) or "").strip() or None


def interpret(doc: dict, schema: dict, title: str) -> tuple[dict | None, list]:
    """({"cash_movement": [fact]}, [(issue_type, key, details)]); None facts: other headers."""
    where = {"planilla": title, "pestaña": "Consolidado"}
    expected = [schema["columns"][role] for role in COLUMNS]
    split = blocks(doc, schema)
    found = []
    if split is not None:
        header_r, tab_blocks = split
        header = next(row for _, rows in tab_blocks for row in rows if row["r"] == header_r)
        found = [_text(header["cells"].get(c)) for c in range(max(header["cells"]) + 1)]
        while found and found[-1] is None:
            found.pop()
    if [normalize(t or "") for t in found] != [normalize(t) for t in expected]:
        details = {**where, "esperadas": len(expected), "encontradas": sum(map(bool, found))}
        return None, [("cash_header_mismatch", "encabezados", details)]
    at = {role: c for c, role in enumerate(COLUMNS)}
    banks = {normalize(bank): kind for bank, kind in schema["banks"].items()}
    known = {normalize(r) for rule in rules() for r in rule["rubros"]}
    movements, issues, unknown_banks, unmapped = [], [], {}, {}
    for row in (row for _, rows in tab_blocks for row in rows if row["r"] > header_r):
        if not any(_text(cell) for cell in row["cells"].values()):
            continue
        name = f"fila {row['r'] + 1}"

        def cell(role, row=row):
            return row["cells"].get(at[role])

        def ref(role, row=row):
            return a1(row["r"], at[role])

        when = month(cell("month"))
        if when is None:
            issues.append(("fila_sin_interpretar", name, {"cell_ref": ref("month")}))
            continue
        fact = {role: _text(cell(role)) for role in ("bank", "rubro", "agrupador", *PRIVATE)}
        if normalize(fact["rubro"] or "") == normalize(SUELDOS):
            fact.update(dict.fromkeys(PRIVATE))
        for role in NUMBERS:
            fact[role] = number(cell(role) or {})
            if fact[role] is None and unreadable(cell(role) or {}):
                key = f"{name}:{schema['columns'][role]}"
                issues.append(("valor_ilegible", key, {"cell_ref": ref(role)}))
        currency, movement_type = _text(cell("currency")), _text(cell("movement_type"))
        if currency not in CURRENCIES:
            key = f"{name}:{schema['columns']['currency']}"
            issues.append(("fila_sin_interpretar", key, {"cell_ref": ref("currency")}))
            currency = None
        if (fact["bank"], fact["rubro"], fact["agrupador"]) == MESH_TRANSFER:
            movement_type = "Interno"
        elif movement_type not in MOVEMENT_TYPES:
            key = f"{name}:{schema['columns']['movement_type']}"
            issues.append(("fila_sin_interpretar", key, {"cell_ref": ref("movement_type")}))
            movement_type = None
        kind = banks.get(normalize(fact["bank"] or ""))
        if kind is None:
            unknown_banks.setdefault(fact["bank"] or "[vacio]", []).append(ref("bank"))
        if movement_type != "Interno" and normalize(fact["rubro"] or "") not in known:
            unmapped.setdefault(fact["rubro"] or "[vacio]", []).append(
                (fact["agrupador"], ref("rubro"))
            )
        movements.append(
            {
                **fact,
                "row_key": name,
                "cell_ref": ref("amount"),
                "month": when,
                "legal_entity": kind if kind not in (None, "historical", "adjustment") else None,
                "historical": kind == "historical",
                "adjustment": kind == "adjustment",
                "currency": currency,
                "movement_type": movement_type,
            }
        )
    for bank, refs in unknown_banks.items():
        details = {**where, "banco": bank, "filas": len(refs), "cell_ref": refs[0]}
        issues.append(("cash_unknown_bank", bank, details))
    for rubro, seen in unmapped.items():
        agrupador, first = seen[0]
        details = {**where, "rubro": rubro, "agrupador": agrupador, "filas": len(seen)}
        issues.append(("cash_unmapped_rubro", rubro, {**details, "cell_ref": first}))
    return {"cash_movement": movements}, issues
