"""Viewer-scoped incident intelligence and operator feedback; no recovery imports."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from redis.exceptions import RedisError

from kubesentinel_api.config import get_settings
from kubesentinel_api.intelligence import BOOKS, IntelligenceOutput, Runbook, analyze, clean
from kubesentinel_api.models import Incident
from kubesentinel_api.operations.auth import Cache, User, authorize, mutation_limit
from kubesentinel_api.operations.commands import audit
from kubesentinel_api.operations.models import IncidentReview
from kubesentinel_api.operations.router import view
from kubesentinel_api.operations.schemas import Mode
from kubesentinel_api.telemetry import Db

router = APIRouter(prefix="/api/v1/ops/intelligence", tags=["read-only intelligence"])


@router.get("", response_model=IntelligenceOutput)
def intelligence(
    db: Db,
    user: User,
    cache: Cache,
    mode: Mode = "real",
    namespace: str = "all",
    q: str = Query(default="", max_length=100),
) -> IntelligenceOutput:
    rate_key = "aiops:reads:" + hashlib.sha256(user.subject.encode()).hexdigest()
    try:
        count = cache.eval(
            "local n=redis.call('INCR',KEYS[1]); "
            "if n==1 then redis.call('EXPIRE',KEYS[1],60) end; return n",
            1,
            rate_key,
        )
        if int(count) > 30:
            raise HTTPException(429, "Intelligence request limit exceeded")
    except (RedisError, TypeError, ValueError) as error:
        raise HTTPException(503, "Intelligence admission limits unavailable") from error
    data = view(db, user, mode, namespace)
    result = analyze(
        data.incidents, [r.model_dump() for r in data.resources], data.anomaly_evidence, mode
    )
    if q:
        search = clean(q).casefold()
        result.explanations = [
            e for e in result.explanations if search in f"{e.resource} {e.summary}".casefold()
        ]
    if data.bridge.get("stale") or data.bridge.get("limited"):
        result.limitations.append(
            "Inventory is stale or truncated; associations may be incomplete."
        )
    return result


@router.get("/runbooks", response_model=list[Runbook])
def runbooks(user: User) -> list[Runbook]:
    return BOOKS


class Feedback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    incident_id: UUID
    verdict: Literal["supported", "unsupported", "insufficient-evidence"]
    note: str = Field(min_length=5, max_length=256)


@router.post("/feedback")
def feedback(
    payload: Feedback, db: Db, user: User, cache: Cache, request: Request
) -> dict[str, str]:
    authorize(user, "operator")
    mutation_limit(user, cache)
    identifier = str(payload.incident_id)
    incident = db.get(Incident, identifier)
    if incident is None or incident.namespace not in get_settings().ops_namespaces:
        raise HTTPException(404, "Scoped incident not found")
    note = json.dumps(
        {"engine": "rules-v1", "verdict": payload.verdict, "note": clean(payload.note, 256)}
    )
    row = db.get(IncidentReview, identifier)
    if row is None:
        row = IncidentReview(incident_id=identifier, actor=user.subject, note=note)
        db.add(row)
    row.actor, row.note, row.at = user.subject, note, datetime.now(UTC)
    audit(
        db,
        user,
        "intelligence.feedback",
        identifier,
        "recorded",
        "real",
        request.state.correlation_id,
        {"verdict": payload.verdict, "engine": "rules-v1", "note": clean(payload.note, 256)},
    )
    db.commit()
    return {"status": "recorded", "incident_id": identifier}
