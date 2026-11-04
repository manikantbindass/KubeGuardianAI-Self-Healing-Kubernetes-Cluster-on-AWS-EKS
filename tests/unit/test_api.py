import json
import logging
from typing import cast
from unittest.mock import Mock

from fastapi.testclient import TestClient
from kubesentinel_api.database import get_db
from kubesentinel_api.main import app
from kubesentinel_api.observability import JsonFormatter
from kubesentinel_api.worker import process_one
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import text
from sqlalchemy.orm import Session


def test_health_and_version(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Correlation-ID": "test-123"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "kubesentinel-api", "version": "0.1.0"}
    assert response.headers["X-Correlation-ID"] == "test-123"
    assert response.headers["Cache-Control"] == "no-store"
    assert client.get("/api/v1/version").json()["api_version"] == "v1"


def test_readiness(client: TestClient, db: Session, cache: Redis) -> None:
    assert client.get("/api/v1/ready").json()["status"] == "ready"
    cast(Mock, cache.ping).side_effect = RedisConnectionError("secret redis host")
    response = client.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json()["dependencies"]["redis"] == "unavailable"
    assert "secret" not in response.text
    assert client.get("/api/v1/health").status_code == 200
    cast(Mock, cache.ping).side_effect = None
    db.execute(text("DROP TABLE greeting_jobs"))
    response = client.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json()["dependencies"]["postgresql"] == "unavailable"


def test_greeting_is_durable_and_processed(client: TestClient, db: Session, cache: Redis) -> None:
    assert client.get("/api/v1/jobs").json() == []
    cast(Mock, cache.lpush).side_effect = RedisConnectionError("offline")
    response = client.post("/api/v1/jobs", json={"name": "Ada"})
    assert response.status_code == 202
    job = response.json()
    assert job["status"] == "queued"
    assert process_one(db) is True
    assert process_one(db) is False
    result = client.get(f"/api/v1/jobs/{job['id']}").json()
    assert result["status"] == "completed"
    assert result["message"] == "Hello, Ada! KubeSentinel AI is connected."
    cast(Mock, cache.setex).assert_called_once()
    cast(Mock, cache.get).return_value = json.dumps(result)
    assert client.get(f"/api/v1/jobs/{job['id']}").json() == result
    assert len(client.get("/api/v1/jobs").json()) == 1


def test_validation_and_not_found(client: TestClient) -> None:
    for name in ["", "   ", "a" * 81]:
        response = client.post("/api/v1/jobs", json={"name": name})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
    assert client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000").status_code == 404
    assert client.get("/api/v1/jobs/invalid").status_code == 422
    assert client.get("/missing").json()["error"]["code"] == "request_error"


def test_database_errors_are_sanitized(client: TestClient, db: Session) -> None:
    db.execute(text("DROP TABLE greeting_jobs"))
    response = client.get("/api/v1/jobs")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
    assert "SELECT" not in response.text


def test_unhandled_errors_are_sanitized(client: TestClient) -> None:
    def broken() -> None:
        raise RuntimeError("internal secret")

    app.dependency_overrides[get_db] = broken
    response = client.get("/api/v1/jobs")
    assert response.status_code == 500
    assert "secret" not in response.text
    assert response.headers["X-Correlation-ID"] == response.json()["correlation_id"]


def test_cors_and_openapi(client: TestClient) -> None:
    allowed = client.options(
        "/api/v1/jobs",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    assert allowed.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
    denied = client.options(
        "/api/v1/jobs",
        headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST"},
    )
    assert "Access-Control-Allow-Origin" not in denied.headers
    schema = client.get("/openapi.json").json()
    assert "/api/v1/health" in schema["paths"]
    assert schema["components"]["schemas"]["GreetingInput"]["properties"]["name"]["maxLength"] == 80


def test_json_logging() -> None:
    record = logging.LogRecord("test", logging.INFO, "", 0, "request", (), None)
    record.correlation_id = "correlation-1"
    output = json.loads(JsonFormatter().format(record))
    assert output["correlation_id"] == "correlation-1"
    assert output["level"] == "INFO"
