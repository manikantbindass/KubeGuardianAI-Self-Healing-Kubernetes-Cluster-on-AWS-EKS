"""Destructive migration round-trip on an explicitly named disposable test database."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


@pytest.mark.postgres
def test_postgres_migration_round_trip() -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip(
            "TEST_DATABASE_URL is not set; real PostgreSQL migration test requires Docker/DB"
        )
    database = make_url(database_url).database
    assert database and database.endswith("_test"), "Only a disposable *_test database is allowed"
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "DATABASE_URL": database_url}

    def migrate(target: str, revision: str) -> None:
        subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "apps/api/alembic.ini", target, revision],
            cwd=root,
            env=env,
            check=True,
            timeout=60,
        )

    engine = create_engine(database_url)
    try:
        migrate("upgrade", "head")
        assert "greeting_jobs" in inspect(engine).get_table_names()
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "0002_incidents"
            )
        migrate("downgrade", "base")
        assert "greeting_jobs" not in inspect(engine).get_table_names()
        assert "incidents" not in inspect(engine).get_table_names()
        migrate("upgrade", "head")
        migrate("upgrade", "head")  # Restart must be harmless.
    finally:
        engine.dispose()
