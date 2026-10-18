import pytest

from craftech_os.migrate import MIGRATIONS_DIR, MigrationError, migration_files


def test_files_are_sorted_by_number(tmp_path):
    for name in ["0010_later.sql", "0002_second.sql", "0001_first.sql"]:
        (tmp_path / name).write_text("SELECT 1;")
    assert [f.name for f in migration_files(tmp_path)] == [
        "0001_first.sql",
        "0002_second.sql",
        "0010_later.sql",
    ]


@pytest.mark.parametrize("names", [["1_bad.sql"], ["0001_Upper.sql"], ["0001-dash.sql"]])
def test_bad_names_are_rejected(tmp_path, names):
    for name in names:
        (tmp_path / name).write_text("SELECT 1;")
    with pytest.raises(MigrationError, match="NNNN_description"):
        migration_files(tmp_path)


def test_duplicated_numbers_are_rejected(tmp_path):
    for name in ["0001_a.sql", "0001_b.sql"]:
        (tmp_path / name).write_text("SELECT 1;")
    with pytest.raises(MigrationError, match="0001"):
        migration_files(tmp_path)


def test_repo_migrations_start_with_sources():
    assert migration_files(MIGRATIONS_DIR)[0].name == "0001_sources.sql"
