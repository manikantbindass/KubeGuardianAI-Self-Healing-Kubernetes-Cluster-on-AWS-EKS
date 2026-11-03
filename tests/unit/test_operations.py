"""Operations authorization, mode separation, durable outbox and signer contract."""

import base64
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key
from fastapi.testclient import TestClient
from kubesentinel_api.config import get_settings
from kubesentinel_api.operations import auth
from kubesentinel_api.operations.commands import canonical
from kubesentinel_api.operations.demo import fixture
from kubesentinel_api.operations.models import Command, OperationsAudit, Snapshot
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

ADMIN = {"Authorization": "Bearer test-admin"}
VIEWER = {"Authorization": "Bearer test-viewer"}
BRIDGE = {"Authorization": "Bearer test-bridge"}


@pytest.fixture(autouse=True)
def operations_config(monkeypatch: pytest.MonkeyPatch, cache: Any) -> Generator[None]:
    for key, value in {
        "APP_ENV": "local",
        "OPS_AUTH_MODE": "development",
        "OPS_DEV_TOKEN": "test-admin",
        "OPS_DEV_VIEWER_TOKEN": "test-viewer",
        "OPS_BRIDGE_TOKEN": "test-bridge",
        "OPS_DEMO_ENABLED": "true",
        "OPS_APPROVAL_KEY_PATH": "",
        "OPS_LOKI_URL": "",
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    cache.eval.return_value = 1
    yield
    get_settings.cache_clear()


def seed(client: TestClient, mode: str = "demo") -> dict[str, Any]:
    body = fixture()
    body["mode"] = mode
    response = client.post("/api/v1/ops/internal/snapshots", headers=BRIDGE, json=body)
    assert response.status_code == 200, response.text
    return dict(client.get(f"/api/v1/ops/view?mode={mode}", headers=ADMIN).json())


def action(view: dict[str, Any]) -> dict[str, Any]:
    return dict(
        next(
            r
            for r in view["resources"]
            if r["kind"] == "RemediationAction"
            and r["data"]["status"]["phase"] == "AwaitingApproval"
        )
    )


def decision(row: dict[str, Any], decision: str = "reject", **updates: Any) -> dict[str, Any]:
    return {
        "decision": decision,
        "reason": "Reviewed exact immutable plan",
        "expected_uid": row["uid"],
        "expected_version": row["resource_version"],
        "idempotency_key": "test-unique-decision-001",
        **updates,
    }


def test_default_real_no_synthetic_fallback(client: TestClient) -> None:
    seed(client)
    body = client.get("/api/v1/ops/view", headers=ADMIN).json()
    assert body["mode"] == "real" and body["resources"] == [] and body["incidents"] == []
    assert body["bridge"]["stale"] is True


@pytest.mark.parametrize(
    "path", ["session", "view", "preferences", "model", "metrics/cpu", "stream"]
)
def test_reads_require_authentication(client: TestClient, path: str) -> None:
    assert client.get("/api/v1/ops/" + path).status_code == 401


def test_namespaces_and_modes_fail_closed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert client.get("/api/v1/ops/view?namespace=kube-system", headers=ADMIN).status_code == 403
    monkeypatch.setenv("OPS_DEMO_ENABLED", "false")
    get_settings.cache_clear()
    assert client.get("/api/v1/ops/view?mode=demo", headers=ADMIN).status_code == 403
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    assert client.get("/api/v1/ops/session", headers=ADMIN).status_code == 503


def test_bridge_has_independent_credentials_and_scope(client: TestClient) -> None:
    body = fixture()
    assert (
        client.post("/api/v1/ops/internal/snapshots", headers=ADMIN, json=body).status_code == 401
    )
    body["rows"][0]["namespace"] = "kube-system"
    assert (
        client.post("/api/v1/ops/internal/snapshots", headers=BRIDGE, json=body).status_code == 403
    )


def test_demo_decision_audited_idempotent_never_delivered(client: TestClient, db: Session) -> None:
    row = action(seed(client))
    path = f"/api/v1/ops/actions/{row['id']}/decision?mode=demo"
    assert client.post(path, headers=VIEWER, json=decision(row)).status_code == 403
    first = client.post(path, headers=ADMIN, json=decision(row))
    assert first.status_code == 200, first.text
    assert first.json()["state"] == "demo_recorded"
    assert client.post(path, headers=ADMIN, json=decision(row)).json()["id"] == first.json()["id"]
    assert db.scalar(select(func.count()).select_from(Command)) == 1
    assert (
        db.scalar(
            select(func.count())
            .select_from(OperationsAudit)
            .where(OperationsAudit.verb == "reject")
        )
        == 1
    )
    assert client.get("/api/v1/ops/internal/commands", headers=BRIDGE).json() == []
    assert (
        client.post(
            path, headers=ADMIN, json=decision(row, reason="A different review reason")
        ).status_code
        == 409
    )


def test_version_staleness_and_rate_guards(client: TestClient, db: Session, cache: Any) -> None:
    row = action(seed(client, "real"))
    path = f"/api/v1/ops/actions/{row['id']}/decision"
    assert (
        client.post(path, headers=ADMIN, json=decision(row, expected_version="changed")).status_code
        == 409
    )
    stored = db.get(Snapshot, row["id"])
    assert stored is not None
    stored.collected_at = datetime.now(UTC) - timedelta(seconds=31)
    db.commit()
    assert client.post(path, headers=ADMIN, json=decision(row)).status_code == 409
    stored.collected_at = datetime.now(UTC)
    db.commit()
    cache.eval.return_value = 21
    assert client.post(path, headers=ADMIN, json=decision(row)).status_code == 429
    cache.eval.side_effect = RedisConnectionError("offline")
    assert client.post(path, headers=ADMIN, json=decision(row)).status_code == 503
    assert db.scalar(select(func.count()).select_from(Command)) == 0


def test_real_rejection_outbox_ack_does_not_claim_recovery(client: TestClient, db: Session) -> None:
    row = action(seed(client, "real"))
    result = client.post(
        f"/api/v1/ops/actions/{row['id']}/decision", headers=ADMIN, json=decision(row)
    )
    assert result.json()["state"] == "pending"
    pending = client.get("/api/v1/ops/internal/commands", headers=BRIDGE).json()
    assert len(pending) == 1 and pending[0]["kind"] == "reject"
    ack = client.post(
        "/api/v1/ops/internal/commands/" + pending[0]["id"],
        headers=BRIDGE,
        json={"state": "delivered", "result": "Rejection annotation accepted"},
    )
    assert ack.status_code == 200
    command = db.get(Command, pending[0]["id"])
    assert command is not None and command.state == "delivered"
    snapshot = db.get(Snapshot, row["id"])
    assert snapshot is not None and snapshot.data["status"]["phase"] == "AwaitingApproval"


def test_signer_binds_approval_to_exact_plan(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    private = Ed25519PrivateKey.generate()
    public = private.public_key()
    raw = private.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
    )
    raw += public.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    key = tmp_path / "key"
    key.write_text(base64.b64encode(raw).decode())
    monkeypatch.setenv("OPS_APPROVAL_KEY_PATH", str(key))
    get_settings.cache_clear()
    row = action(seed(client, "real"))
    stored = db.get(Snapshot, row["id"])
    assert stored is not None
    stored.data = {**stored.data, "planDigest": "a" * 64}
    db.commit()
    result = client.post(
        f"/api/v1/ops/actions/{row['id']}/decision", headers=ADMIN, json=decision(row, "approve")
    )
    assert result.status_code == 200, result.text
    command = db.get(Command, result.json()["id"])
    assert command is not None
    spec = command.payload["approval"]["spec"]
    message = canonical(
        [
            "kubesentinel-approval-v1",
            row["namespace"],
            row["uid"],
            "a" * 64,
            spec["expiresAt"],
            spec["keyID"],
        ]
    ).encode()
    public.verify(base64.b64decode(spec["signature"]), message)
    assert "approval" not in result.json()  # private command payload never reaches browser


def test_preferences_are_principal_scoped_and_persistent(client: TestClient) -> None:
    body = {"refresh_seconds": 30, "compact_tables": True, "timezone": "local"}
    assert client.post("/api/v1/ops/preferences", headers=VIEWER, json=body).json() == body
    assert client.get("/api/v1/ops/preferences", headers=VIEWER).json() == body
    assert client.get("/api/v1/ops/preferences", headers=ADMIN).json()["compact_tables"] is False


def test_logs_fixed_scope_and_demo_label(client: TestClient) -> None:
    view = seed(client)
    pod = next(r for r in view["resources"] if r["kind"] == "Pod")
    assert (
        client.get(f"/api/v1/ops/resources/{pod['id']}/logs?mode=demo", headers=VIEWER).json()[
            "source"
        ]
        == "synthetic"
    )
    assert client.get(f"/api/v1/ops/resources/{pod['id']}/logs", headers=VIEWER).status_code == 404


@pytest.mark.parametrize(
    "override",
    [
        {},
        {"aud": "wrong"},
        {"iss": "https://other.invalid"},
        {"exp": 1},
        {"kubesentinel_roles": []},
    ],
)
def test_oidc_validates_claims_and_roles(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, override: dict[str, Any]
) -> None:
    monkeypatch.setenv("OPS_AUTH_MODE", "oidc")
    monkeypatch.setenv("OPS_OIDC_ISSUER", "https://issuer.invalid")
    monkeypatch.setenv("OPS_OIDC_JWKS_URL", "https://issuer.invalid/keys")
    get_settings.cache_clear()
    key = generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(
        auth,
        "jwks",
        lambda _: SimpleNamespace(
            get_signing_key_from_jwt=Mock(return_value=SimpleNamespace(key=key.public_key()))
        ),
    )
    now = int(datetime.now(UTC).timestamp())
    claims = {
        "sub": "alice",
        "iss": "https://issuer.invalid",
        "aud": "kubesentinel-api",
        "exp": now + 300,
        "iat": now,
        "kubesentinel_roles": ["viewer"],
        **override,
    }
    token = jwt.encode(claims, key, algorithm="RS256")
    result = client.get("/api/v1/ops/session", headers={"Authorization": "Bearer " + token})
    assert result.status_code == (
        200 if not override else 403 if override == {"kubesentinel_roles": []} else 401
    )


def test_snapshot_full_scope_prunes_deleted_pods(client: TestClient) -> None:
    seed(client, "real")
    result = client.post(
        "/api/v1/ops/internal/snapshots",
        headers=BRIDGE,
        json={"mode": "real", "rows": [], "replace_scopes": ["Pod:sentinel-lab"]},
    )
    assert result.status_code == 200
    assert not any(
        r["kind"] == "Pod"
        for r in client.get("/api/v1/ops/view", headers=ADMIN).json()["resources"]
    )
