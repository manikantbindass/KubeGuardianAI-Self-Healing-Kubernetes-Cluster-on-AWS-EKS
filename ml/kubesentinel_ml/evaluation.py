"""Held-out measurements, labels/provenance visible; latency is measured, not deterministic."""

import csv
import json
import platform
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from kubesentinel_ml.dataset import split_windows
from kubesentinel_ml.features import Window
from kubesentinel_ml.model import Bundle
from kubesentinel_ml.rules import rule_score


def evaluate(
    bundle: Bundle, rows: list[Window], output: Path, plots: bool = True
) -> dict[str, Any]:
    from sklearn.metrics import precision_recall_curve

    test = [w for w in split_windows(rows, bundle.window_seconds)["test"] if w.label is not None]
    if not test or not any(w.label for w in test) or all(w.label for w in test):
        raise ValueError("Evaluation needs held-out positive and negative labels")
    output.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "model_version": bundle.model_version,
        "provenance": bundle.metadata["provenance"],
        "dataset_sha256": bundle.metadata["dataset_sha256"],
        "scope": "held-out windows; synthetic fixture results do not establish real-world accuracy",
        "score_kind": "uncalibrated_anomaly_score",
        "test_windows": len(test),
        "runtime": {
            "python": platform.python_version(),
            "system": platform.system(),
            "machine": platform.machine(),
            "timing": "serial warm-process; per-window",
        },
        "detectors": {},
    }
    predictions: list[dict[str, Any]] = []
    for name in ("rules", "robust_statistics", "isolation_forest"):
        times, results = [], []
        for window in test:
            start = time.perf_counter_ns()
            score = rule_score(window) if name == "rules" else bundle.score(window, name)
            times.append((time.perf_counter_ns() - start) / 1e6)
            results.append(score)
            predictions.append(
                {
                    "detector": name,
                    "window_end": window.end.isoformat(),
                    "resource": window.resource,
                    "label": int(window.label is True),
                    "prediction": int(score.anomalous),
                    "score": score.score,
                    "threshold": score.threshold,
                    "quality": score.quality,
                }
            )
        labels = [w.label is True for w in test]
        tp = sum(y and s.anomalous for y, s in zip(labels, results, strict=True))
        fp = sum(not y and s.anomalous for y, s in zip(labels, results, strict=True))
        fn = sum(y and not s.anomalous for y, s in zip(labels, results, strict=True))
        tn = len(test) - tp - fp - fn
        delays: dict[str, list[float]] = defaultdict(list)
        incident_ids = {i for w in test for i in w.incident_ids}
        detected: set[str] = set()
        for window, score in zip(test, results, strict=True):
            if window.label and score.anomalous:
                detected.update(window.incident_ids)
                for incident in window.incident_ids:
                    if incident in window.incident_starts:
                        delays[incident].append(
                            (window.end - window.incident_starts[incident]).total_seconds()
                        )
        first = [min(value) for value in delays.values()]
        precision, recall, _ = precision_recall_curve(labels, [s.score for s in results])
        report["detectors"][name] = {
            "precision": tp / max(1, tp + fp),
            "recall": tp / max(1, tp + fn),
            "f1": 2 * tp / max(1, 2 * tp + fp + fn),
            "false_positive_rate": fp / max(1, fp + tn),
            "confusion_matrix": [[tn, fp], [fn, tp]],
            "incident_count": len(incident_ids),
            "detected_incidents": len(detected),
            "missed_incidents": sorted(incident_ids - detected),
            "delay_missing_incidents": sorted(detected - delays.keys()),
            "mean_detection_delay_seconds": mean(first) if first else None,
            "delay_definition": "first positive window END minus fault start; excludes misses",
            "inference_latency_ms": {
                "p50": sorted(times)[len(times) // 2],
                "p95": sorted(times)[int(len(times) * 0.95)],
            },
            "threshold": results[0].threshold,
            "insufficient_data_windows": sum(s.quality != "ok" for s in results),
            "extreme_shift_window_rate": sum(bool(s.drift) for s in results) / len(results),
        }
        with (output / f"{name}-precision-recall.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["precision", "recall"])
            writer.writerows(zip(precision, recall, strict=True))
        if plots:
            import matplotlib

            matplotlib.use("Agg")
            from matplotlib import pyplot as plt

            fig, axes = plt.subplots(1, 2, figsize=(9, 3.5))
            axes[0].imshow([[tn, fp], [fn, tp]], cmap="Blues")
            for (y, x), value in {(0, 0): tn, (0, 1): fp, (1, 0): fn, (1, 1): tp}.items():
                axes[0].text(
                    x,
                    y,
                    str(value),
                    ha="center",
                    va="center",
                    color="white" if value > max(tn, fp, fn, tp) / 2 else "black",
                )
            axes[0].set(
                xticks=[0, 1],
                yticks=[0, 1],
                xlabel="Predicted",
                ylabel="Actual",
                title="Held-out confusion matrix",
            )
            axes[1].step(recall, precision, where="post")
            axes[1].set(
                xlabel="Recall",
                ylabel="Precision",
                xlim=(0, 1.02),
                ylim=(0, 1.02),
                title="Precision–recall (uncalibrated)",
            )
            fig.suptitle(f"{name} · {bundle.metadata['provenance']} telemetry")
            fig.tight_layout()
            fig.savefig(output / f"{name}.png", dpi=130)
            plt.close(fig)
    with (output / "predictions.csv").open("w", newline="", encoding="utf-8") as f:
        dict_writer = csv.DictWriter(f, fieldnames=list(predictions[0]))
        dict_writer.writeheader()
        dict_writer.writerows(predictions)
    (output / "evaluation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
