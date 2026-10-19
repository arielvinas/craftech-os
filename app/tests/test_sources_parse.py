import pytest

from craftech_os import sources
from craftech_os.sources import SourcesError, parse


def test_real_config_has_the_twenty_annex_spreadsheets():
    parsed = parse(sources.SOURCES_FILE.read_text(encoding="utf-8"))
    tabs = [(s["title"], name, cls) for s in parsed for name, cls in s["tabs"]]
    assert len(parsed) == 20
    assert len(tabs) == 244
    assert sum(cls == "A_CONFIRMAR" for _, _, cls in tabs) == 12
    all_tabs = {s["title"] for s in parsed if s["default_class"]}
    assert len(all_tabs) == 9
    assert "Facturación - Craftech Total" in {s["title"] for s in parsed}


def test_names_keep_their_spaces():
    parsed = parse(
        'sources:\n  - title: "Base informe Craftech "\n'
        '    tabs: {HISTORICA: [" Pagos USA Sleakops(2023)"]}\n'
    )
    assert parsed == [
        {
            "title": "Base informe Craftech ",
            "drive_id": None,
            "default_class": None,
            "tabs": [(" Pagos USA Sleakops(2023)", "HISTORICA")],
        }
    ]


def test_all_tabs_entry():
    parsed = parse("sources:\n  - {title: P&L - DATA, all_tabs: DERIVADA}\n")
    assert parsed == [
        {"title": "P&L - DATA", "drive_id": None, "default_class": "DERIVADA", "tabs": []}
    ]


@pytest.mark.parametrize(
    "text, message",
    [
        ("{}", "top-level key"),
        ("sources: {}", "top-level key"),
        ("sources: [x]", "must be a mapping"),
        ("sources: [{title: A, all_tabs: CARGA, extra: 1}]", "unknown keys"),
        ("sources: [{all_tabs: CARGA}]", "title must be a non-empty string"),
        ("sources: [{title: '  ', all_tabs: CARGA}]", "title must be a non-empty string"),
        ("sources: [{title: A}]", "exactly one of"),
        ("sources: [{title: A, all_tabs: CARGA, tabs: {CARGA: [x]}}]", "exactly one of"),
        ("sources: [{title: A, all_tabs: Carga}]", "unknown class 'Carga'"),
        ("sources: [{title: A, tabs: {CALCULADA: [x]}}]", "unknown class 'CALCULADA'"),
        ("sources: [{title: A, tabs: {}}]", "'tabs' must map"),
        ("sources: [{title: A, tabs: {CARGA: []}}]", "non-empty list"),
        ("sources: [{title: A, tabs: {CARGA: [1]}}]", "tab must be a non-empty string"),
        ("sources: [{title: A, tabs: {CARGA: [x], IGNORAR: [x]}}]", "duplicated tab 'x'"),
        ("sources: [{title: A, all_tabs: CARGA}, {title: A, all_tabs: CARGA}]", "duplicated"),
        ("sources: [{title: A, tabs: {CARGA: [x], CARGA: [y]}}]", "duplicated key 'CARGA'"),
        ("sources: [{title: A, title: B, all_tabs: CARGA}]", "duplicated key 'title'"),
        ("sources: [{title: A, drive_id: 'a/b', all_tabs: CARGA}]", "Google Drive file id"),
        ("sources: [{title: A, drive_id: 12, all_tabs: CARGA}]", "Google Drive file id"),
        (
            "sources: [{title: A, drive_id: x, all_tabs: CARGA},"
            " {title: B, drive_id: x, all_tabs: CARGA}]",
            "duplicated drive_id",
        ),
    ],
)
def test_invalid_files_are_rejected(text, message):
    with pytest.raises(SourcesError, match=message):
        parse(text)


def test_with_drive_ids_adds_only_the_id_lines():
    text = (
        "# comment\nsources:\n"
        '  - title: "Base informe Craftech "\n    tabs: {HISTORICA: [x]}\n'
        "  - title: Other\n    all_tabs: DERIVADA\n"
    )
    written = sources.with_drive_ids(text, {"Base informe Craftech ": "1aB_-z"})
    assert written.replace('    drive_id: "1aB_-z"\n', "") == text
    assert [s["drive_id"] for s in parse(written)] == ["1aB_-z", None]


def test_with_drive_ids_rejects_an_invalid_id_or_an_unknown_title():
    text = "sources:\n  - title: A\n    all_tabs: DERIVADA\n"
    with pytest.raises(SourcesError, match="invalid file id"):
        sources.with_drive_ids(text, {"A": 'x"\n  evil: 1'})
    with pytest.raises(SourcesError, match="could not write drive_id for \\['B'\\]"):
        sources.with_drive_ids(text, {"B": "x"})
