"""Explainable fixed baseline; scores are severities, never calibrated probabilities."""

from pydantic import BaseModel

from kubesentinel_ml.features import Window


class Explanation(BaseModel):
    feature: str
    value: float
    reference: float
    detail: str


class Score(BaseModel):
    detector: str
    score: float
    threshold: float
    anomalous: bool
    severity: str
    score_kind: str = "uncalibrated_anomaly_score"
    explanations: list[Explanation]
    quality: str
    model_version: str | None = None
    drift: list[str] = []


RULES = (
    ("cpu_ratio", 0.9, "above"),
    ("memory_ratio", 0.9, "above"),
    ("restarts", 2.0, "above"),
    ("error_ratio", 0.05, "above"),
    ("latency_p95_ms", 500.0, "above"),
    ("pending_seconds", 120.0, "above"),
    ("availability_ratio", 0.9, "below"),
    ("node_pressure_ratio", 0.0, "above"),
    ("saturation_ratio", 0.9, "above"),
    ("warning_events", 2.0, "above"),
)


def rule_score(window: Window) -> Score:
    evidence = []
    for key, reference, direction in RULES:
        value = window.values[key]
        if value is not None and (value > reference if direction == "above" else value < reference):
            evidence.append(
                Explanation(
                    feature=key,
                    value=value,
                    reference=reference,
                    detail=f"Rule: {direction} {reference}",
                )
            )
    critical = any(e.feature in {"restarts", "availability_ratio"} for e in evidence)
    return Score(
        detector="rules",
        score=float(bool(evidence)),
        threshold=0.5,
        anomalous=bool(evidence),
        severity="critical" if critical else "warning" if evidence else "info",
        explanations=evidence,
        quality="ok" if window.coverage >= 0.75 else "insufficient_data",
    )
