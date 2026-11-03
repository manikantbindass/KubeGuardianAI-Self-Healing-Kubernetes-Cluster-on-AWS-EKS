# Phase 05 validation record

Date: 2026-11-03, Asia/Kolkata. Scope: reproducible advisory anomaly detection; no AWS deployment or remediation.

## Local evidence

- `uv lock` and `uv sync --frozen --extra ml`: exact NumPy 2.5.4, scikit-learn 1.9.1 and Matplotlib 3.11.2 resolved/installed on Python 3.12.4, Windows AMD64.
- `python scripts/ml.py generate`: 1800 synthetic observations, 900 UTC windows, seed 42. Data SHA-256 is recorded in [metadata](../../ml/models/synthetic-v1-metadata.json).
- `python scripts/ml.py train` and `python scripts/ml.py evaluate --output .cache/ml/repeated`: completed; prediction CSV hashes match across repeated evaluation. Unit tests separately retrain and compare fitted model arrays/thresholds and alter held-out features to check leakage.
- `python -m pytest -q -m "not postgres"`: 35 passed, one PostgreSQL test deselected locally. Includes partial-label and missing fault-start accounting checks.
- Ruff lint/format and strict mypy passed during implementation. Final repository/Markdown/Mermaid checks are recorded after completion.
- Native server plus `python scripts/test_detector_http.py`: 40 HTTP requests, concurrency four, four synthetic windows/request, no failures. [Measured HTTP report](phase-05/http-load.json) records latency and process-local drift counts.
- All three confusion/precision-recall PNGs were rendered by Matplotlib and visually inspected. They display actual held-out counts, not mock panels.

## Synthetic reference evaluation

The held-out set has **177 windows: 157 negative, 20 positive, two incident episodes**. This small/simple generator favors the fixed rules; results are not real Kubernetes accuracy estimates.

| Detector | Precision | Recall | F1 | FPR | Detected incidents | Mean delay, detected only |
| --- | --- | --- | --- | --- | --- | --- |
| Rules | 1.000 | 1.000 | 1.000 | 0.000 | 2/2 | 60 s |
| Robust statistics | 0.875 | 0.350 | 0.500 | 0.0064 | 1/2 | 240 s |
| Isolation Forest | 0.667 | 0.900 | 0.766 | 0.0573 | 2/2 | 120 s |

Rules remain the default. See [evaluation JSON](phase-05/evaluation.json), [per-window predictions](phase-05/predictions.csv), [rule plot](phase-05/rules.png), [statistical plot](phase-05/robust_statistics.png), [forest plot](phase-05/isolation_forest.png) and [model card](../../ml/models/model-card.md). The JSON records measured inference latency, thresholds, misses and runtime. Reproducing quality/predictions does not mean identical wall-clock timing.

## Integration and known limits

Tests cover causal/lag features, gaps/duplicates/clipping/finite-value validation, incident-lineage purge, training repeatability, held-out leakage checks, forest/scikit-learn parity, tamper/topology rejection, deterministic fallback, publishing restrictions, authenticated replay-safe incident evidence, source outages, queue saturation/deadlines and live HTTP load. Contract fixtures marked `real` exist only inside isolated tests; they are not presented as collected telemetry or training data.

Local Docker daemon is unavailable (`dockerDesktopWindowsEngine` pipe missing), so local container/PostgreSQL/cluster tests cannot run here. On the first published implementation, [ML CI run 41562202951](https://github.com/manikantbindass/KubeSentinel-AI/actions/runs/41562202951) passed Windows/Linux reproducibility and Linux detector image/Compose startup, real HTTP trained/fallback load tests. PostgreSQL migration 0003 also passed in [foundation run 41562202850](https://github.com/manikantbindass/KubeSentinel-AI/actions/runs/41562202850). Initial base-install API type checks exposed absent optional training-library imports; the configuration now permits those optional imports, and ML CI separately type-checks with all extras installed. Final commit checks are recorded after completion. The inherited observability suite's empty DELETE-response parsing bug is fixed in this branch; full monitoring acceptance remains separately tracked.

No real training dataset, independent labeled real-world evaluation, live AWS plan/deployment, production identity controls or automated recovery is claimed. Existing image-security findings from [Phase 02](phase-02-validation.md) remain relevant. Do not promote this development stack to production on synthetic F1 alone.
