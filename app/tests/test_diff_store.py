"""Changes and problems stored with each import, against the test database. Invented data only."""

import pytest
from test_import import MARKER, FakeGoogle, _events, _tab

from craftech_os import cli, sources
from craftech_os.migrate import migrate

SOURCES = """
sources:
  - title: "Cobranzas Ficticias"
    drive_id: "file-a"
    tabs:
      CARGA: ["Cobros"]
    schemas:
      "Cobros":
        header: "Cliente"
        key: A
        blocks: ["General", "Total Ingresos"]
        grid: "B:D"
  - title: "P&L Ficticio"
    drive_id: "file-p"
    all_tabs: DERIVADA
"""
SCHEMA = {"header": "Cliente", "key": "A", "blocks": ["General", "Total Ingresos"], "grid": "B:D"}
BASE = [
    ["Título ficticio"],
    ["Cliente", "ene", "feb", "mar"],
    ["General"],
    ["Cliente A", "100", "200", "300"],
    ["Cliente B", "10", "20", "30"],
    ["Total Ingresos", "110", "220", "330"],
]
ORANGE = "#ff9900"  # FC ENVIADA in rule R29
SALMON = "#ea9999"  # seen in a real tab, not in rule R29


def _rgb(hex_color):
    return {
        k: int(hex_color[i : i + 2], 16) / 255
        for k, i in zip(("red", "green", "blue"), (1, 3, 5), strict=True)
    }


def _value(text, bg=None):
    """A Sheets API cell: numbers as numbers, anything else as text; None paints an empty cell."""
    if text is None:
        return {"effectiveFormat": {"backgroundColor": _rgb(bg)}}
    try:
        effective = {"numberValue": float(text)}
    except ValueError:
        effective = {"stringValue": text}
    cell = {"effectiveValue": effective, "formattedValue": text}
    if bg:
        cell["effectiveFormat"] = {"backgroundColor": _rgb(bg)}
    return cell


def _grid(sheet_id, title, rows):
    """rows: lists of texts or (text, color); None leaves the cell empty."""
    tab = _tab(sheet_id, title, "")
    tab["merges"] = []
    tab["data"] = [
        {
            "rowData": [
                {
                    "values": [
                        {} if x is None else _value(*x) if isinstance(x, tuple) else _value(x)
                        for x in row
                    ]
                }
                for row in rows
            ]
        }
    ]
    return tab


@pytest.fixture
def fake(monkeypatch):
    from craftech_os.ingest.google import Google

    fake = FakeGoogle()
    fake.files_by_id["file-a"]["tabs"] = [_grid(11, "Cobros", BASE)]
    monkeypatch.setattr(Google, "from_environment", classmethod(lambda cls: fake.google()))
    return fake


