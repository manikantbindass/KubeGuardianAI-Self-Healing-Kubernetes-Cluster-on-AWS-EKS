"""Bounded Prometheus queries and authenticated, idempotent telemetry normalization."""

import hashlib
import hmac
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from kubesentinel_api.config import get_settings
from kubesentinel_api.database import get_db
from kubesentinel_api.models import Incident

QUERIES = {
    "cpu": (
        'sum(rate(container_cpu_usage_seconds_total{namespace="kubesentinel",container!=""}[5m]))'
    ),
    "memory": 'sum(container_memory_working_set_bytes{namespace="kubesentinel",container!=""})',
    "restarts": 'sum(kube_pod_container_status_restarts_total{namespace="kubesentinel"})',
    "request_rate": "sum(rate(sentinel_http_requests_total[5m]))",
    "error_rate": 'sum(rate(sentinel_http_requests_total{status=~"5.."}[5m]))',
}


class MetricsUnavailable(Exception):
    pass


class PrometheusClient:
    def query(self, expression: str) -> list[dict[str, Any]]:
        url = (
            get_settings().prometheus_url.rstrip("/")
            + "/api/v1/query?"
            + urllib.parse.urlencode({"query": expression})
        )
        try:
            with urllib.request.urlopen(url, timeout=3) as result:
                body = json.loads(result.read(1_048_577))
            if body.get("status") != "success" or body["data"]["resultType"] != "vector":
                raise ValueError("Invalid Prometheus response")
            rows: list[dict[str, Any]] = body["data"]["result"]
            return rows
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise MetricsUnavailable from error


def get_metrics() -> PrometheusClient:
    return PrometheusClient()


class EventInput(BaseModel):
    uid: str = Field(min_length=1, max_length=128)
    resource_version: str = Field(min_length=1, max_length=64)
    namespace: str = Field(min_length=1, max_length=63)
    resource: str = Field(min_length=1, max_length=253)
    reason: str = Field(min_length=1, max_length=128)
    message: str = Field(max_length=1024)
    type: Literal["Normal", "Warning"]
    count: int = Field(default=1, ge=1)
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Timezone is required")
        return value


class Alert(BaseModel):
    status: Literal["firing", "resolved"]
    labels: dict[str, str] = Field(max_length=32)
    annotations: dict[str, str] = Field(default_factory=dict, max_length=16)
    startsAt: datetime
    endsAt: datetime | None = None

    @field_validator("labels", "annotations")
    @classmethod
    def bounded_values(cls, value: dict[str, str]) -> dict[str, str]:
        if any(len(key) > 128 or len(item) > 1024 for key, item in value.items()):
            raise ValueError("Oversized alert fields")
        return value


class AlertBatch(BaseModel):
    alerts: list[Alert] = Field(max_length=100)


class IncidentOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    source: str
    namespace: str
    resource: str
    reason: str
    summary: str
    severity: str
    status: str
    occurrences: int
    first_seen: datetime
    last_seen: datetime


def authenticate(authorization: Annotated[str | None, Header()] = None) -> None:
    token = get_settings().telemetry_token.get_secret_value()
    if not token:
        raise HTTPException(503, "Telemetry ingestion is disabled.")
    if not hmac.compare_digest(authorization or "", f"Bearer {token}"):
        raise HTTPException(401, "Invalid ingestion credentials.")


def store_incident(
    db: Session,
    *,
    identity: str,
    source: str,
    namespace: str,
    resource: str,
    reason: str,
    summary: str,
    severity: str,
    status: str,
    observed_at: datetime,
    occurrences: int | None = None,
) -> Incident:
    fingerprint = hashlib.sha256(identity.encode()).hexdigest()
    # The unique fingerprint and row lock serialize concurrent collector/webhook updates.
    row = db.scalar(select(Incident).where(Incident.fingerprint == fingerprint).with_for_update())
    if row is None:
        row = Incident(
            fingerprint=fingerprint,
            source=source,
            namespace=namespace,
            resource=resource,
            reason=reason,
            summary=summary,
            severity=severity,
            status=status,
            observed_at=observed_at,
            occurrences=occurrences or 1,
        )
        db.add(row)
        try:
            db.commit()
            db.refresh(row)
            return row
        except IntegrityError:
            db.rollback()
            row = db.scalar(
                select(Incident).where(Incident.fingerprint == fingerprint).with_for_update()
            )
            if row is None:
                raise
    old_time = (
        row.observed_at.replace(tzinfo=UTC) if row.observed_at.tzinfo is None else row.observed_at
    )
    if observed_at >= old_time:
        row.status = status
        row.summary = summary
        row.severity = severity
        row.observed_at = observed_at
        row.occurrences = max(row.occurrences, occurrences or 1)
        row.last_seen = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return row


