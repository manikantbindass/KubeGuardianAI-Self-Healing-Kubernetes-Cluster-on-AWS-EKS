"""Escalation safety, durable retries, scoped history and real loopback HTTP delivery."""

import hashlib
import hmac
import json
import threading
import time
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from kubesentinel_api.config import Settings, get_settings
from kubesentinel_api.escalations import Escalation, enqueue_escalation, process_escalation
from kubesentinel_api.operations.models import OperationsAudit
from kubesentinel_api.webhook_transport import deliver, validate_destination
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

SECRET = "test-signing-key-32-bytes-minimum-length"


@pytest.fixture(autouse=True)
def configuration(monkeypatch: pytest.MonkeyPatch, cache: Any) -> Generator[None]:
    for key, value in {
        "APP_ENV": "local",
        "ESCALATION_ENABLED": "true",
        "ESCALATION_URL": "http://127.0.0.1:12345/hook",
        "ESCALATION_IP": "127.0.0.1",
        "ESCALATION_LOCAL_HTTP": "true",
        "ESCALATION_SIGNING_SECRET": SECRET,
        "ESCALATION_MAX_ATTEMPTS": "3",
        "ESCALATION_MAX_PENDING": "10",
        "OPS_AUTH_MODE": "development",
        "OPS_DEV_TOKEN": "escalation-admin",
        "OPS_DEV_VIEWER_TOKEN": "escalation-viewer",
        "OPS_BRIDGE_TOKEN": "escalation-bridge",
        "OPS_NAMESPACES": '["sentinel-lab"]',
        "OPS_DEMO_ENABLED": "true",
    }.items():
        monkeypatch.setenv(key, value)
    cache.eval.return_value = 1
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def queue(db: Session, phase: str = "Escalated", uid: str = "action-1", mode: str = "real") -> None:
    enqueue_escalation(
        db,
        mode,
        "sentinel-lab",
        "recovery-action",
        uid,
        {
            "status": {"phase": phase, "reason": "secret-raw-log"},
            "spec": {"token": "never-export-this"},
        },
    )


def test_snapshot_transaction_deduplicates_and_excludes_demo(
    client: TestClient, db: Session
) -> None:
    body = {
        "mode": "real",
        "rows": [
            {
                "kind": "RemediationAction",
                "namespace": "sentinel-lab",
                "name": "action",
                "uid": "test-action-uid",
                "resource_version": "1",
                "collected_at": datetime.now(UTC).isoformat(),
                "data": {"status": {"phase": "Escalated", "reason": "private-log"}},
            }
        ],
    }
    assert client.post("/api/v1/ops/internal/snapshots", json=body).status_code == 401
    for _ in range(2):
        assert (
            client.post(
                "/api/v1/ops/internal/snapshots",
                json=body,
                headers={"Authorization": "Bearer escalation-bridge"},
            ).status_code
            == 200
        )
    rows = list(db.scalars(select(Escalation)))
    assert len(rows) == 1 and rows[0].attempts == 0
    assert "private-log" not in json.dumps(rows[0].payload)
    body["mode"] = "demo"
    client.post(
        "/api/v1/ops/internal/snapshots",
        json=body,
        headers={"Authorization": "Bearer escalation-bridge"},
    )
    assert db.scalar(select(func.count()).select_from(Escalation)) == 1
    assert client.get("/api/v1/ops/escalations").status_code == 401
    response = client.get(
        "/api/v1/ops/escalations", headers={"Authorization": "Bearer escalation-viewer"}
    )
    assert response.status_code == 200 and len(response.json()) == 1
    assert all(x not in response.text for x in [SECRET, "http://", "payload"])


