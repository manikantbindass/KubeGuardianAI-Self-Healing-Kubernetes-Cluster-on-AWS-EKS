from collections.abc import Generator
from typing import cast
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from kubesentinel_api.database import Base, get_db, get_redis
from kubesentinel_api.main import app
from redis import Redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db() -> Generator[Session]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
        connection.execute(text("INSERT INTO alembic_version VALUES ('0003_anomaly_evidence')"))
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


@pytest.fixture
def cache() -> Redis:
    mock = Mock(spec=Redis)
    mock.ping.return_value = True
    mock.get.return_value = None
    return cast(Redis, mock)


@pytest.fixture
def client(db: Session, cache: Redis) -> Generator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_redis] = lambda: cache
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()
