"""Authenticated, persistent operations read model and audited decision endpoints."""

import asyncio
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from kubesentinel_api.config import get_settings
from kubesentinel_api.database import SessionLocal as SessionLocal
from kubesentinel_api.models import AnomalyEvidence, Incident
from kubesentinel_api.operations.auth import Cache, User, authorize, bridge, mutation_limit
from kubesentinel_api.operations.commands import audit, change_policy, command_output, decide
from kubesentinel_api.operations.models import (
    Command,
    IncidentReview,
    OperationsAudit,
    Preference,
    Snapshot,
)
from kubesentinel_api.operations.schemas import (
    CostScenario,
    Decision,
    Mode,
    PolicyChange,
    Preferences,
    Review,
    SnapshotBatch,
)
from kubesentinel_api.telemetry import Db

router = APIRouter(prefix="/api/v1/ops", tags=["operations"])


class ResourceOutput(BaseModel):
    id: str
    kind: str
    namespace: str
    name: str
    uid: str
    resource_version: str
    collected_at: datetime
    data: dict[str, Any]


class ViewOutput(BaseModel):
    mode: Mode
    generated_at: datetime
    namespaces: list[str]
    resources: list[ResourceOutput]
    incidents: list[dict[str, Any]]
    anomaly_evidence: list[dict[str, Any]]
    commands: list[dict[str, Any]]
    audit: list[dict[str, Any]]
    summary: dict[str, int | float | None]
    bridge: dict[str, Any]


def check_mode(mode: Mode) -> None:
    if mode == "demo" and not get_settings().ops_demo_enabled:
        raise HTTPException(403, "Synthetic demo mode is not enabled")


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def resource(db: Session, resource_id: str, mode: Mode, kind: str) -> Snapshot:
    row = db.get(Snapshot, resource_id)
    if row is None or row.mode != mode or row.kind != kind:
        raise HTTPException(404, "Resource not found")
    if row.namespace not in get_settings().ops_namespaces:
        raise HTTPException(403, "Resource namespace is outside the authorized scope")
    return row


@router.get("/session")
def session(user: User) -> dict[str, Any]:
    return {
        **user.model_dump(),
        "demo_enabled": get_settings().ops_demo_enabled,
        "namespaces": get_settings().ops_namespaces,
        "data_default": "real",
    }


