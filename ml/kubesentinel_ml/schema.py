"""Redacted, bounded input contract shared by collection, training and inference."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Metrics(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    cpu_ratio: float | None = Field(default=None, ge=0, le=1000)
    memory_ratio: float | None = Field(default=None, ge=0, le=1000)
    restarts: float | None = Field(default=None, ge=0, le=1_000_000)
    error_ratio: float | None = Field(default=None, ge=0, le=1)
    latency_p95_ms: float | None = Field(default=None, ge=0, le=3_600_000)
    pending_seconds: float | None = Field(default=None, ge=0, le=604800)
    availability_ratio: float | None = Field(default=None, ge=0, le=1)
    deployment_changes: float | None = Field(default=None, ge=0, le=1_000_000)
    node_pressure_ratio: float | None = Field(default=None, ge=0, le=1)
    saturation_ratio: float | None = Field(default=None, ge=0, le=1000)
    log_errors: float | None = Field(default=None, ge=0, le=1_000_000)
    warning_events: float | None = Field(default=None, ge=0, le=1_000_000)


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=128)
    timestamp: datetime
    dataset_id: str = Field(min_length=1, max_length=128)
    provenance: Literal["real", "synthetic"]
    origin: Literal["prometheus", "loki", "kubernetes", "synthetic"]
    namespace: str = Field(default="kubesentinel", pattern=r"^[a-z0-9-]{1,63}$")
    resource: str = Field(min_length=1, max_length=253)
    metrics: Metrics
    label: bool | None = None
    incident_id: str | None = Field(default=None, min_length=1, max_length=128)
    fault_started_at: datetime | None = None

    @field_validator("timestamp", "fault_started_at")
    @classmethod
    def utc(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            if value.tzinfo is None:
                raise ValueError("Timezone is required")
            return value.astimezone(UTC)
        return value

    @model_validator(mode="after")
    def provenance_consistent(self) -> "Observation":
        if (self.provenance == "synthetic") != (self.origin == "synthetic"):
            raise ValueError("Synthetic and real origin/provenance must agree")
        if self.fault_started_at and self.fault_started_at > self.timestamp:
            raise ValueError("Fault start cannot be in the future")
        if self.label is True and not self.incident_id:
            raise ValueError("Positive labels require incident lineage")
        return self
