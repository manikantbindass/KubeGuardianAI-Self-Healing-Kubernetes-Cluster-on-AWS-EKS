import json
import urllib.request
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from kubesentinel_api.config import get_settings
from kubesentinel_api.models import AnomalyEvidence, Incident
from kubesentinel_detector.main import ScoreRequest, Settings, deliver, predict
from kubesentinel_ml.schema import Metrics, Observation
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def test_real_contract_scoring_to_durable_incident_and_replay(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Contract fixture only: no claim this is collected real telemetry.
    monkeypatch.setattr(get_settings(), "telemetry_token", SecretStr("test-token"))
    row = Observation(
        id="fixture",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        dataset_id="contract-test",
        provenance="real",
        origin="prometheus",
        resource="namespace/kubesentinel",
        metrics=Metrics(cpu_ratio=0.99),
    )
    result = predict(ScoreRequest(observations=[row]), None, 60)
    scored = result.windows[0]
    anomaly = {
        "namespace": scored.namespace,
        "resource": scored.resource,
        "window_start": scored.start.isoformat(),
        "window_end": scored.end.isoformat(),
        "provenance": "real",
        "detector": "rules",
        "model_version": "rules-v1",
        "score": scored.score.score,
        "threshold": scored.score.threshold,
        "severity": scored.score.severity,
        "explanations": [e.model_dump() for e in scored.score.explanations],
    }
    headers = {"Authorization": "Bearer test-token"}
    assert (
        client.post("/api/v1/internal/anomalies", json={"anomalies": [anomaly]}).status_code == 401
    )
    for _ in range(2):
        response = client.post(
            "/api/v1/internal/anomalies", json={"anomalies": [anomaly]}, headers=headers
        )
        assert response.status_code == 200
    assert db.scalar(select(func.count()).select_from(Incident)) == 1
    assert db.scalar(select(func.count()).select_from(AnomalyEvidence)) == 1
    incident_id = response.json()["incident_ids"][0]
    evidence = client.get(f"/api/v1/incidents/{incident_id}/anomaly").json()
    assert evidence["score_kind"] == "uncalibrated_anomaly_score"
    assert evidence["explanations"][0]["feature"] == "cpu_ratio"

    def send_to_backend(request: urllib.request.Request, timeout: int) -> MagicMock:
        assert timeout == 3
        assert isinstance(request.data, bytes)
        sent = client.post(
            "/api/v1/internal/anomalies",
            json=json.loads(request.data),
            headers={"Authorization": request.get_header("Authorization") or ""},
        )
        assert sent.status_code == 200
        response = MagicMock(status_code=200)
        response.status = 200
        response.__enter__.return_value = response
        return response

    monkeypatch.setattr(urllib.request, "urlopen", send_to_backend)
    assert deliver(result, Settings(telemetry_token=SecretStr("test-token"))) == "accepted"
    assert db.scalar(select(func.count()).select_from(Incident)) == 1
    anomaly["provenance"] = "synthetic"
    assert (
        client.post(
            "/api/v1/internal/anomalies", json={"anomalies": [anomaly]}, headers=headers
        ).status_code
        == 422
    )


def test_unavailable_incident_api_preserves_score() -> None:
    row = Observation(
        id="contract",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        dataset_id="fixture",
        provenance="real",
        origin="prometheus",
        resource="test",
        metrics=Metrics(cpu_ratio=0.99),
    )
    score = predict(ScoreRequest(observations=[row]), None, 60)
    assert deliver(score, Settings(incident_api="http://127.0.0.1:1")) == "unavailable"
    assert score.windows[0].score.anomalous
