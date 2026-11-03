from datetime import timedelta

import pytest
from kubesentinel_ml.dataset import split_windows, synthetic
from kubesentinel_ml.features import FEATURES, windows
from kubesentinel_ml.schema import Observation
from pydantic import ValidationError


def test_duplicates_order_missing_and_causal_history() -> None:
    rows = synthetic(minutes=300)[:12]
    original = windows(rows)
    assert windows(list(reversed(rows)) + [rows[0]]) == original
    # A change in a later window must not alter any earlier feature.
    future = rows[-1].model_copy(deep=True)
    future.metrics.cpu_ratio = 999
    changed = windows(rows[:-1] + [future])
    assert changed[:-1] == original[:-1]
    assert changed[-1].clipped == 1
    assert original[0].values["cpu_ratio_lag1"] is None
    assert original[1].values["cpu_ratio_lag1"] == original[0].values["cpu_ratio"]
    assert set(original[0].values) == set(FEATURES)
    assert not any("label" in name or "incident" in name for name in FEATURES)
    sparse = windows(rows[:2] + rows[6:8])
    assert sparse[1].samples == 0 and sparse[1].coverage == 0
    assert sparse[2].values["cpu_ratio"] is None


def test_conflicting_duplicate_and_bounded_gap() -> None:
    rows = synthetic(minutes=300)[:2]
    duplicate = rows[0].model_copy(update={"resource": "different"})
    with pytest.raises(ValueError, match="Conflicting"):
        windows([rows[0], duplicate])
    far = rows[1].model_copy(update={"timestamp": rows[1].timestamp + timedelta(days=1)})
    with pytest.raises(ValueError, match="Too many"):
        windows([rows[0], far], max_windows=256)


@pytest.mark.parametrize(
    "field,value",
    [
        ("timestamp", "2026-01-01T00:00:00"),
        ("provenance", "real"),
        ("metrics", {"cpu_ratio": float("nan")}),
        ("metrics", {"error_ratio": 4}),
        ("metrics", {"raw_log": "secret"}),
    ],
)
def test_input_validation(field: str, value: object) -> None:
    payload = synthetic(minutes=300)[0].model_dump()
    payload[field] = value
    with pytest.raises(ValidationError):
        Observation.model_validate(payload)


def test_time_purge_and_incident_lineage_disjoint() -> None:
    rows = windows(synthetic())
    # Force an incident lineage to span train and validation; remove it from both.
    rows[500].incident_ids = ["shared-incident"]
    rows[600].incident_ids = ["shared-incident"]
    parts = split_windows(rows, 60)
    assert max(w.end for w in parts["train"]) + timedelta(minutes=3) <= min(
        w.start for w in parts["validation"]
    )
    assert max(w.end for w in parts["validation"]) + timedelta(minutes=3) <= min(
        w.start for w in parts["test"]
    )
    for partition in parts.values():
        assert all("shared-incident" not in w.incident_ids for w in partition)
