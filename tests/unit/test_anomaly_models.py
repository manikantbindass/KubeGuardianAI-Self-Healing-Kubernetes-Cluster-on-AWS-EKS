import json
from pathlib import Path

import pytest
from kubesentinel_ml.dataset import split_windows, synthetic
from kubesentinel_ml.evaluation import evaluate
from kubesentinel_ml.features import FEATURES, Window, windows
from kubesentinel_ml.model import Bundle, Tree
from kubesentinel_ml.training import train
from pydantic import ValidationError


@pytest.fixture(scope="module")
def trained() -> tuple[Bundle, list[Window]]:
    pytest.importorskip("sklearn")
    rows = windows(synthetic())
    return train(rows, "fixture-hash", trees=16), rows


def test_serialization_and_reference_sklearn_parity(
    trained: tuple[Bundle, list[Window]],
    tmp_path: Path,
) -> None:
    import numpy as np
    from sklearn.ensemble import IsolationForest

    bundle, rows = trained
    path = tmp_path / "model.json"
    bundle.save(path)
    loaded = Bundle.load(path)
    normal = [
        w for w in split_windows(rows, 60)["train"] if w.label is not True and w.coverage >= 0.75
    ]
    estimator = IsolationForest(
        n_estimators=16, max_samples=256, contamination="auto", random_state=42, n_jobs=1
    ).fit([bundle.vector(w) for w in normal])
    for window in rows[720:760:3]:
        expected = -estimator.score_samples(np.array([bundle.vector(window)]))[0]
        assert loaded.raw_scores(window)[1] == pytest.approx(expected, abs=1e-8)
        assert loaded.score(window) == bundle.score(window)
    body = json.loads(path.read_text())
    body["center"][0] += 1
    path.write_text(json.dumps(body))
    with pytest.raises(ValueError, match="checksum"):
        Bundle.load(path)
    with pytest.raises(ValidationError, match="topology"):
        Tree.model_validate(
            {"nodes": [{"feature": 0, "threshold": 0, "left": 0, "right": 0, "samples": 3}]}
        )


def test_training_and_evaluation_reproducible_without_test_leakage(
    trained: tuple[Bundle, list[Window]],
    tmp_path: Path,
) -> None:
    bundle, rows = trained
    repeated = train(rows, "fixture-hash", trees=16)
    assert bundle.model_dump() == repeated.model_dump()
    changed = [w.model_copy(deep=True) for w in rows]
    for row in split_windows(changed, 60)["test"]:
        row.values[FEATURES[0]] = 15
    altered = train(changed, "fixture-hash", trees=16)
    assert bundle.center == altered.center and bundle.scale == altered.scale
    assert bundle.forest == altered.forest
    assert bundle.forest_threshold == altered.forest_threshold
    assert bundle.statistical_threshold == altered.statistical_threshold
    report = evaluate(bundle, rows, tmp_path / "first", plots=False)
    repeated_report = evaluate(bundle, rows, tmp_path / "second", plots=False)
    assert (tmp_path / "first/predictions.csv").read_bytes() == (
        tmp_path / "second/predictions.csv"
    ).read_bytes()
    for detector in report["detectors"]:
        for field in (
            "precision",
            "recall",
            "f1",
            "false_positive_rate",
            "confusion_matrix",
            "mean_detection_delay_seconds",
        ):
            assert (
                report["detectors"][detector][field]
                == repeated_report["detectors"][detector][field]
            )
    assert report["provenance"] == "synthetic"
    assert report["detectors"]["isolation_forest"]["inference_latency_ms"]["p95"] < 1000


def test_quality_fallback_and_drift(trained: tuple[Bundle, list[Window]]) -> None:
    bundle, rows = trained
    sparse = rows[0].model_copy(deep=True)
    sparse.coverage = 0
    assert bundle.score(sparse).detector == "rules"
    assert bundle.score(sparse).quality == "insufficient_data"
    extreme = rows[400].model_copy(deep=True)
    extreme.values["cpu_ratio"] = 16
    assert "extreme_feature_shift" in bundle.score(extreme).drift
    extreme.feature_version = "invalid"
    with pytest.raises(ValueError, match="version"):
        bundle.score(extreme)
