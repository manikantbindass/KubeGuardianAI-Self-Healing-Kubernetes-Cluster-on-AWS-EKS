"""Non-overlapping UTC windows; past-only history, no forward fill or label features."""

from collections import defaultdict
from datetime import UTC, datetime
from statistics import mean, pstdev

from pydantic import BaseModel, ConfigDict

from kubesentinel_ml import FEATURE_VERSION
from kubesentinel_ml.schema import Metrics, Observation

BASE = tuple(Metrics.model_fields)
TREND = ("cpu_ratio", "memory_ratio", "error_ratio", "latency_p95_ms")
FEATURES = BASE + tuple(f"{key}_{op}" for key in TREND for op in ("lag1", "mean3", "std3", "delta"))
SUMS = {"restarts", "deployment_changes", "log_errors", "warning_events"}
# Preserve extreme signals at bounded magnitude; report clipping rather than discard anomalies.
CAPS = {"cpu_ratio": 16.0, "memory_ratio": 16.0, "saturation_ratio": 16.0}


class Window(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    feature_version: str = FEATURE_VERSION
    dataset_id: str
    provenance: str
    namespace: str
    resource: str
    start: datetime
    end: datetime
    values: dict[str, float | None]
    coverage: float
    samples: int
    clipped: int
    irregular: bool
    label: bool | None
    incident_ids: list[str]
    fault_started_at: datetime | None


def windows(
    observations: list[Observation], seconds: int = 60, max_windows: int = 100_000
) -> list[Window]:
    if not 10 <= seconds <= 3600 or len(observations) > 100_000:
        raise ValueError("Window size must be 10..3600 seconds; at most 100000 observations")
    seen: dict[str, Observation] = {}
    groups: dict[tuple[str, str, str, str], list[Observation]] = defaultdict(list)
    for row in observations:
        if row.id in seen:
            if row != seen[row.id]:
                raise ValueError("Conflicting duplicate observation ID")
            continue
        seen[row.id] = row
        groups[(row.dataset_id, row.provenance, row.namespace, row.resource)].append(row)
    output: list[Window] = []
    for (dataset, provenance, namespace, resource), rows in sorted(groups.items()):
        buckets: dict[int, list[Observation]] = defaultdict(list)
        for row in rows:
            buckets[int(row.timestamp.timestamp()) // seconds * seconds].append(row)
        history: list[Window] = []
        for stamp in range(min(buckets), max(buckets) + seconds, seconds):
            if len(output) >= max_windows:
                raise ValueError("Too many feature windows")
            bucket = sorted(buckets.get(stamp, []), key=lambda row: (row.timestamp, row.id))
            values: dict[str, float | None] = {}
            clipped = 0
            for key in BASE:
                numbers = []
                for row in bucket:
                    number = getattr(row.metrics, key)
                    if number is not None:
                        cap = CAPS.get(key, float(number))
                        clipped += int(number > cap)
                        numbers.append(min(float(number), cap))
                values[key] = (
                    (
                        sum(numbers)
                        if key in SUMS
                        else max(numbers)
                        if key == "pending_seconds"
                        else mean(numbers)
                    )
                    if numbers
                    else None
                )
            for key in TREND:
                past = [w.values[key] for w in history[-3:]]
                valid = [v for v in past if v is not None]
                lag = history[-1].values[key] if history else None
                current = values[key]
                values.update(
                    {
                        f"{key}_lag1": lag,
                        f"{key}_mean3": mean(valid) if valid else None,
                        f"{key}_std3": pstdev(valid) if valid else None,
                        f"{key}_delta": current - lag
                        if current is not None and lag is not None
                        else None,
                    }
                )
            labels = [r.label for r in bucket if r.label is not None]
            faults = [r.fault_started_at for r in bucket if r.fault_started_at is not None]
            times = sorted({r.timestamp.timestamp() for r in bucket})
            window = Window(
                dataset_id=dataset,
                provenance=provenance,
                namespace=namespace,
                resource=resource,
                start=datetime.fromtimestamp(stamp, UTC),
                end=datetime.fromtimestamp(stamp + seconds, UTC),
                values=values,
                coverage=sum(values[k] is not None for k in BASE) / len(BASE),
                samples=len(bucket),
                clipped=clipped,
                irregular=any(b - a > seconds / 2 for a, b in zip(times, times[1:], strict=False)),
                label=any(labels) if labels else None,
                incident_ids=sorted({r.incident_id for r in bucket if r.incident_id}),
                fault_started_at=min(faults) if faults else None,
            )
            output.append(window)
            history.append(window)
    return sorted(output, key=lambda w: (w.start, w.dataset_id, w.namespace, w.resource))
