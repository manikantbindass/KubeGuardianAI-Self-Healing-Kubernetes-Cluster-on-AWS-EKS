# Phase 05 validation record

Date: 2026-11-03, Asia/Kolkata. Scope: reproducible advisory anomaly detection; no AWS deployment or remediation.

## Local evidence

- `uv lock` and `uv sync --frozen --extra ml`: exact NumPy 2.5.4, scikit-learn 1.9.1 and Matplotlib 3.11.2 resolved/installed on Python 3.12.4, Windows AMD64.
- `python scripts/ml.py generate`: 1800 synthetic observations, 900 UTC windows, seed 42. Data SHA-256 is recorded in [metadata](../../ml/models/synthetic-v1-metadata.json).
- `python scripts/ml.py train` and `python scripts/ml.py evaluate --output .cache/ml/repeated`: completed; prediction CSV hashes match across repeated evaluation. Unit tests separately retrain and compare fitted model arrays/thresholds and alter held-out features to check leakage.
- `python -m pytest -q -m "not postgres"`: 35 passed, one PostgreSQL test deselected locally. Includes partial-label and missing fault-start accounting checks.
- Ruff lint/format passed (98 Python files); strict mypy passed (43 source files). Markdown lint, all nine Mermaid diagrams, local file links, original LICENSE, Git ancestry and Terraform formatting passed.
- An isolated base-only locked install, without sklearn/NumPy/Matplotlib, passed mypy and 31 tests; four ML tests skipped explicitly and the PostgreSQL test was deselected. Training extras remain optional.
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

Local Docker daemon is unavailable (`dockerDesktopWindowsEngine` pipe missing), so local container/PostgreSQL/cluster tests cannot run here. For source commit `92326af`, [ML CI run 41562507769](https://github.com/manikantbindass/KubeSentinel-AI/actions/runs/41562507769) passed Windows/Linux type checking, tests, training/repeated evaluation and Linux detector image/Compose startup with real HTTP trained/fallback load tests. Downloaded Windows/Linux artifacts matched the local reference's 531 detector/label/prediction rows with zero differences. [Foundation run 41562507973](https://github.com/manikantbindass/KubeSentinel-AI/actions/runs/41562507973) passed Windows/Linux API checks, frontend lint/types/tests/build, PostgreSQL migration round-trip and ordinary Compose startup/outage/recovery checks. [Terraform static checks](https://github.com/manikantbindass/KubeSentinel-AI/actions/runs/41562507703) passed without cloud provisioning.

The Linux container load measured 40 requests at concurrency four for each mode: [trained report](phase-05/http-container-trained.json), p95 14.46 ms; [fallback report](phase-05/http-container-fallback.json), p95 10.31 ms. These short-run measurements are hardware/load dependent, not throughput guarantees.

Initial base-install API type checks exposed absent optional training-library imports; the final configuration permits those optional imports, while ML CI separately checks with extras installed. The inherited monitoring test's empty DELETE-response parsing bug is fixed. Local Kubernetes and full monitoring checks are tracked separately below; they are not replaced by the synthetic ML benchmark.

All **11 checks passed for implementation source commit `92326af`**. In addition to the checks above, [kind run 41562507900](https://github.com/manikantbindass/KubeSentinel-AI/actions/runs/41562507900) passed deployment/probe/scaling/RBAC/network/schema checks and advisory image scanning. [Monitoring run 41562507805](https://github.com/manikantbindass/KubeSentinel-AI/actions/runs/41562507805) passed real metrics/logs/events, controlled OOM, silence/incident resolution, Grafana capture and outage/recovery acceptance. [Actual captures](../screenshots/observability/README.md) from the first successful run are retained with their exact source provenance. Image scan completion does not mean zero vulnerabilities.

The final evidence/documentation update also removes obsolete dashboard footer wording; frontend lint/type checking and all 10 component/client/proxy tests passed locally after that wording change. Final evidence updates preserve the tested ML/API implementation and hashes. The PR may trigger a fresh CI run for those documentation/text-only changes; the source-commit evidence above is the completed verification record.

No real training dataset, independent labeled real-world evaluation, live AWS plan/deployment, production identity controls or automated recovery is claimed. Existing image-security findings from [Phase 02](phase-02-validation.md) remain relevant. Do not promote this development stack to production on synthetic F1 alone.
