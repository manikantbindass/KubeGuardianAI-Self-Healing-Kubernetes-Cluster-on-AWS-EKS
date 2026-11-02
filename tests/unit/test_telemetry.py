from datetime import UTC, datetime
from typing import cast
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from kubesentinel_api.config import get_settings
from kubesentinel_api.event_collector import normalize
from kubesentinel_api.main import app
from kubesentinel_api.models import Incident
from kubesentinel_api.telemetry import MetricsUnavailable, PrometheusClient, get_metrics
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session


@pytest.fixture(autouse=True)
def token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "telemetry_token", SecretStr("test-token"))


def event() -> dict[str, object]:
    return {
        "uid": "event-uid",
        "resource_version": "1",
        "namespace": "kubesentinel",
        "resource": "fault-pod",
        "reason": "BackOff",
        "message": "Container is restarting",
        "type": "Warning",
        "count": 1,
        "observed_at": "2026-11-02T10:00:00Z",
    }


def test_authentication_and_disabled_ingestion(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert client.post("/api/v1/internal/events", json=event()).status_code == 401
    assert (
        client.post(
            "/api/v1/internal/events", json=event(), headers={"Authorization": "Bearer wrong"}
        ).status_code
        == 401
    )
    monkeypatch.setattr(get_settings(), "telemetry_token", SecretStr(""))
    assert client.post("/api/v1/internal/events", json=event()).status_code == 503


def test_event_dedup_count_and_scope(client: TestClient, db: Session) -> None:
    headers = {"Authorization": "Bearer test-token"}
    payload = event()
    first = client.post("/api/v1/internal/events", json=payload, headers=headers)
    assert first.status_code == 200
    assert (
        client.post("/api/v1/internal/events", json=payload, headers=headers).json() == first.json()
    )
    payload["count"] = 3
    client.post("/api/v1/internal/events", json=payload, headers=headers)
    assert db.scalar(select(func.count()).select_from(Incident)) == 1
    assert client.get("/api/v1/incidents").json()[0]["occurrences"] == 3
    payload["namespace"] = "kube-system"
    assert client.post("/api/v1/internal/events", json=payload, headers=headers).status_code == 422


def test_normal_events_ignored_and_payload_limits(client: TestClient) -> None:
    headers = {"Authorization": "Bearer test-token"}
    payload = event()
    payload["type"] = "Normal"
    assert (
        client.post("/api/v1/internal/events", json=payload, headers=headers).json()["status"]
        == "ignored"
    )
    payload["message"] = "a" * 1025
    assert client.post("/api/v1/internal/events", json=payload, headers=headers).status_code == 422
    assert client.get("/api/v1/incidents?limit=999").status_code == 422


def test_alert_resolution_and_out_of_order_delivery(client: TestClient) -> None:
    headers = {"Authorization": "Bearer test-token"}
    alert = {
        "status": "firing",
        "labels": {
            "alertname": "WorkloadReplicasUnavailable",
            "namespace": "kubesentinel",
            "deployment": "fault",
        },
        "startsAt": "2026-11-02T10:00:00Z",
    }
    for _ in range(2):
        assert (
            client.post(
                "/api/v1/internal/alerts", json={"alerts": [alert]}, headers=headers
            ).status_code
            == 200
        )
    alert["status"] = "resolved"
    alert["endsAt"] = "2026-11-02T10:05:00Z"
    client.post("/api/v1/internal/alerts", json={"alerts": [alert]}, headers=headers)
    alert["status"] = "firing"
    client.post("/api/v1/internal/alerts", json={"alerts": [alert]}, headers=headers)
    rows = client.get("/api/v1/incidents").json()
    assert len(rows) == 1 and rows[0]["status"] == "resolved"


def test_prometheus_outage_does_not_break_incidents_or_liveness(client: TestClient) -> None:
    metrics = Mock(spec=PrometheusClient)
    metrics.query.side_effect = MetricsUnavailable()
    app.dependency_overrides[get_metrics] = lambda: cast(PrometheusClient, metrics)
    assert client.get("/api/v1/metrics/cpu").status_code == 503
    assert client.get("/api/v1/telemetry/health").status_code == 503
    assert client.get("/api/v1/incidents").status_code == 200
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/metrics/arbitrary-promql").status_code == 404


def test_metric_labels_use_route_templates(client: TestClient) -> None:
    client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert 'route="/api/v1/jobs/{job_id}"' in response.text
    assert "00000000-0000-0000-0000-000000000000" not in response.text
    assert "sentinel_remediation_actions_total" in response.text


def test_kubernetes_normalization() -> None:
    result = normalize(
        {
            "metadata": {
                "uid": "1",
                "namespace": "kubesentinel",
                "resourceVersion": "2",
                "creationTimestamp": datetime.now(UTC).isoformat(),
            },
            "involvedObject": {"name": "bad-pod"},
            "type": "Warning",
            "reason": "FailedScheduling",
            "message": "m" * 2048,
        }
    )
    assert result["resource"] == "bad-pod"
    assert len(result["message"]) == 1024