@router.get("/view", response_model=ViewOutput)
def view(db: Db, user: User, mode: Mode = "real", namespace: str = "all") -> ViewOutput:
    check_mode(mode)
    allowed = get_settings().ops_namespaces
    if namespace != "all" and namespace not in allowed:
        raise HTTPException(403, "Namespace is outside the authorized operations scope")
    query = select(Snapshot).where(Snapshot.mode == mode, Snapshot.namespace.in_(["", *allowed]))
    if namespace != "all":
        query = query.where((Snapshot.namespace == namespace) | (Snapshot.namespace == ""))
    rows = list(db.scalars(query.order_by(Snapshot.kind, Snapshot.name).limit(1000)))
    incident_query = (
        select(Incident)
        .where(Incident.namespace.in_(allowed))
        .order_by(Incident.last_seen.desc())
        .limit(100)
    )
    if namespace != "all":
        incident_query = incident_query.where(Incident.namespace == namespace)
    incidents = list(db.scalars(incident_query)) if mode == "real" else []
    incident_data = []
    evidence = []
    for incident in incidents:
        review = db.get(IncidentReview, incident.id)
        incident_data.append(
            {
                "id": incident.id,
                "source": incident.source,
                "namespace": incident.namespace,
                "resource": incident.resource,
                "reason": incident.reason,
                "summary": incident.summary,
                "severity": incident.severity,
                "status": incident.status,
                "first_seen": incident.first_seen,
                "last_seen": incident.last_seen,
                "occurrences": incident.occurrences,
                "review": {"actor": review.actor, "note": review.note, "at": review.at}
                if review
                else None,
                "confidence": None,
                "confidence_label": "Not calibrated",
            }
        )
        anomaly = db.get(AnomalyEvidence, incident.id)
        if anomaly:
            evidence.append(
                {
                    "incident_id": incident.id,
                    "at": incident.last_seen,
                    "resource": incident.resource,
                    "detector": anomaly.detector,
                    "model_version": anomaly.model_version,
                    "score": anomaly.score,
                    "threshold": anomaly.threshold,
                    "provenance": anomaly.provenance,
                    "explanations": anomaly.explanations,
                    "score_kind": "uncalibrated_anomaly_score",
                }
            )
    if mode == "demo":
        # Demo rows are explicitly imported fixtures, never substituted for real source failures.
        for row in rows:
            if row.kind == "Event" and row.data.get("demoIncident"):
                incident_data.append(row.data["demoIncident"])
            if row.kind == "Event" and row.data.get("demoAnomaly"):
                evidence.append(row.data["demoAnomaly"])
    audits = list(
        db.scalars(
            select(OperationsAudit)
            .where(OperationsAudit.mode == mode, OperationsAudit.verb != "snapshot.refresh")
            .order_by(OperationsAudit.id.desc())
            .limit(100)
        )
    )
    commands = list(
        db.scalars(
            select(Command)
            .where(Command.mode == mode)
            .order_by(Command.created_at.desc())
            .limit(100)
        )
    )
    deployments = [r for r in rows if r.kind == "Deployment"]
    pods = [r for r in rows if r.kind == "Pod"]
    action_rows = [r for r in rows if r.kind == "RemediationAction"]
    healthy = sum(bool(r.data.get("healthy")) for r in deployments)
    last = max((utc(r.collected_at) for r in rows), default=None)
    now = datetime.now(UTC)
    return ViewOutput(
        mode=mode,
        generated_at=now,
        namespaces=allowed,
        resources=[
            ResourceOutput(
                id=r.id,
                kind=r.kind,
                namespace=r.namespace,
                name=r.name,
                uid=r.uid,
                resource_version=r.resource_version,
                collected_at=r.collected_at,
                data=r.data,
            )
            for r in rows
        ],
        incidents=incident_data,
        anomaly_evidence=evidence,
        commands=[command_output(c) for c in commands],
        audit=[
            {
                "id": a.id,
                "at": a.at,
                "actor": a.actor,
                "verb": a.verb,
                "target": a.target,
                "outcome": a.outcome,
                "correlation_id": a.correlation_id,
                "detail": a.detail,
            }
            for a in audits
        ],
        summary={
            "nodes": sum(r.kind == "Node" for r in rows),
            "pods": len(pods),
            "workloads": len(deployments),
            "healthy_workloads": healthy,
            "unhealthy_workloads": len(deployments) - healthy,
            "active_incidents": sum(i.get("status") != "resolved" for i in incident_data),
            "recoveries": sum(
                r.data.get("status", {}).get("phase") == "Succeeded" for r in action_rows
            ),
            "awaiting_approval": sum(
                r.data.get("status", {}).get("phase") == "AwaitingApproval" for r in action_rows
            ),
        },
        bridge={
            "last_collected_at": last,
            "stale": last is None or (now - last).total_seconds() > 30,
            "resource_limit": 1000,
            "source": "synthetic fixture" if mode == "demo" else "Kubernetes bridge",
            "limited": len(rows) >= 1000 or any(r.data.get("collection_truncated") for r in rows),
        },
    )


@router.post("/actions/{resource_id}/decision")
def decision(
    resource_id: str,
    payload: Decision,
    db: Db,
    user: User,
    cache: Cache,
    request: Request,
    mode: Mode = "real",
) -> dict[str, Any]:
    check_mode(mode)
    authorize(user, "approver")
    mutation_limit(user, cache)
    row = decide(
        db,
        user,
        resource(db, resource_id, mode, "RemediationAction"),
        payload,
        request.state.correlation_id,
    )
    return command_output(row)


@router.post("/policies/{resource_id}")
def update_policy(
    resource_id: str,
    payload: PolicyChange,
    db: Db,
    user: User,
    cache: Cache,
    request: Request,
    mode: Mode = "real",
) -> dict[str, Any]:
    check_mode(mode)
    authorize(user, "admin")
    mutation_limit(user, cache)
    return command_output(
        change_policy(
            db,
            user,
            resource(db, resource_id, mode, "RemediationPolicy"),
            payload,
            request.state.correlation_id,
        )
    )


