import hashlib
import re
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"
NAME_PATTERN = re.compile(r"^\d{4}_[a-z0-9_]+\.sql$")

BOOTSTRAP = """
CREATE TABLE IF NOT EXISTS schema_migration (
    name       text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now(),
    sha256     text NOT NULL
);
COMMENT ON TABLE schema_migration IS
    'Migración aplicada: cada archivo de app/migrations que ya corrió contra esta base.';
COMMENT ON COLUMN schema_migration.name IS 'Nombre del archivo de migración.';
COMMENT ON COLUMN schema_migration.applied_at IS 'Momento en que se aplicó la migración.';
COMMENT ON COLUMN schema_migration.sha256 IS
    'Hash SHA-256 del archivo al aplicarlo; si el archivo cambia después, migrate falla.';
"""


class MigrationError(Exception):
    pass


def migration_files(directory: Path) -> list[Path]:
    files = sorted(directory.glob("*.sql"))
    bad = [f.name for f in files if not NAME_PATTERN.match(f.name)]
    if bad:
        raise MigrationError(f"migration file names must look like NNNN_description.sql: {bad}")
    numbers = [f.name[:4] for f in files]
    duplicated = sorted({n for n in numbers if numbers.count(n) > 1})
    if duplicated:
        raise MigrationError(f"duplicated migration numbers: {duplicated}")
    return files


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def migrate(conn: psycopg.Connection, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply pending migrations in order, one transaction each. Returns the names applied."""
    files = migration_files(directory)
    conn.execute("SELECT pg_advisory_lock(hashtext('craftech_os.migrate'))")
    try:
        with conn.transaction():
            conn.execute(BOOTSTRAP)
        applied = dict(conn.execute("SELECT name, sha256 FROM schema_migration").fetchall())
        for f in files:
            if f.name in applied and applied[f.name] != sha256(f):
                raise MigrationError(f"migration {f.name} changed after it was applied")
        done = []
        for f in files:
            if f.name in applied:
                continue
            with conn.transaction():
                conn.execute(f.read_text())
                conn.execute(
                    "INSERT INTO schema_migration (name, sha256) VALUES (%s, %s)",
                    (f.name, sha256(f)),
                )
            done.append(f.name)
        return done
    finally:
        conn.execute("SELECT pg_advisory_unlock(hashtext('craftech_os.migrate'))")