def test_disabled_and_non_escalation_phases_do_not_enqueue(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    for phase in ["Succeeded", "DryRun", "Rejected", "AwaitingApproval"]:
        queue(db, phase)
    queue(db, mode="demo")
    monkeypatch.setenv("ESCALATION_ENABLED", "false")
    get_settings.cache_clear()
    queue(db)
    assert not process_escalation(db)
    assert db.scalar(select(func.count()).select_from(Escalation)) == 0


@pytest.mark.parametrize(
    "status,expected",
    [
        (204, "delivered"),
        (302, "dead"),
        (400, "dead"),
        (401, "dead"),
        (429, "pending"),
        (503, "pending"),
    ],
)
def test_status_retry_policy(
    db: Session, monkeypatch: pytest.MonkeyPatch, status: int, expected: str
) -> None:
    queue(db)
    db.commit()
    sender = Mock(return_value=status)
    monkeypatch.setattr("kubesentinel_api.escalations.deliver", sender)
    assert process_escalation(db)
    row = db.scalar(select(Escalation))
    assert row and row.state == expected and row.attempts == 1 and row.last_status == status
    assert not process_escalation(db)  # completed or backoff is in the future
    assert sender.call_count == 1


def test_network_failure_is_bounded_and_redacted(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue(db)
    db.commit()
    sender = Mock(side_effect=OSError("SECRET token response"))
    monkeypatch.setattr("kubesentinel_api.escalations.deliver", sender)
    for _ in range(3):
        row = db.scalar(select(Escalation))
        assert row
        row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
        assert process_escalation(db)
    assert row is not None and row.state == "dead" and row.attempts == 3
    audits = list(db.scalars(select(OperationsAudit)))
    assert len(audits) == 7
    assert "SECRET" not in str([a.detail for a in audits])
    assert not process_escalation(db)


@pytest.mark.parametrize("change", ["destination", "scope", "expired"])
def test_cancel_stale_destination_or_scope(
    db: Session, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    queue(db)
    db.commit()
    row = db.scalar(select(Escalation))
    assert row
    if change == "destination":
        monkeypatch.setenv("ESCALATION_URL", "http://127.0.0.1:12346/new")
    elif change == "scope":
        monkeypatch.setenv("OPS_NAMESPACES", '["other"]')
    else:
        row.created_at = datetime.now(UTC) - timedelta(days=2)
        db.commit()
    get_settings.cache_clear()
    sender = Mock(side_effect=AssertionError("must not send"))
    monkeypatch.setattr("kubesentinel_api.escalations.deliver", sender)
    assert process_escalation(db)
    assert row.state == "cancelled" and row.attempts == 0
    sender.assert_not_called()


def test_capacity_and_transaction_rollback(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ESCALATION_MAX_PENDING", "1")
    get_settings.cache_clear()
    queue(db)
    db.commit()
    with pytest.raises(HTTPException, match="backlog"):
        queue(db, uid="action-2")
    db.rollback()
    assert db.scalar(select(func.count()).select_from(Escalation)) == 1
    queue(db)  # duplicates must not consume the available capacity
    db.rollback()


@pytest.mark.parametrize(
    "url,ip,local",
    [
        ("https://receiver.example/hook", "169.254.169.254", False),
        ("https://receiver.example/hook", "127.0.0.1", False),
        ("https://receiver.example/hook", "10.0.0.1", False),
        ("http://receiver.example/hook", "8.8.8.8", False),
        ("https://receiver.example:444/hook", "8.8.8.8", False),
        ("https://user:password@receiver.example/hook", "8.8.8.8", False),
        ("https://receiver.example/hook?secret=x", "8.8.8.8", False),
        ("http://localhost/hook", "127.0.0.1", True),
        ("https://receiver.example/hook", "::ffff:127.0.0.1", False),
    ],
)
def test_ssrf_destination_rejected(url: str, ip: str, local: bool) -> None:
    with pytest.raises(ValueError):
        validate_destination(url, ip, local)


def test_prod_rejects_local_http_and_short_secret() -> None:
    with pytest.raises(ValueError):
        Settings(
            app_env="production",
            escalation_enabled=True,
            escalation_local_http=True,
            escalation_url=SecretStr("http://127.0.0.1/hook"),
            escalation_ip="127.0.0.1",
            escalation_signing_secret=SecretStr(SECRET),
        )
    with pytest.raises(ValueError, match="32 bytes"):
        Settings(
            escalation_enabled=True,
            escalation_url=SecretStr("https://receiver.example/hook"),
            escalation_ip="8.8.8.8",
            escalation_signing_secret=SecretStr("short"),
        )


def test_loopback_delivery_and_signature(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    received: list[tuple[bytes, dict[str, str]]] = []

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            received.append(
                (self.rfile.read(int(self.headers["Content-Length"])), dict(self.headers.items()))
            )
            self.send_response(204)
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("ESCALATION_URL", f"http://127.0.0.1:{server.server_port}/hook")
        get_settings.cache_clear()
        queue(db)
        db.commit()
        assert process_escalation(db)
        assert len(received) == 1
        body, headers = received[0]
        stamp = headers["X-KubeSentinel-Timestamp"]
        expected = (
            "sha256="
            + hmac.new(SECRET.encode(), stamp.encode() + b"." + body, hashlib.sha256).hexdigest()
        )
        assert hmac.compare_digest(expected, headers["X-KubeSentinel-Signature"])
        assert abs(time.time() - int(stamp)) < 5
        assert json.loads(body)["event_id"] == headers["X-KubeSentinel-Event-ID"]
        assert "never-export" not in body.decode() and "secret-raw" not in body.decode()
        assert db.scalar(select(Escalation.state)) == "delivered"
    finally:
        server.shutdown()
        thread.join(timeout=3)
        server.server_close()


def test_tls_connects_pinned_address_and_checks_hostname(monkeypatch: pytest.MonkeyPatch) -> None:
    socket_factory = Mock()
    tls = Mock()
    connection = Mock()
    connection.getresponse.return_value.status = 204
    monkeypatch.setattr(
        "kubesentinel_api.webhook_transport.socket.create_connection", socket_factory
    )
    monkeypatch.setattr(
        "kubesentinel_api.webhook_transport.ssl.create_default_context", Mock(return_value=tls)
    )
    monkeypatch.setattr(
        "kubesentinel_api.webhook_transport.http.client.HTTPConnection",
        Mock(return_value=connection),
    )
    assert (
        deliver(
            validate_destination("https://receiver.example/hook", "8.8.8.8"),
            b"{}",
            "event-id",
            SECRET,
            "123",
            2,
        )
        == 204
    )
    socket_factory.assert_called_once_with(("8.8.8.8", 443), 2)
    tls.wrap_socket.assert_called_once_with(
        socket_factory.return_value, server_hostname="receiver.example"
    )
    connection.close.assert_called_once()


def test_crash_lease_recovers_and_attempt_is_persisted(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue(db)
    db.commit()
    # Simulate process death after committing the lease but before acknowledging delivery.
    monkeypatch.setattr("kubesentinel_api.escalations.deliver", Mock(side_effect=SystemExit))
    with pytest.raises(SystemExit):
        process_escalation(db)
    row = db.scalar(select(Escalation))
    assert row and row.state == "sending" and row.attempts == 1
    assert not process_escalation(db)  # live lease is not eligible
    row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    monkeypatch.setattr("kubesentinel_api.escalations.deliver", Mock(return_value=204))
    assert process_escalation(db)
    assert row.state == "delivered" and row.attempts == 2


def test_ingestion_backpressure_rolls_back_snapshot_and_outbox(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kubesentinel_api.operations.models import Snapshot

    monkeypatch.setenv("ESCALATION_MAX_PENDING", "1")
    get_settings.cache_clear()
    body = {
        "mode": "real",
        "rows": [
            {
                "kind": "RemediationAction",
                "namespace": "sentinel-lab",
                "name": f"action-{i}",
                "uid": f"uid-{i}",
                "resource_version": "1",
                "collected_at": datetime.now(UTC).isoformat(),
                "data": {"status": {"phase": "Failed"}},
            }
            for i in range(2)
        ],
    }
    response = client.post(
        "/api/v1/ops/internal/snapshots",
        json=body,
        headers={"Authorization": "Bearer escalation-bridge"},
    )
    assert response.status_code == 503
    db.rollback()
    assert db.scalar(select(func.count()).select_from(Snapshot)) == 0
    assert db.scalar(select(func.count()).select_from(Escalation)) == 0
