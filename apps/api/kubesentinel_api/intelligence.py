"""Bounded, read-only evidence correlation. No execution or provider network access."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class Runbook(BaseModel):
    id: str
    title: str
    path: str
    reasons: list[str]
    steps: list[str]


BOOKS = [
    Runbook(
        id="memory",
        title="Memory pressure investigation",
        path="docs/runbooks/aiops-investigation.md#memory-pressure",
        reasons=["oomkilled", "memorypressure", "resourcepressure"],
        steps=[
            "Inspect container termination reasons and memory limits.",
            "Compare memory usage with limits over the incident window.",
        ],
    ),
    Runbook(
        id="startup",
        title="Startup and availability investigation",
        path="docs/runbooks/aiops-investigation.md#startup-and-availability",
        reasons=[
            "crashloopbackoff",
            "readinessfailure",
            "readinessprobefailure",
            "excessiverestarts",
            "replicashortage",
            "stuckrollout",
        ],
        steps=[
            "Inspect probe failures, recent events and ready replica counts.",
            "Compare deployment changes with the first observed failure.",
        ],
    ),
    Runbook(
        id="latency",
        title="Latency investigation",
        path="docs/runbooks/aiops-investigation.md#latency",
        reasons=["latencydegradation", "httperrorrate", "latencyanomaly"],
        steps=[
            "Compare latency and error-rate windows with baseline traffic.",
            "Inspect dependency health and recent deployment changes.",
        ],
    ),
    Runbook(
        id="general",
        title="Evidence collection",
        path="docs/runbooks/aiops-investigation.md#evidence-collection",
        reasons=[],
        steps=[
            "Confirm the workload identity and telemetry freshness.",
            "Collect missing evidence before proposing recovery.",
        ],
    ),
]


def clean(value: Any, maximum: int = 128) -> str:
    text = str(value)[:2048]
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[REDACTED_EMAIL]", text)
    text = re.sub(
        r"(?i)(bearer\s+\S+|(?:password|secret|token|api[_-]?key)\s*[:=]\s*\S+)",
        "[REDACTED_SECRET]",
        text,
    )
    text = re.sub(r"-----BEGIN[\s\S]*", "[REDACTED_KEY]", text)
    return re.sub(r"[\x00-\x1f<>]", "", text)[:maximum]


def stamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(UTC) if parsed.tzinfo else None
    except ValueError:
        return None


def key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())[:128]


class Hypothesis(BaseModel):
    id: str
    label: str
    rank_score: int
    evidence: list[str]
    uncertainty: str = "Heuristic hypothesis; not an established cause or calibrated confidence."


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hypothesis_ids: list[str] = Field(max_length=8)


class Assistant(Protocol):
    def select(self, hypotheses: tuple[Hypothesis, ...]) -> Selection: ...


class Explanation(BaseModel):
    incident_id: str
    namespace: str
    resource: str
    priority: int
    duplicate_ids: list[str]
    related_ids: list[str]
    historical_similar_ids: list[str]
    hypotheses: list[Hypothesis]
    runbooks: list[Runbook]
    summary: str
    evidence_ids: list[str]


class IntelligenceOutput(BaseModel):
    engine_version: str = "rules-v1"
    mode: Literal["real", "demo"]
    assistant: str = "local-deterministic"
    remote_requests: int = 0
    explanations: list[Explanation]
    limitations: list[str]
    channels: dict[str, str]


def analyze(
    incidents: list[dict[str, Any]],
    resources: list[dict[str, Any]],
    anomalies: list[dict[str, Any]],
    mode: Literal["real", "demo"] = "real",
    assistant: Assistant | None = None,
) -> IntelligenceOutput:
    if len(incidents) > 100 or len(resources) > 1000 or len(anomalies) > 100:
        raise ValueError("Intelligence input exceeds bounded read model")
    output = IntelligenceOutput(
        mode=mode,
        explanations=[],
        channels={
            "events": "scoped collected Kubernetes events",
            "metrics": "incident-linked anomaly records only",
            "logs": "not retrieved; no raw logs are sent to an assistant",
        },
        limitations=[
            "Only the latest 100 scoped incidents and 1000 snapshots are searched.",
            "Identity equality and a 15-minute window indicate association, not causality.",
            "Missing evidence and collection lag may hide related incidents.",
            "No learned ranking, live accuracy, multi-cluster identity or LLM claims.",
        ],
    )
    for incident in incidents:
        identifier = str(incident["id"])
        namespace, resource = str(incident["namespace"]), str(incident["resource"])
        observed = stamp(incident.get("first_seen"))
        reason = key(incident.get("reason", ""))
        duplicates, related, history = [], [], []
        for other in incidents:
            if other["id"] == identifier or other["namespace"] != namespace:
                continue
            other_at = stamp(other.get("first_seen"))
            if not observed or not other_at:
                continue
            difference = (observed - other_at).total_seconds()
            if other["resource"] == resource and abs(difference) <= 900:
                related.append(clean(other["id"]))
                if key(other.get("reason")) == reason:
                    duplicates.append(clean(other["id"]))
            elif difference > 900 and key(other.get("reason")) == reason:
                history.append(clean(other["id"]))
        evidence = ["incident:" + clean(identifier)]
        changes = []
        for row in resources:
            if row.get("kind") != "Event" or row.get("namespace") != namespace:
                continue
            data = row.get("data", {})
            at = stamp(data.get("timestamp"))
            if data.get("owner") != resource or not observed or not at:
                continue
            if abs((observed - at).total_seconds()) <= 900:
                citation = "event:" + clean(row["id"])
                evidence.append(citation)
                if 0 <= (observed - at).total_seconds() <= 900 and data.get("reason") in {
                    "ScalingReplicaSet",
                    "DeploymentUpdated",
                    "RolloutStarted",
                }:
                    changes.append(citation)
        evidence.extend(
            "anomaly:" + clean(identifier)
            for a in anomalies
            if str(a.get("incident_id")) == identifier
        )
        books = [b for b in BOOKS if reason in b.reasons] or [BOOKS[-1]]
        stable = hashlib.sha256(identifier.encode()).hexdigest()[:16]
        hypotheses = [
            Hypothesis(
                id=stable + ":symptom",
                label=books[0].title,
                rank_score=1 + min(len(evidence) - 1, 5),
                evidence=evidence,
            )
        ]
        if changes:
            hypotheses.append(
                Hypothesis(
                    id=stable + ":change",
                    label="Recent deployment change association",
                    rank_score=2,
                    evidence=changes,
                )
            )
        hypotheses.sort(key=lambda h: (-h.rank_score, h.id))
        if assistant:
            try:
                selected = Selection.model_validate(
                    assistant.select(tuple(h.model_copy(deep=True) for h in hypotheses))
                )
                if not set(selected.hypothesis_ids).issubset({h.id for h in hypotheses}):
                    raise ValueError("Unsupported hypothesis")
                # Preserve deterministic ranking; selectors cannot invent evidence or actions.
                output.assistant = "validated-selector; deterministic ranking retained"
            except Exception:
                output.assistant = "local-fallback; selector unavailable or invalid"
        output.explanations.append(
            Explanation(
                incident_id=clean(identifier),
                namespace=clean(namespace),
                resource=clean(resource),
                priority={"critical": 4, "warning": 3, "info": 1}.get(
                    str(incident.get("severity")), 2
                ),
                duplicate_ids=sorted(duplicates),
                related_ids=sorted(related),
                historical_similar_ids=sorted(history)[:10],
                hypotheses=hypotheses,
                runbooks=books,
                summary=f"{books[0].title}: {len(evidence)} evidence references; "
                f"{len(related)} related records. Cause unconfirmed.",
                evidence_ids=list(dict.fromkeys(evidence)),
            )
        )
    output.explanations.sort(key=lambda e: (-e.priority, e.incident_id))
    return output