@router.post("/incidents/{incident_id}/review")
def review_incident(
    incident_id: str, payload: Review, db: Db, user: User, cache: Cache, request: Request
) -> dict[str, str]:
    authorize(user, "operator")
    mutation_limit(user, cache)
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(404, "Incident not found")
    if incident.namespace not in get_settings().ops_namespaces:
        raise HTTPException(403, "Incident namespace is outside the authorized scope")
    row = db.get(IncidentReview, incident_id)
    if row is None:
        row = IncidentReview(incident_id=incident_id, actor=user.subject, note=payload.note)
        db.add(row)
    row.actor, row.note, row.at = user.subject, payload.note, datetime.now(UTC)
    audit(db, user, "incident.review", incident_id, "saved", "real", request.state.correlation_id)
    db.commit()
    return {"status": "saved"}


@router.get("/preferences", response_model=Preferences)
def preferences(db: Db, user: User) -> Preferences:
    row = db.get(Preference, user.subject)
    return Preferences.model_validate(row.data) if row else Preferences()


@router.post("/preferences", response_model=Preferences)
def save_preferences(
    payload: Preferences, db: Db, user: User, cache: Cache, request: Request
) -> Preferences:
    mutation_limit(user, cache)
    row = db.get(Preference, user.subject)
    if row is None:
        db.add(Preference(actor=user.subject, data=payload.model_dump()))
    else:
        row.data = payload.model_dump()
    audit(db, user, "preferences.update", "self", "saved", "real", request.state.correlation_id)
    db.commit()
    return payload


@router.post("/cost-estimate")
def estimate(payload: CostScenario, user: User) -> dict[str, Any]:
    monthly = (
        730 * (payload.nodes * payload.node_hourly + payload.cluster_hourly) + payload.other_monthly
    )
    return {
        "monthly": round(monthly, 2),
        "hours": 730,
        "currency": "USD",
        "kind": "user-entered scenario; not an AWS bill or price quote",
        "excluded": ["tax", "data transfer", "unentered services", "credits"],
    }


