"""Train-only normalization and validation-only threshold selection."""

import hashlib
import importlib.metadata
import platform
from pathlib import Path
from typing import Any

from kubesentinel_ml.dataset import split_windows
from kubesentinel_ml.features import FEATURES, Window
from kubesentinel_ml.model import Bundle, Tree


def choose_threshold(scores: list[float], labels: list[bool]) -> float:
    if not labels or not any(labels) or all(labels):
        raise ValueError("Threshold tuning requires validation positives and negatives")
    candidates = sorted(set(scores + [max(scores) + 1e-9]))
    ranked = []
    for threshold in candidates:
        tp = sum(y and s >= threshold for y, s in zip(labels, scores, strict=True))
        fp = sum(not y and s >= threshold for y, s in zip(labels, scores, strict=True))
        fn = sum(y and s < threshold for y, s in zip(labels, scores, strict=True))
        fpr = fp / labels.count(False)
        f1 = 2 * tp / max(1, 2 * tp + fp + fn)
        if fpr <= 0.1:
            ranked.append((f1, -fpr, threshold))
    return max(ranked)[2]


def train(
    rows: list[Window],
    dataset_sha: str,
    *,
    seed: int = 42,
    trees: int = 64,
    max_samples: int = 256,
    seconds: int = 60,
) -> Bundle:
    import numpy as np
    from sklearn.ensemble import IsolationForest

    if not 8 <= trees <= 256 or not 16 <= max_samples <= 4096:
        raise ValueError("trees must be 8..256; max_samples 16..4096")
    parts = split_windows(rows, seconds)
    normal = [w for w in parts["train"] if w.label is not True and w.coverage >= 0.75]
    if len(normal) < 30:
        raise ValueError("Need at least 30 usable baseline training windows")
    raw = np.array(
        [[np.nan if w.values[k] is None else w.values[k] for k in FEATURES] for w in normal],
        dtype=float,
    )
    # Empty columns indicate an unusable dataset, not permission to learn healthy zeros.
    if np.any(np.all(np.isnan(raw), axis=0)):
        raise ValueError("A training feature is entirely missing")
    center = np.nanmedian(raw, axis=0)
    floors = np.array(
        [
            5.0
            if "latency" in k
            else 1.0
            if any(token in k for token in ("restarts", "seconds", "changes", "errors", "events"))
            else 0.02
            for k in FEATURES
        ]
    )
    scale = np.maximum(np.nanmedian(np.abs(raw - center), axis=0) * 1.4826, floors)
    filled = np.where(np.isnan(raw), center, raw)
    estimator = IsolationForest(
        n_estimators=trees,
        max_samples=min(max_samples, len(normal)),
        contamination="auto",
        random_state=seed,
        n_jobs=1,
    ).fit(filled)
    forest = []
    for tree in estimator.estimators_:
        data = tree.tree_
        forest.append(
            Tree.model_validate(
                {
                    "nodes": [
                        {
                            "feature": int(data.feature[i]),
                            "threshold": float(data.threshold[i]),
                            "left": int(data.children_left[i]),
                            "right": int(data.children_right[i]),
                            "samples": int(data.n_node_samples[i]),
                        }
                        for i in range(data.node_count)
                    ]
                }
            )
        )
    summaries: dict[str, Any] = {}
    for name, partition in parts.items():
        summaries[name] = {
            "windows": len(partition),
            "start": min(w.start for w in partition).isoformat(),
            "end": max(w.end for w in partition).isoformat(),
            "labeled_positive": sum(w.label is True for w in partition),
            "labeled_negative": sum(w.label is False for w in partition),
            "incident_ids": sorted({i for w in partition for i in w.incident_ids}),
        }
    code = hashlib.sha256()
    for file in sorted(Path(__file__).parent.glob("*.py")):
        code.update(file.name.encode())
        code.update(file.read_bytes().replace(b"\r\n", b"\n"))
    bundle = Bundle(
        feature_order=list(FEATURES),
        window_seconds=seconds,
        center=center.tolist(),
        scale=scale.tolist(),
        forest=forest,
        max_samples=int(estimator.max_samples_),
        statistical_threshold=6.0,
        forest_threshold=0.65,
        metadata={
            "dataset_sha256": dataset_sha,
            "dataset_id": rows[0].dataset_id,
            "provenance": rows[0].provenance,
            "code_sha256": code.hexdigest(),
            "python": platform.python_version(),
            "packages": {p: importlib.metadata.version(p) for p in ("numpy", "scikit-learn")},
            "parameters": {
                "seed": seed,
                "trees": trees,
                "max_samples": max_samples,
                "validation_max_fpr": 0.1,
                "minimum_coverage": 0.75,
            },
            "splits": summaries,
            "training_baseline_windows": len(normal),
            "training_label_policy": "exclude known positives; unlabeled assumed baseline",
            "score_kind": "uncalibrated_anomaly_score",
            "calibration": "none; scores and severities are not incident probabilities",
        },
    )
    validation = [w for w in parts["validation"] if w.label is not None and w.coverage >= 0.75]
    pairs = [bundle.raw_scores(w) for w in validation]
    labels = [w.label is True for w in validation]
    bundle.statistical_threshold = choose_threshold([p[0] for p in pairs], labels)
    bundle.forest_threshold = choose_threshold([p[1] for p in pairs], labels)
    bundle.model_version = bundle.digest()
    return bundle
