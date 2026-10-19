import os

import psycopg
import pytest


@pytest.fixture
def db():
    """Empty public schema in the test database, for integration tests."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set: skipping integration tests (see README.md)")
    with psycopg.connect(url, autocommit=True) as conn:
        if not conn.info.dbname.endswith("_test"):
            pytest.fail(
                f"TEST_DATABASE_URL points at {conn.info.dbname!r}; its name must end in _test"
                " because every test drops the public schema"
            )
        conn.execute("DROP SCHEMA IF EXISTS mcp CASCADE")
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        # As in a fresh database, so the MCP role tests meet the table privileges.
        conn.execute("GRANT USAGE ON SCHEMA public TO PUBLIC")
        yield conn
