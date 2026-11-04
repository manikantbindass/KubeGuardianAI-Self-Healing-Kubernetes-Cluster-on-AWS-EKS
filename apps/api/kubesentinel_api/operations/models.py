import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from kubesentinel_api.database import Base


class Snapshot(Base):
    __tablename__ = "operations_snapshots"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mode: Mapped[str] = mapped_column(String(8), index=True)
    kind: Mapped[str] = mapped_column(String(24), index=True)
    namespace: Mapped[str] = mapped_column(String(63), index=True)
    name: Mapped[str] = mapped_column(String(253))
    uid: Mapped[str] = mapped_column(String(128))
    resource_version: Mapped[str] = mapped_column(String(64))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data: Mapped[dict[str, Any]] = mapped_column(JSON)


class OperationsAudit(Base):
    __tablename__ = "operations_audit"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    actor: Mapped[str] = mapped_column(String(256))
    verb: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(String(256))
    outcome: Mapped[str] = mapped_column(String(32))
    mode: Mapped[str] = mapped_column(String(8), index=True)
    correlation_id: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Command(Base):
    __tablename__ = "operations_commands"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    identity: Mapped[str] = mapped_column(String(64), unique=True)
    payload_digest: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(256))
    kind: Mapped[str] = mapped_column(String(24))
    namespace: Mapped[str] = mapped_column(String(63))
    target: Mapped[str] = mapped_column(String(253))
    mode: Mapped[str] = mapped_column(String(8))
    state: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)


class Preference(Base):
    __tablename__ = "operations_preferences"
    actor: Mapped[str] = mapped_column(String(256), primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)


class IncidentReview(Base):
    __tablename__ = "operations_incident_reviews"
    incident_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor: Mapped[str] = mapped_column(String(256))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    note: Mapped[str] = mapped_column(String(512))
