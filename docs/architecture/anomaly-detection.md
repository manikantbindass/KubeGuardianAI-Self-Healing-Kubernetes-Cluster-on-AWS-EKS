# Phase 05 anomaly detection architecture

The [data-flow diagram](../diagrams/anomaly-detection.mmd) describes the advisory path. The detector has no Kubernetes credentials or remediation client. A separate operator-controlled exporter can read namespace-scoped Kubernetes events. Models cannot approve or execute actions.

## Data and features

An observation has a unique ID, UTC timestamp, dataset ID, real/synthetic provenance, origin, namespace/resource and allowlisted finite numeric metrics. Labels, incident lineage and fault starts are evaluation metadata, never features. Raw log messages, resource annotations and event text are not exported. Kubernetes reads require an explicit kubectl context.

Real collection aggregates namespace `kubesentinel`; these are not per-pod measurements. CPU/memory ratios use requests/limits; HTTP measurements describe the API; node pressure/saturation provide cluster context. Loki supplies ERROR log counts. Events are retained Warning UID snapshots, not a complete history. Cumulative event repeats are not counted as new events. Prometheus `increase` estimates restarts/generation changes over 30 seconds and handles counter resets; two-minute rates/histograms smooth HTTP/CPU. Saved queries make these semantics reviewable.

UTC windows are aligned, non-overlapping, half-open intervals: 60 seconds by default, configurable from 10–3600. Exact duplicate IDs are ignored, conflicting IDs fail. Measurements use means, pending duration uses maxima, interval counts use sums. Missing intervals remain explicit empty windows. Nulls are never forward-filled; training medians impute model inputs. CPU/memory/saturation are capped at 16 with clipping counts retained. Input schemas reject NaN/infinity and impossible values.

The 28 features comprise 12 base channels plus lag-1, prior-three-window mean/standard deviation and current-minus-lag changes for CPU, memory, error ratio and latency. History is isolated per dataset/provenance/namespace/resource. Coverage counts present base channels, not expected scrape completeness. Irregular sampling, clipping and sample counts are exposed; no interpolation claims uniform sampling. Coverage below 75% activates rules with `insufficient_data`. An empty interval is not evidence of health.

## Training boundaries

Chronological 60/20/20 partitions use distinct timestamps, with a three-window purge before validation/test. Rolling history cannot overlap fitted windows. Incident IDs spanning retained partitions are removed from all of them. No shuffling, test-fit normalization, test threshold tuning or random cross-validation. Known positive training windows are excluded from the baseline fit; unknown training labels are explicitly assumed baseline, a contamination risk.

Training fits medians/MAD scales with declared floors and seeded, single-threaded Isolation Forest. Validation chooses the best F1 threshold subject to FPR ≤10%; both validation classes are required. This tuning constraint is not a test-set guarantee. Hyperparameters, feature order/version, data/code hashes, software versions, split time ranges/counts and incident IDs are saved. Baseline rule thresholds stay fixed.

Forests export tree arrays to JSON; runtime isolation-path scores are tested against scikit-learn. No pickle/joblib loading. Size, graph topology, finite values, dimensions, feature contract and checksum are checked. SHA-256 detects corruption, not malicious replacement: artifact access controls and approval still matter. Runtime does not require sklearn/numpy. Model replacement/rollback requires a process restart.

Held-out evaluation reports window precision/recall/F1/FPR, confusion matrices, per-incident misses, first-detection delay and measured warm-process latency. Delay is first positive window end minus labeled fault start; misses are listed separately. Precision-recall curves rank uncalibrated scores. Synthetic and real results remain separate. The fixture favors rules; it establishes neither generalization nor ML superiority.

## Interfaces and failures

`POST /api/v1/score` accepts at most 2000 observations and emits at most 256 completed windows. `score_from` restricts output while preserving input history. Select `rules` (default), `robust_statistics` or `isolation_forest`. Outputs include score/threshold, severity, quality and evidence. Robust deviations describe unusual features, not causal attribution or a faithful forest decomposition. Scores are not probabilities.

The service limits bodies to 1 MiB, queued requests to 16 and active workers to two. Saturation returns 429/Retry-After; deadlines return 504. Already-started thread work retains capacity until it actually ends. Fixed data/tree bounds constrain remaining work. Invalid/missing models activate rules; `/ready` reports usable `rules_fallback`. `/health`, `/api/v1/model` and `/api/v1/drift` expose liveness, lineage and shift counters. Unexpected failures are sanitized; payloads/tokens are not logged.

The polling CLI retains five minutes of context, emits only the last completed minute and waits 60 seconds between polls. Source timeouts are five seconds with four-MB response caps. Missing telemetry stays missing; all-source outage fails without synthetic substitution. Absent channels can block training until sufficient telemetry exists. Collection is an operator CLI, not a public URL-fetch endpoint.

Publishing is disabled by default and requires separate detector and backend credentials. Synthetic inputs/models cannot publish live ML incidents. The backend accepts only real, completed anomalous windows in `kubesentinel`; resource/window/detector/model identify a replay-safe incident. Bounded explanations persist in `anomaly_evidence`. Delivery is at-least-once with caller retry: timeouts may follow successful delivery. Evidence follows incident creation; retries repair an interrupted evidence write. Incidents remain advisory/open pending later correlation/lifecycle work.

Deployment assumes trusted local development. Loopback publication and optional API tokens do not replace production OIDC/RBAC/TLS. Robust deviation >12 and clipping indicate possible distribution shift, not proven concept drift. Drift counters reset on process restart. No automatic retraining or promotion occurs.

## Technology decisions

Rules give a transparent, dependency-light fallback. MAD statistics avoid Gaussian assumptions; fixed floors handle constant columns. Isolation Forest supplies a reproducible unsupervised comparison with modest compute. Robust covariance, change-point detection or seasonal forecasting may suit later labeled workloads. LSTMs/autoencoders are deferred until independent real data and measured baseline improvement justify their complexity. PostgreSQL remains the incident/evidence record; JSONL is an offline export, not a production feature store.

References: [Isolation Forest](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html), [persistence security](https://scikit-learn.org/stable/model_persistence.html), [precision-recall API](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.precision_recall_curve.html).
