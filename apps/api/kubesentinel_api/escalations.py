"""Transactional escalation outbox. Advisory delivery never executes cluster actions."""

import hashlib
import http.client
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import JSON, DateTime, Index, Integer, String, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from kubesentinel_api.config import Settings, get_settings
from kubesentinel_api.database import Base
from kubesentinel_api.operations.models import OperationsAudit
from kubesentinel_api.webhook_transport import deliver, validate_destination

PHASES = {"Escalated", "Failed", "RolledBack"}


class Escalation(Base):
    __tablename__ = "escalation_deliveries"
    __table_args__ = (Index("ix_escalation_due", "state", "next_attempt_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    namespace: Mapped[str] = mapped_column(String(63))
    destination: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[int | None] = mapped_column(Integer, nullable=True)


def destination_id(settings: Settings) -> str:
    return hashlib.sha256(
        (settings.escalation_url.get_secret_value() + "|" + settings.escalation_ip).encode()
    ).hexdigest()


def enqueue_escalation(
    db: Session, mode: str, namespace: str, name: str, uid: str, data: dict[str, Any]
) -> None:
    settings = get_settings()
    status = data.get("status")
    phase = status.get("phase") if isinstance(status, dict) else None
    if (
        not settings.escalation_enabled
        or mode != "real"
        or not isinstance(phase, str)
        or phase not in PHASES
    ):
        return
    if namespace not in settings.ops_namespaces or not all(
        re.fullmatch(r"[a-zA-Z0-9.-]{1,253}", value) for value in (namespace, name, uid)
    ):
        return
    target = destination_id(settings)
    identity = hashlib.sha256(f"{target}:{namespace}:{uid}:{phase}".encode()).hexdigest()
    if db.get(Escalation, identity):
        return
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(7365821)"))
    pending = (
        db.scalar(
            select(func.count())
            .select_from(Escalation)
            .where(Escalation.state.in_(["pending", "sending"]))
        )
        or 0
    )
    if pending >= settings.escalation_max_pending:
        # Fail the enclosing ingestion transaction: bridge retries; no silent event loss.
        from fastapi import HTTPException

        raise HTTPException(503, "Escalation backlog full; collection must retry")
    now = datetime.now(UTC)
    # Only identifiers and typed phase are exported, never summaries, logs, secrets or plan bodies.
    payload = {
        "schema_version": 1,
        "event_id": identity,
        "type": "recovery.escalation",
        "action_uid": uid,
        "namespace": namespace,
        "action_name": name,
        "phase": phase,
        "recorded_at": now.isoformat(),
    }
    values = dict(
        id=identity,
        namespace=namespace,
        destination=target,
        payload=payload,
        state="pending",
        attempts=0,
        created_at=now,
        next_attempt_at=now,
    )
    insert = (
        pg_insert if db.bind is not None and db.bind.dialect.name == "postgresql" else sqlite_insert
    )
    inserted = db.scalar(
        insert(Escalation)
        .values(**values)
        .on_conflict_do_nothing(index_elements=["id"])
        .returning(Escalation.id)
    )
    if inserted:
        record(db, identity, "queued", namespace, {})


def record(
    db: Session, identity: str, outcome: str, namespace: str, detail: dict[str, Any]
) -> None:
    db.add(
        OperationsAudit(
            actor="escalation-worker",
            verb="escalation.delivery",
            target=identity,
            outcome=outcome,
            mode="real",
            correlation_id=identity,
            detail={"namespace": namespace, **detail},
        )
    )


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def process_escalation(db: Session) -> bool:
    settings = get_settings()
    if not settings.escalation_enabled:
        return False
    now = datetime.now(UTC)
    row = db.scalar(
        select(Escalation)
        .where(Escalation.state.in_(["pending", "sending"]), Escalation.next_attempt_at <= now)
        .order_by(Escalation.next_attempt_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if row is None:
        db.rollback()
        return False
    if (
        row.destination != destination_id(settings)
        or row.namespace not in settings.ops_namespaces
        or now - utc(row.created_at) > timedelta(hours=24)
        or row.attempts >= settings.escalation_max_attempts
    ):
        row.state, row.completed_at = "cancelled", now
        record(db, row.id, "cancelled", row.namespace, {})
        db.commit()
        return True
    row.attempts += 1
    attempt = row.attempts
    row.state = "sending"
    # Persist before I/O. Expired 30-second leases recover a crashed worker.
    # Receivers deduplicate event IDs across the unavoidable send/ack crash window.
    row.next_attempt_at = now + timedelta(seconds=30)
    record(db, row.id, "sending", row.namespace, {"attempt": attempt})
    body = json.dumps(row.payload, sort_keys=True, separators=(",", ":")).encode()
    identity = row.id
    db.commit()
    try:
        status = deliver(
            validate_destination(
                settings.escalation_url.get_secret_value(),
                settings.escalation_ip,
                settings.escalation_local_http and settings.app_env == "local",
            ),
            body,
            row.id,
            settings.escalation_signing_secret.get_secret_value(),
            str(int(now.timestamp())),
            settings.escalation_timeout_seconds,
        )
    except (OSError, ValueError, http.client.HTTPException):
        status = 0
    current = db.scalar(
        select(Escalation)
        .where(Escalation.id == identity)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if current is None or current.state != "sending" or current.attempts != attempt:
        db.rollback()
        return True
    row = current
    row.last_status = status or None
    if 200 <= status < 300:
        row.state = "delivered"
    elif status not in {0, 429} and not 500 <= status < 600:
        row.state = "dead"
    elif row.attempts >= settings.escalation_max_attempts:
        row.state = "dead"
    else:
        row.state = "pending"
        row.next_attempt_at = now + timedelta(seconds=min(300, 2**row.attempts))
    if row.state != "pending":
        row.completed_at = datetime.now(UTC)
    record(db, row.id, row.state, row.namespace, {"attempt": row.attempts, "http_status": status})
    db.commit()
    return True
