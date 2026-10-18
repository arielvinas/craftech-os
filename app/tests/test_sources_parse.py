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
            "default_class": None,
            "tabs": [(" Pagos USA Sleakops(2023)", "HISTORICA")],
        }
    ]


def test_all_tabs_entry():
    parsed = parse("sources:\n  - {title: P&L - DATA, all_tabs: DERIVADA}\n")
    assert parsed == [{"title": "P&L - DATA", "default_class": "DERIVADA", "tabs": []}]


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
    ],
)
def test_invalid_files_are_rejected(text, message):
    with pytest.raises(SourcesError, match=message):
        parse(text)