router = APIRouter(prefix="/api/v1", tags=["telemetry"])
Db = Annotated[Session, Depends(get_db)]


@router.get("/incidents", response_model=list[IncidentOutput])
def incidents(db: Db, limit: int = 50) -> list[Incident]:
    if not 1 <= limit <= 100:
        raise HTTPException(422, "Limit must be between 1 and 100.")
    return list(db.scalars(select(Incident).order_by(Incident.last_seen.desc()).limit(limit)))


@router.get("/metrics/{name}")
def query_metrics(
    name: str, metrics: Annotated[PrometheusClient, Depends(get_metrics)]
) -> dict[str, Any]:
    if name not in QUERIES:
        raise HTTPException(404, "Unknown metric query.")
    try:
        return {"status": "ok", "query": name, "result": metrics.query(QUERIES[name])}
    except MetricsUnavailable as error:
        raise HTTPException(
            503, "Metrics are temporarily unavailable; incidents remain readable."
        ) from error


@router.get("/telemetry/health")
def telemetry_health(
    response: Response, metrics: Annotated[PrometheusClient, Depends(get_metrics)]
) -> dict[str, Any]:
    try:
        result = metrics.query('up{job="sentinel-api"}')
        healthy = bool(result) and all(float(row["value"][1]) == 1 for row in result)
    except (MetricsUnavailable, ValueError, KeyError, TypeError):
        healthy = False
    response.status_code = 200 if healthy else 503
    return {"status": "ok" if healthy else "unavailable", "api_scrape": healthy}


@router.post("/internal/events", dependencies=[Depends(authenticate)])
def ingest_event(payload: EventInput, db: Db) -> dict[str, str]:
    if payload.namespace != "kubesentinel":
        raise HTTPException(422, "Collector scope is limited to kubesentinel.")
    # Normal scheduling/pull noise is not an incident; Warning events are durable evidence.
    if payload.type == "Normal":
        return {"status": "ignored"}
    row = store_incident(
        db,
        identity=f"kubernetes:{payload.namespace}:{payload.uid}",
        source="kubernetes",
        namespace=payload.namespace,
        resource=payload.resource,
        reason=payload.reason,
        summary=payload.message,
        severity="critical" if payload.reason == "OOMKilled" else "warning",
        status="open",
        observed_at=payload.observed_at,
        occurrences=payload.count,
    )
    return {"status": "accepted", "id": row.id}


@router.post("/internal/alerts", dependencies=[Depends(authenticate)])
def ingest_alerts(payload: AlertBatch, db: Db) -> dict[str, int]:
    for alert in payload.alerts:
        namespace = alert.labels.get("namespace", "kubesentinel")
        if namespace != "kubesentinel":
            continue
        reason = alert.labels.get("alertname", "UnknownAlert")[:128]
        resource = alert.labels.get("pod", alert.labels.get("deployment", "control-plane"))[:253]
        # Canonical bounded labels; replica-specific transport fields do not split incidents.
        identity = json.dumps([reason, namespace, resource, alert.startsAt.isoformat()])
        observed = alert.endsAt if alert.status == "resolved" and alert.endsAt else alert.startsAt
        if observed.tzinfo is None:
            raise HTTPException(422, "Alert timestamps require timezones.")
        store_incident(
            db,
            identity=identity,
            source="alertmanager",
            namespace=namespace,
            resource=resource,
            reason=reason,
            summary=alert.annotations.get("summary", reason)[:1024],
            severity=alert.labels.get("severity", "warning")
            if alert.labels.get("severity") in {"info", "warning", "critical"}
            else "warning",
            status="resolved" if alert.status == "resolved" else "open",
            observed_at=observed,
        )
    return {"accepted": len(payload.alerts)}
