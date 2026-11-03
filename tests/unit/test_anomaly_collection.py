from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from kubesentinel_ml import collection
from kubesentinel_ml.features import windows


def test_redacted_collection_preserves_missing_and_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)

    def source(base: str, path: str, params: dict[str, str]) -> dict[str, Any]:
        if "query_range" in path and "loki" not in path:
            if params["query"] == collection.QUERIES["memory_ratio"]:
                raise OSError("metrics source unavailable")
            return {"data": {"result": [{"values": [[start.timestamp() + 5, "0.2"]]}]}}
        return {"data": {"result": [{"values": [[start.timestamp() + 30, "2"]]}]}}

    monkeypatch.setattr(collection, "get_json", source)
    rows, metadata = collection.collect(
        "http://prometheus", "http://loki", start, start + timedelta(minutes=2), "real-test-fixture"
    )
    assert all(r.provenance == "real" and r.label is None for r in rows)
    assert metadata["unavailable_metrics"] == ["memory_ratio"]
    features = windows(rows)
    assert features[0].values["memory_ratio"] is None
    assert features[0].values["log_errors"] == 2
    assert all("message" not in r.model_dump_json() for r in rows)


def test_collection_outage_never_substitutes_synthetic(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(*args: object) -> dict[str, Any]:
        raise OSError("down")

    monkeypatch.setattr(collection, "get_json", unavailable)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="No real telemetry"):
        collection.collect(
            "http://prometheus", "http://loki", start, start + timedelta(minutes=2), "real-outage"
        )
