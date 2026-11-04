from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Mode = Literal["real", "demo"]


class SnapshotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["Node", "Deployment", "Pod", "Event", "RemediationAction", "RemediationPolicy"]
    namespace: str = Field(max_length=63)
    name: str = Field(min_length=1, max_length=253)
    uid: str = Field(min_length=1, max_length=128)
    resource_version: str = Field(min_length=1, max_length=64)
    collected_at: datetime
    data: dict[str, Any]

    @field_validator("collected_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Timezone required")
        return value.astimezone(UTC)


class SnapshotBatch(BaseModel):
    mode: Mode = "real"
    rows: list[SnapshotInput] = Field(max_length=250)
    # Full kind/namespace scopes included in this batch allow deletion of absent current rows.
    replace_scopes: list[str] = Field(default_factory=list, max_length=20)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    expected_uid: str = Field(min_length=1, max_length=128)
    expected_version: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=10, max_length=512)
    idempotency_key: str = Field(min_length=16, max_length=128)


class PolicyChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_uid: str = Field(min_length=1, max_length=128)
    expected_version: str = Field(min_length=1, max_length=64)
    dry_run: bool
    cooldown_seconds: int = Field(ge=0, le=86400)
    maximum_actions: int = Field(ge=1, le=20)
    maximum_replicas: int = Field(ge=1, le=100)
    reason: str = Field(min_length=10, max_length=512)
    idempotency_key: str = Field(min_length=16, max_length=128)


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_seconds: int = Field(default=15, ge=5, le=60)
    compact_tables: bool = False
    timezone: Literal["UTC", "local"] = "UTC"


class Review(BaseModel):
    note: str = Field(min_length=5, max_length=512)


class CostScenario(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    nodes: int = Field(ge=0, le=100)
    node_hourly: float = Field(ge=0, le=100)
    cluster_hourly: float = Field(ge=0, le=100)
    other_monthly: float = Field(ge=0, le=100000)