@pytest.fixture
def env(db, monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", db.info.dsn + " password=" + (db.info.password or ""))
    migrate(db)
    path = tmp_path / "sources.yaml"
    path.write_text(SOURCES, encoding="utf-8")
    return path


def _import(path):
    return cli.main(["import", "--file", str(path)])


def _set(fake, rows, sheet_id=11, title="Cobros"):
    fake.files_by_id["file-a"]["tabs"] = [_grid(sheet_id, title, rows)]


def _changes(db, tab="Cobros"):
    return db.execute(
        """
        SELECT c.change_type, c.block, c.row_key, c.cell_ref, c.old_value, c.new_value
        FROM cell_change c JOIN source_tab t ON t.id = c.source_tab_id
        WHERE t.name = %s ORDER BY c.id
        """,
        (tab,),
    ).fetchall()


def _issues(db, issue_type):
    return db.execute(
        "SELECT stable_key, details, status FROM v_issue WHERE issue_type = %s ORDER BY id",
        (issue_type,),
    ).fetchall()


def _tab_id(db, name="Cobros"):
    return db.execute("SELECT id FROM source_tab WHERE name = %s", (name,)).fetchone()[0]


def test_sources_load_stores_the_schema_of_each_listed_tab(db, env):
    assert cli.main(["sources", "load", "--file", str(env)]) == 0
    assert db.execute("SELECT schema FROM source_tab WHERE name = 'Cobros'").fetchone() == (SCHEMA,)
    env.write_text(SOURCES.replace('grid: "B:D"', 'grid: "B:E"'), encoding="utf-8")
    assert cli.main(["sources", "load", "--file", str(env)]) == 0
    assert db.execute("SELECT schema->>'grid' FROM source_tab").fetchone() == ("B:E",)


@pytest.mark.parametrize(
    "schema, error",
    [
        ('{header: "Cliente"}', "needs 'header' and 'key'"),
        ('{header: "Cliente", key: "1"}', "key must be a column"),
        ('{header: "Cliente", key: A, grid: "D:B"}', "grid a range"),
        ('{header: "Cliente", key: A, grid: "D"}', "grid a range"),
        ('{header: "Cliente", key: A, blocks: "General"}', "list of texts"),
        ('{header: "", key: A}', "header"),
        ('{header: "Cliente", key: A, rows: 3}', "unknown schema keys"),
    ],
)
def test_a_bad_schema_is_rejected(schema, error):
    text = SOURCES.split("    schemas:")[0] + f'    schemas:\n      "Cobros": {schema}\n'
    with pytest.raises(sources.SourcesError, match=error):
        sources.parse(text)


def test_a_schema_needs_a_listed_tab():
    with pytest.raises(sources.SourcesError, match="not listed"):
        sources.parse(SOURCES.replace('"Cobros":\n', '"Pagos":\n'))
    with pytest.raises(sources.SourcesError, match="all_tabs"):
        sources.parse(
            SOURCES.replace('    tabs:\n      CARGA: ["Cobros"]\n', "    all_tabs: CARGA\n")
        )


def test_a_row_inserted_above_a_block_is_stored_as_one_row_inserted(db, env, fake):
    assert _import(env) == 0
    assert _changes(db) == []
    _set(fake, BASE[:3] + [["Cliente C", "1", "2", "3"]] + BASE[3:])
    assert _import(env) == 0
    assert _changes(db) == [("row_inserted", "General", "cliente c", None, None, "4")]
    row = db.execute(
        """
        SELECT c.detected_at = s.read_at, c.window_start IS NOT NULL, c.window_end IS NOT NULL,
               c.attributed_editor_ids IS NULL AND c.attribution_certainty IS NULL
        FROM cell_change c JOIN snapshot s ON s.id = c.to_snapshot
        """
    ).fetchone()
    assert row == (True, True, True, True)
    diffed = [d for _, _, d in _events(db, "tab_diffed") if d["from_snapshot"]]
    assert [d["changes"] for d in diffed] == [{"row_inserted": 1}]


def test_color_value_and_emptied_changes_are_stored(db, env, fake):
    assert _import(env) == 0
    rows = [list(r) for r in BASE]
    rows[3][1] = ("100", ORANGE)
    rows[3][2] = "201"
    rows[4][3] = None
    _set(fake, rows)
    assert _import(env) == 0
    stored = db.execute(
        "SELECT change_type, cell_ref, old_value, new_value, old_color, new_color"
        " FROM cell_change WHERE cell_ref IS NOT NULL ORDER BY cell_ref"
    ).fetchall()
    assert stored == [
        ("color", "B4", None, None, None, ORANGE),
        ("value", "C4", "200", "201", None, None),
        ("emptied", "D5", "30", None, None, None),
    ]


def test_an_unknown_color_is_one_problem_however_many_cells(db, env, fake):
    clients = [
        [f"Cliente {n}", (str(n), SALMON), (str(n), SALMON), (str(n), SALMON)] for n in range(17)
    ]
    _set(fake, BASE[:3] + clients + BASE[3:])
    assert _import(env) == 0
    ((key, details, status),) = _issues(db, "color_desconocido")
    assert (key, details["cells"], len(details["sample"]), status) == (
        f"{_tab_id(db)}:{SALMON}",
        51,
        5,
        "abierto",
    )
    first = db.execute("SELECT last_seen_at FROM issue").fetchone()[0]
    _set(fake, BASE[:3] + clients + [["Cliente Z", (("1", SALMON))]] + BASE[3:])
    assert _import(env) == 0
    assert len(_issues(db, "color_desconocido")) == 1
    assert db.execute("SELECT last_seen_at > %s FROM issue", (first,)).fetchone() == (True,)
    assert _issues(db, "color_desconocido")[0][1]["cells"] == 52


def test_a_painted_empty_cell_is_kept_only_in_a_carga_tab_with_schema(db, env, fake):
    rows = [list(r) for r in BASE]
    rows[4][3] = (None, SALMON)
    rows[4].append((None, "#ffffff"))
    _set(fake, rows)
    fake.files_by_id["file-p"]["tabs"] = [_grid(21, "Resumen", rows)]
    assert _import(env) == 0
    painted = db.execute(
        "SELECT t.name, cell FROM snapshot s JOIN source_tab t ON t.id = s.source_tab_id,"
        " jsonb_array_elements(s.content->'rows') r, jsonb_array_elements(r->'cells') cell"
        " WHERE NOT cell ? 'value'"
    ).fetchall()
    assert painted == [("Cobros", {"c": 3, "bg": SALMON})]
    ((key, details, _),) = _issues(db, "color_desconocido")
    assert (key, details["sample"]) == (f"{_tab_id(db)}:{SALMON}", ["D5"])
    # Painting a whole empty row is not a row inserted.
    _set(fake, rows + [[(None, ORANGE), (None, ORANGE)]])
    assert _import(env) == 0
    assert [c for c in _changes(db) if c[0] != "tab_added"] == []


def test_text_in_the_month_grid_is_an_unreadable_value(db, env, fake):
    rows = [list(r) for r in BASE]
    rows[3][2] = "814,8"
    _set(fake, rows)
    assert _import(env) == 0
    assert _issues(db, "valor_ilegible") == [
        (f"{_tab_id(db)}:General:cliente a:feb", {"cell_ref": "C4"}, "abierto")
    ]


def test_unreadable_values_of_two_rows_with_the_same_key_are_two_problems(db, env, fake):
    rows = [list(r) for r in BASE[:5] + [["Cliente A", "1", "2", "3"]] + BASE[5:]]
    rows[3][2] = "814,8"
    rows[5][2] = "n/d"
    _set(fake, rows)
    assert _import(env) == 0
    assert sorted(key for key, _, _ in _issues(db, "valor_ilegible")) == [
        f"{_tab_id(db)}:General:cliente a (2):feb",
        f"{_tab_id(db)}:General:cliente a:feb",
    ]


def test_unreadable_values_with_the_same_key_in_two_blocks_are_two_problems(db, env, fake):
    rows = [list(r) for r in BASE] + [["Cliente A", "1", "n/d", "3"]]
    rows[3][2] = "814,8"
    _set(fake, rows)
    assert _import(env) == 0
    assert sorted(key for key, _, _ in _issues(db, "valor_ilegible")) == [
        f"{_tab_id(db)}:General:cliente a:feb",
        f"{_tab_id(db)}:Total Ingresos:cliente a:feb",
    ]


def test_a_third_repeated_key_is_an_ambiguous_alignment(db, env, fake):
    two = BASE[:5] + [["Cliente A", "1", "2", "3"]] + BASE[5:]
    _set(fake, two)
    assert _import(env) == 0
    _set(fake, two[:6] + [["Cliente A", "4", "5", "6"]] + two[6:])
    assert _import(env) == 0
    ((key, details, _),) = _issues(db, "alineacion_ambigua")
    assert key == f"{_tab_id(db)}:General:cliente a"
    assert details["block"] == "General"


def test_issue_status_follows_its_last_resolution(db, env, fake):
    rows = [list(r) for r in BASE]
    rows[3][1] = ("100", SALMON)
    _set(fake, rows)
    assert _import(env) == 0
    (issue_id,) = db.execute("SELECT id FROM issue").fetchone()

    def reread_with(text):
        rows[4][1] = text
        _set(fake, rows)
        assert _import(env) == 0
        return _issues(db, "color_desconocido")[0][2]

    db.execute(
        "INSERT INTO issue_resolution (issue_id, action, author, reason)"
        " VALUES (%s, 'ignorado', 'test', 'test')",
        (issue_id,),
    )
    assert reread_with("11") == "ignorado"
    db.execute(
        "INSERT INTO issue_resolution (issue_id, action, author, reason)"
        " VALUES (%s, 'resuelto', 'test', 'test')",
        (issue_id,),
    )
    assert _issues(db, "color_desconocido")[0][2] == "resuelto"
    assert reread_with("12") == "reabierto"


def test_a_tab_renamed_in_google_is_tab_renamed_and_keeps_its_row(db, env, fake):
    assert _import(env) == 0
    tab_id = _tab_id(db)
    _set(fake, BASE, title="Cobros 2026")
    assert _import(env) == 0
    assert db.execute(
        "SELECT change_type, old_value, new_value FROM cell_change WHERE source_tab_id = %s",
        (tab_id,),
    ).fetchall() == [("tab_renamed", "Cobros", "Cobros 2026")]
    assert db.execute(
        "SELECT name, active FROM source_tab WHERE id = %s", (tab_id,)
    ).fetchone() == (
        "Cobros 2026",
        True,
    )
    # The title is part of the snapshot: a second one, with no cell changes, after the first.
    assert db.execute(
        "SELECT count(*) FROM snapshot WHERE source_tab_id = %s", (tab_id,)
    ).fetchone() == (2,)


def test_tabs_added_and_deleted_in_google(db, env, fake):
    assert _import(env) == 0
    fake.files_by_id["file-a"]["tabs"].append(_grid(12, "Nueva", BASE))
    assert _import(env) == 0
    assert _changes(db, "Nueva") == [("tab_added", None, None, None, None, "Nueva")]
    assert [k for k, _, _ in _issues(db, "pestana_sin_clasificar")] == [
        f"{db.execute('SELECT id FROM source WHERE drive_id = %s', ('file-a',)).fetchone()[0]}:12"
    ]
    fake.files_by_id["file-a"]["tabs"].pop()
    assert _import(env) == 0
    assert _changes(db, "Nueva")[-1][0] == "tab_deleted"
    assert db.execute("SELECT active FROM source_tab WHERE name = 'Nueva'").fetchone() == (False,)


def test_a_tab_without_schema_is_compared_by_position(db, env, fake):
    fake.files_by_id["file-p"]["tabs"] = [_grid(21, "Resumen", BASE)]
    assert _import(env) == 0
    rows = [list(r) for r in BASE]
    rows[4][2] = "21"
    fake.files_by_id["file-p"]["tabs"] = [_grid(21, "Resumen", rows)]
    assert _import(env) == 0
    assert _changes(db, "Resumen") == [
        ("tab_added", None, None, None, None, "Resumen"),
        ("value", None, None, "C5", "20", "21"),
    ]


def test_cli_diff_prints_counts_and_writes_nothing(db, env, fake, capsys):
    assert _import(env) == 0
    _set(fake, BASE[:3] + [["Cliente C", "1"]] + BASE[3:])
    assert _import(env) == 0
    changes = db.execute("SELECT count(*) FROM cell_change").fetchone()
    capsys.readouterr()
    assert cli.main(["diff", "--tab", "Cobranzas Ficticias", "Cobros"]) == 0
    out = capsys.readouterr().out
    assert "  row_inserted 1\n" in out and "1 changes, ambiguous 0" in out
    first, last = db.execute("SELECT min(id), max(id) FROM snapshot").fetchone()
    assert cli.main(["diff", "--tab", "Cobranzas Ficticias", "Cobros", "--to", str(first)]) == 1
    assert "fewer than two snapshots" in capsys.readouterr().err
    other = db.execute(
        "SELECT max(s.id) FROM snapshot s JOIN source_tab t ON t.id = s.source_tab_id"
        " WHERE t.name = 'Resumen'"
    ).fetchone()[0]
    args = ["--from", str(other), "--to", str(last)]
    assert cli.main(["diff", "--tab", "Cobranzas Ficticias", "Cobros", *args]) == 1
    assert "are not both of" in capsys.readouterr().err
    assert cli.main(["diff", "--tab", "Cobranzas Ficticias", "Otra"]) == 1
    assert db.execute("SELECT count(*) FROM cell_change").fetchone() == changes


def test_no_event_issue_or_output_contains_cell_values(db, env, fake, capsys):
    rows = [list(r) for r in BASE]
    rows[4][0] = MARKER
    rows[4][2] = MARKER
    _set(fake, rows)
    assert _import(env) == 0
    rows[4][1] = (MARKER, SALMON)
    _set(fake, rows)
    assert _import(env) == 0
    assert cli.main(["diff", "--tab", "Cobranzas Ficticias", "Cobros"]) == 0
    captured = capsys.readouterr()
    assert MARKER not in captured.out + captured.err
    assert db.execute(
        "SELECT count(*) FROM system_event WHERE details::text ILIKE %s", (f"%{MARKER}%",)
    ).fetchone() == (0,)
    # The problem key names the row, as the ticket asks; details carry cells, never amounts.
    assert db.execute(
        "SELECT count(*) FROM issue WHERE details::text ILIKE %s", (f"%{MARKER}%",)
    ).fetchone() == (0,)
    assert db.execute("SELECT count(*) FROM cell_change").fetchone()[0] > 0