@router.get("/metrics/{name}")
def metric_history(
    name: str, user: User, minutes: int = Query(default=60, ge=15, le=360), mode: Mode = "real"
) -> dict[str, Any]:
    check_mode(mode)
    scope = json.dumps("|".join(re.escape(ns) for ns in get_settings().ops_namespaces))
    selector = "{namespace=~" + scope + ',container!=""}'
    expressions = {
        "cpu": ("sum(rate(container_cpu_usage_seconds_total" + selector + "[2m]))"),
        "memory": ("sum(container_memory_working_set_bytes" + selector + ")"),
        "latency": (
            "1000 * histogram_quantile(0.95,sum by(le)"
            "(rate(sentinel_http_duration_seconds_bucket[5m])))"
        ),
        "requests": "sum(rate(sentinel_http_requests_total[5m]))",
    }
    if name not in expressions:
        raise HTTPException(404, "Unknown metric")
    if mode == "demo":
        # Values are deliberately synthetic, generated only by an explicit request for demo mode.
        import math

        end = int(time.time())
        factor = {"cpu": 1, "memory": 1e9, "latency": 60, "requests": 30}[name]
        return {
            "source": "synthetic",
            "points": [
                [
                    end - (59 - i) * 60,
                    factor * (1.1 + 0.25 * math.sin(i / 7) + (0.25 if 35 < i < 42 else 0)),
                ]
                for i in range(60)
            ],
        }
    query = urllib.parse.urlencode(
        {
            "query": expressions[name],
            "start": time.time() - minutes * 60,
            "end": time.time(),
            "step": max(15, minutes * 60 // 120),
        }
    )
    try:
        with urllib.request.urlopen(
            get_settings().prometheus_url.rstrip("/") + "/api/v1/query_range?" + query, timeout=3
        ) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Oversized metrics response")
        body = json.loads(raw)
        if body.get("status") != "success" or body["data"]["resultType"] != "matrix":
            raise ValueError("Invalid metrics response")
        result = body["data"]["result"]
        points = [[float(t), float(v)] for t, v in result[0]["values"]] if result else []
        import math

        points = [point for point in points if all(math.isfinite(value) for value in point)]
        return {"source": "prometheus", "points": points}
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise HTTPException(503, "Prometheus unavailable; no synthetic fallback used") from error


@router.get("/model")
def model_health(user: User) -> dict[str, Any]:
    url = get_settings().ops_detector_url
    if not url:
        return {
            "status": "not_configured",
            "metadata": None,
            "drift": None,
            "evaluation": "No independent live labeled evaluation configured",
        }
    try:
        values = []
        for path in ("/api/v1/model", "/api/v1/drift"):
            with urllib.request.urlopen(url.rstrip("/") + path, timeout=2) as response:
                raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ValueError("Oversized detector response")
            values.append(json.loads(raw))
        return {
            "status": "connected",
            "metadata": values[0],
            "drift": values[1],
            "evaluation": "Uncalibrated scores; no live false-positive claim",
        }
    except (OSError, ValueError) as error:
        raise HTTPException(503, "Detector unavailable") from error


@router.get("/resources/{resource_id}/logs")
def pod_logs(resource_id: str, db: Db, user: User, mode: Mode = "real") -> dict[str, Any]:
    """Bounded Loki query for one authorized pod; never a general LogQL proxy."""
    check_mode(mode)
    row = resource(db, resource_id, mode, "Pod")
    if mode == "demo":
        return {
            "source": "synthetic",
            "lines": [{"at": str(time.time_ns()), "text": "Synthetic pod log: readiness check"}],
        }
    url = get_settings().ops_loki_url
    if not url:
        return {"source": "not_configured", "lines": []}
    # Namespace/pod values are JSON-escaped literals, never interpolated LogQL syntax.
    query = (
        '{service_name=~".+"} | k8s_namespace_name='
        + json.dumps(row.namespace)
        + " | k8s_pod_name="
        + json.dumps(row.name)
    )
    params = urllib.parse.urlencode(
        {"query": query, "start": time.time_ns() - 900_000_000_000, "limit": 100}
    )
    try:
        with urllib.request.urlopen(
            url.rstrip("/") + "/loki/api/v1/query_range?" + params, timeout=3
        ) as response:
            raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            raise ValueError("Oversized log response")
        body = json.loads(raw)
        if body.get("status") != "success":
            raise ValueError("Loki query failed")
        lines = [
            {"at": str(at), "text": str(line)[:4096]}
            for stream in body["data"]["result"]
            for at, line in stream.get("values", [])
        ]
        return {"source": "loki", "lines": sorted(lines, key=lambda x: x["at"], reverse=True)[:100]}
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise HTTPException(503, "Loki unavailable; no synthetic fallback used") from error


@router.get("/stream")
async def stream(
    request: Request, user: User, mode: Mode = "real", after: int = Query(default=0, ge=0)
) -> StreamingResponse:
    check_mode(mode)

    async def updates() -> Any:
        cursor = after
        # Bounded lifetime; reconnect with Last-Event-ID, no DB connection held while waiting.
        with_header = request.headers.get("Last-Event-ID", "")
        if with_header.isdigit():
            cursor = max(cursor, int(with_header))
        for _ in range(20):
            if await request.is_disconnected():
                return

            def read(last_id: int = cursor) -> list[tuple[int, str]]:
                with SessionLocal() as db:
                    return [
                        (row.id, row.verb)
                        for row in db.scalars(
                            select(OperationsAudit)
                            .where(OperationsAudit.mode == mode, OperationsAudit.id > last_id)
                            .order_by(OperationsAudit.id)
                            .limit(100)
                        )
                    ]

            rows = await asyncio.to_thread(read)
            if rows:
                cursor = rows[-1][0]
                detail = json.dumps({"changed": len(rows), "verb": rows[-1][1]})
                yield f"id: {cursor}\nevent: update\ndata: {detail}\n\n"
            else:
                yield ": heartbeat\n\n"
            await asyncio.sleep(3)

    return StreamingResponse(
        updates(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.post("/internal/snapshots", dependencies=[Depends(bridge)])
def ingest(payload: SnapshotBatch, db: Db) -> dict[str, int]:
    check_mode(payload.mode)
    now = datetime.now(UTC)
    allowed = get_settings().ops_namespaces
    if len(json.dumps(payload.model_dump(mode="json"))) > 1_000_000:
        raise HTTPException(413, "Snapshot batch too large")
    ids_by_scope: dict[str, list[str]] = {}
    for item in payload.rows:
        if item.namespace and item.namespace not in allowed:
            raise HTTPException(403, "Bridge namespace outside configured scope")
        if not item.namespace and item.kind != "Node":
            raise HTTPException(422, "Only Node records are cluster-scoped")
        if (
            item.collected_at > now + timedelta(seconds=10)
            or (now - item.collected_at).total_seconds() > 120
        ):
            raise HTTPException(422, "Collection timestamp is not current")
        identity = hashlib.sha256(
            f"{payload.mode}:{item.kind}:{item.namespace}:{item.name}".encode()
        ).hexdigest()
        ids_by_scope.setdefault(f"{item.kind}:{item.namespace}", []).append(identity)
        row = db.get(Snapshot, identity)
        if row is None:
            row = Snapshot(
                id=identity,
                mode=payload.mode,
                kind=item.kind,
                namespace=item.namespace,
                name=item.name,
                uid=item.uid,
                resource_version=item.resource_version,
                collected_at=item.collected_at,
                data=item.data,
            )
            db.add(row)
        elif utc(row.collected_at) <= item.collected_at:
            row.uid, row.resource_version, row.collected_at, row.data = (
                item.uid,
                item.resource_version,
                item.collected_at,
                item.data,
            )
    for scope in payload.replace_scopes:
        kind, _, namespace = scope.partition(":")
        if namespace not in allowed and not (kind == "Node" and namespace == ""):
            raise HTTPException(403, "Replacement scope outside allowlist")
        query = delete(Snapshot).where(
            Snapshot.mode == payload.mode, Snapshot.kind == kind, Snapshot.namespace == namespace
        )
        keep = ids_by_scope.get(scope, [])
        if keep:
            query = query.where(Snapshot.id.not_in(keep))
        db.execute(query)
    # One durable change cursor per collection, no raw token or object bodies in audit.
    db.add(
        OperationsAudit(
            actor="kubernetes-bridge",
            verb="snapshot.refresh",
            target="configured namespaces",
            outcome="collected",
            mode=payload.mode,
            correlation_id="bridge",
            detail={"records": len(payload.rows)},
        )
    )
    db.commit()
    return {"accepted": len(payload.rows)}


@router.get("/internal/commands", dependencies=[Depends(bridge)])
def pending_commands(db: Db) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    rows = list(
        db.scalars(
            select(Command)
            .where(Command.mode == "real", Command.state == "pending")
            .order_by(Command.created_at)
            .limit(20)
        )
    )
    output = []
    for row in rows:
        if utc(row.expires_at) <= now:
            row.state, row.result = "expired", "Command expired before bridge delivery"
        else:
            output.append({**command_output(row), "payload": row.payload})
    db.commit()
    return output


class Delivery(BaseModel):
    state: str = Field(pattern=r"^(delivered|failed)$")
    result: str = Field(max_length=512)


@router.post("/internal/commands/{command_id}", dependencies=[Depends(bridge)])
def delivered(command_id: str, payload: Delivery, db: Db) -> dict[str, str]:
    row = db.get(Command, command_id)
    if row is None or row.mode != "real":
        raise HTTPException(404, "Command not found")
    if row.state != "pending":
        return {"state": row.state}
    row.state, row.result = payload.state, payload.result
    db.add(
        OperationsAudit(
            actor="kubernetes-bridge",
            verb="command.delivery",
            target=row.target,
            outcome=payload.state,
            mode="real",
            correlation_id=command_id,
            detail={"command_id": row.id, "result": payload.result},
        )
    )
    db.commit()
    return {"state": row.state}
