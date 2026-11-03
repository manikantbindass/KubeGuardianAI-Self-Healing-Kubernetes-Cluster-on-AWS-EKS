"""Decision outbox: browser/server never receives Deployment mutation permissions."""

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from kubesentinel_api.config import get_settings
from kubesentinel_api.operations.auth import Principal
from kubesentinel_api.operations.models import Command, OperationsAudit, Snapshot
from kubesentinel_api.operations.schemas import Decision, PolicyChange


def canonical(value: object) -> str:
    # Go encoding/json preserves declared struct field order. The bridge stores exact Go plan JSON.
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def audit(
    db: Session,
    user: Principal,
    verb: str,
    target: str,
    outcome: str,
    mode: str,
    correlation_id: str,
    detail: dict[str, Any] | None = None,
) -> None:
    db.add(
        OperationsAudit(
            actor=user.subject,
            verb=verb,
            target=target,
            outcome=outcome,
            mode=mode,
            correlation_id=correlation_id,
            detail=detail or {},
        )
    )


def command_output(row: Command) -> dict[str, Any]:
    return {
        "id": row.id,
        "kind": row.kind,
        "target": row.target,
        "namespace": row.namespace,
        "state": row.state,
        "created_at": row.created_at,
        "expires_at": row.expires_at,
        "actor": row.actor,
        "mode": row.mode,
        "result": row.result,
    }


def enqueue(
    db: Session,
    user: Principal,
    snapshot: Snapshot,
    kind: str,
    key: str,
    reason: str,
    payload: dict[str, Any],
    correlation_id: str,
) -> Command:
    identity = hashlib.sha256(
        canonical([user.subject, kind, snapshot.id, key]).encode()
    ).hexdigest()
    semantic = {key: value for key, value in payload.items() if key != "approval"}
    digest = hashlib.sha256(canonical(semantic).encode()).hexdigest()
    existing = db.scalar(select(Command).where(Command.identity == identity))
    if existing:
        if existing.payload_digest != digest:
            raise HTTPException(409, "Idempotency key was already used for a different request")
        return existing
    row = Command(
        identity=identity,
        payload_digest=digest,
        actor=user.subject,
        kind=kind,
        namespace=snapshot.namespace,
        target=snapshot.name,
        mode=snapshot.mode,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        payload=payload,
    )
    if snapshot.mode == "demo":
        row.state = "demo_recorded"
        row.result = "Synthetic decision recorded; no cluster command was sent"
    db.add(row)
    audit(
        db,
        user,
        kind,
        snapshot.name,
        "demo_recorded" if snapshot.mode == "demo" else "queued",
        snapshot.mode,
        correlation_id,
        {"reason": reason, "uid": snapshot.uid},
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Command).where(Command.identity == identity))
        if existing is None or existing.payload_digest != digest:
            raise HTTPException(409, "Concurrent conflicting request") from None
        return existing
    db.refresh(row)
    return row


def check_snapshot(snapshot: Snapshot, uid: str, version: str) -> None:
    collected = (
        snapshot.collected_at.replace(tzinfo=UTC)
        if snapshot.collected_at.tzinfo is None
        else snapshot.collected_at
    )
    if snapshot.uid != uid or snapshot.resource_version != version:
        raise HTTPException(409, "Resource changed; refresh and review the new version")
    if snapshot.mode == "real" and (datetime.now(UTC) - collected).total_seconds() > 30:
        raise HTTPException(409, "Resource snapshot is stale; wait for the bridge")


def decide(
    db: Session, user: Principal, snapshot: Snapshot, change: Decision, correlation: str
) -> Command:
    check_snapshot(snapshot, change.expected_uid, change.expected_version)
    data = snapshot.data
    if data.get("status", {}).get("phase") != "AwaitingApproval":
        raise HTTPException(409, "Only an action awaiting approval can receive a decision")
    payload: dict[str, Any] = {
        "uid": snapshot.uid,
        "resourceVersion": snapshot.resource_version,
        "reason": change.reason,
        "actor": user.subject,
    }
    if change.decision == "approve" and snapshot.mode == "real":
        settings = get_settings()
        if not settings.ops_approval_key_path:
            raise HTTPException(503, "Approval signing is not configured")
        spec = data["spec"]
        expiry = datetime.fromisoformat(spec["expiresAt"].replace("Z", "+00:00"))
        expiry = min(expiry, datetime.now(UTC) + timedelta(minutes=5)).replace(microsecond=0)
        if expiry <= datetime.now(UTC):
            raise HTTPException(409, "Action approval window expired")
        plan_digest = data.get("planDigest")
        if not isinstance(plan_digest, str) or len(plan_digest) != 64:
            raise HTTPException(409, "Bridge did not supply a verified plan digest")
        expires = expiry.isoformat().replace("+00:00", "Z")
        key_id = settings.ops_approval_key_id
        message = canonical(
            [
                "kubesentinel-approval-v1",
                snapshot.namespace,
                snapshot.uid,
                plan_digest,
                expires,
                key_id,
            ]
        ).encode()
        try:
            encoded = Path(settings.ops_approval_key_path).read_text(encoding="utf-8").strip()
            private = base64.b64decode(encoded, validate=True)
            if len(private) != 64:
                raise ValueError("Invalid Ed25519 private key")
            signature = Ed25519PrivateKey.from_private_bytes(private[:32]).sign(message)
        except (OSError, ValueError) as error:
            raise HTTPException(503, "Approval signer unavailable") from error
        payload["approval"] = {
            "apiVersion": "recovery.kubesentinel.ai/v1alpha1",
            "kind": "RemediationApproval",
            "metadata": {"name": "approve-" + snapshot.uid, "namespace": snapshot.namespace},
            "spec": {
                "actionUID": snapshot.uid,
                "actionDigest": plan_digest,
                "expiresAt": expires,
                "keyID": key_id,
                "signature": base64.b64encode(signature).decode(),
            },
        }
    return enqueue(
        db,
        user,
        snapshot,
        change.decision,
        change.idempotency_key,
        change.reason,
        payload,
        correlation,
    )


def change_policy(
    db: Session, user: Principal, snapshot: Snapshot, change: PolicyChange, correlation: str
) -> Command:
    check_snapshot(snapshot, change.expected_uid, change.expected_version)
    current = snapshot.data["spec"]
    if change.maximum_replicas < max(
        current.get("minimumReplicas", 1), current.get("minimumHealthyReplicas", 1)
    ):
        raise HTTPException(422, "Maximum replicas cannot violate policy minimums")
    return enqueue(
        db,
        user,
        snapshot,
        "policy",
        change.idempotency_key,
        change.reason,
        {
            "uid": snapshot.uid,
            "resourceVersion": snapshot.resource_version,
            "reason": change.reason,
            "spec": {
                "dryRun": change.dry_run,
                "cooldownSeconds": change.cooldown_seconds,
                "maxActionsPerWindow": change.maximum_actions,
                "maximumReplicas": change.maximum_replicas,
            },
        },
        correlation,
    )
