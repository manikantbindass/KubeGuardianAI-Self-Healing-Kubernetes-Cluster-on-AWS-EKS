"""Authenticated detector-to-incident interface; synthetic evidence cannot create live incidents."""

import json
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy.exc import IntegrityError

from kubesentinel_api.models import AnomalyEvidence
from kubesentinel_api.telemetry import Db, authenticate, store_incident


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    feature: str = Field(max_length=64)
    value: float
    reference: float
    detail: str = Field(max_length=256)


class Anomaly(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    namespace: Literal["kubesentinel"]
    resource: str = Field(min_length=1, max_length=253)
    window_start: datetime
    window_end: datetime
    provenance: Literal["real"]
    detector: Literal["rules", "robust_statistics", "isolation_forest"]
    model_version: str = Field(min_length=1, max_length=128)
    score: float = Field(ge=0)
    threshold: float = Field(gt=0)
    severity: Literal["warning", "critical"]
    explanations: list[Evidence] = Field(min_length=1, max_length=10)

    @field_validator("window_start", "window_end")
    @classmethod
    def timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Timezone is required")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def valid_window(self) -> "Anomaly":
        if not 10 <= (self.window_end - self.window_start).total_seconds() <= 3600:
            raise ValueError("Window duration must be 10..3600 seconds")
        if self.window_end > datetime.now(UTC) or self.score < self.threshold:
            raise ValueError("Only completed anomalous windows are accepted")
        return self


class AnomalyBatch(BaseModel):
    anomalies: list[Anomaly] = Field(min_length=1, max_length=256)


router = APIRouter(prefix="/api/v1", tags=["anomalies"])


@router.post("/internal/anomalies", dependencies=[Depends(authenticate)])
def ingest_anomalies(payload: AnomalyBatch, db: Db) -> dict[str, object]:
    ids = []
    for anomaly in payload.anomalies:
        identity = json.dumps(
            [
                "anomaly-v1",
                anomaly.namespace,
                anomaly.resource,
                anomaly.window_start.isoformat(),
                anomaly.window_end.isoformat(),
                anomaly.detector,
                anomaly.model_version,
            ]
        )
        incident = store_incident(
            db,
            identity=identity,
            source="anomaly-detector",
            namespace=anomaly.namespace,
            resource=anomaly.resource,
            reason="AnomalyDetected",
            summary=f"{anomaly.detector}: uncalibrated score {anomaly.score:.5g} "
            f">= {anomaly.threshold:.5g}; {anomaly.explanations[0].feature}",
            severity=anomaly.severity,
            status="open",
            observed_at=anomaly.window_end,
        )
        if db.get(AnomalyEvidence, incident.id) is None:
            db.add(
                AnomalyEvidence(
                    incident_id=incident.id,
                    detector=anomaly.detector,
                    model_version=anomaly.model_version,
                    score=anomaly.score,
                    threshold=anomaly.threshold,
                    provenance=anomaly.provenance,
                    explanations=[e.model_dump() for e in anomaly.explanations],
                )
            )
            try:
                db.commit()
            except IntegrityError:
                db.rollback()  # A concurrent replay already supplied the same evidence row.
                if db.get(AnomalyEvidence, incident.id) is None:
                    raise
        ids.append(incident.id)
    return {"accepted": len(ids), "incident_ids": ids}


@router.get("/incidents/{incident_id}/anomaly")
def anomaly_evidence(incident_id: str, db: Db) -> dict[str, object]:
    row = db.get(AnomalyEvidence, incident_id)
    if row is None:
        raise HTTPException(404, "No anomaly evidence for this incident")
    return {
        "incident_id": row.incident_id,
        "detector": row.detector,
        "model_version": row.model_version,
        "score": row.score,
        "threshold": row.threshold,
        "provenance": row.provenance,
        "explanations": row.explanations,
        "score_kind": "uncalibrated_anomaly_score",
    }
