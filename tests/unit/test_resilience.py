import pytest
from chaos_lab import main
from fastapi.testclient import TestClient
from kubesentinel_api.main import settings
from kubesentinel_api.worker import process_one
from pytest import MonkeyPatch
from sqlalchemy.orm import Session


def test_backpressure_releases_after_processing(
    client: TestClient, db: Session, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "queue_max_pending", 1)
    assert client.post("/api/v1/jobs", json={"name": "first"}).status_code == 202
    response = client.post("/api/v1/jobs", json={"name": "second"})
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "2"
    assert process_one(db)
    assert client.post("/api/v1/jobs", json={"name": "third"}).status_code == 202


def test_chaos_requires_explicit_authorization(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["chaos_lab.py", "terminate-pod", "--target", "fixture"])
    with pytest.raises(SystemExit, match="authorization"):
        main()
