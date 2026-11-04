"""Bounded JSONL IO, deterministic fault fixture and purged temporal partitions."""

import hashlib
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from kubesentinel_ml.features import Window
from kubesentinel_ml.schema import Metrics, Observation


def read_dataset(path: Path) -> tuple[list[Observation], str]:
    if path.stat().st_size > 64_000_000:
        raise ValueError("Dataset exceeds 64 MB; shard outside Git")
    raw = path.read_bytes()
    rows = [Observation.model_validate_json(line) for line in raw.splitlines() if line.strip()]
    if not rows or len(rows) > 100_000:
        raise ValueError("Expected 1..100000 observations")
    if len({(r.dataset_id, r.provenance) for r in rows}) != 1:
        raise ValueError("Train separately per dataset/provenance; do not mix real and synthetic")
    return rows, hashlib.sha256(raw).hexdigest()


def synthetic(seed: int = 42, minutes: int = 900) -> list[Observation]:
    if not 300 <= minutes <= 10_000:
        raise ValueError("Synthetic fixture supports 300..10000 minutes")
    rng = random.Random(seed)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    rows = []
    for minute in range(minutes):
        fault = minute % 90 in range(50, 60)
        kind = (minute // 90) % 4
        incident = f"fault-{minute // 90}" if fault else None
        for second in (5, 35):
            values = {
                "cpu_ratio": max(0.01, rng.gauss(0.3, 0.04)),
                "memory_ratio": max(0.01, rng.gauss(0.45, 0.03)),
                "restarts": 0.0,
                "error_ratio": rng.uniform(0, 0.01),
                "latency_p95_ms": rng.uniform(75, 125),
                "pending_seconds": 0.0,
                "availability_ratio": 1.0,
                "deployment_changes": float(minute % 180 == 0),
                "node_pressure_ratio": 0.0,
                "saturation_ratio": rng.uniform(0.2, 0.4),
                "log_errors": float(rng.randrange(2)),
                "warning_events": 0.0,
            }
            if fault:
                values["warning_events"] = 2.0
                values["log_errors"] = 12.0
                if kind == 0:
                    values.update(cpu_ratio=0.99, saturation_ratio=0.97, latency_p95_ms=800.0)
                elif kind == 1:
                    values.update(memory_ratio=0.98, restarts=2.0, availability_ratio=0.5)
                elif kind == 2:
                    values.update(error_ratio=0.35, latency_p95_ms=1200.0)
                else:
                    values.update(
                        pending_seconds=240.0, node_pressure_ratio=1.0, availability_ratio=0.0
                    )
            # Missing measurements are explicit nulls, not manufactured healthy zeros.
            if rng.random() < 0.025:
                values["cpu_ratio"] = None  # type: ignore[assignment]
            rows.append(
                Observation(
                    id=f"synthetic-{seed}-{minute}-{second}",
                    timestamp=start + timedelta(minutes=minute, seconds=second),
                    dataset_id=f"synthetic-v1-seed-{seed}",
                    provenance="synthetic",
                    origin="synthetic",
                    resource="demo-workload",
                    metrics=Metrics(**values),
                    label=fault,
                    incident_id=incident,
                    fault_started_at=start + timedelta(minutes=minute // 90 * 90 + 50)
                    if fault
                    else None,
                )
            )
    return rows


def split_windows(rows: list[Window], seconds: int) -> dict[str, list[Window]]:
    timestamps = sorted({w.start for w in rows})
    if len(timestamps) < 100:
        raise ValueError("Need at least 100 distinct windows for temporal evaluation")
    first, second = timestamps[int(len(timestamps) * 0.6)], timestamps[int(len(timestamps) * 0.8)]
    gap = timedelta(seconds=seconds * 3)
    parts = {
        "train": [w for w in rows if w.end <= first],
        "validation": [w for w in rows if first + gap <= w.start and w.end <= second],
        "test": [w for w in rows if w.start >= second + gap],
    }
    ids = {key: {i for w in value for i in w.incident_ids} for key, value in parts.items()}
    shared = (
        (ids["train"] & ids["validation"])
        | (ids["train"] & ids["test"])
        | (ids["validation"] & ids["test"])
    )
    parts = {
        key: [w for w in value if not shared.intersection(w.incident_ids)]
        for key, value in parts.items()
    }
    if any(len(value) < 10 for value in parts.values()):
        raise ValueError("Insufficient independent windows after temporal/incident purging")
    return parts
