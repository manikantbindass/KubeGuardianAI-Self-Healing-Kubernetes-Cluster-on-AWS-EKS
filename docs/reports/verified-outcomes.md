# Verified results and engineering outcome

Date: 4 November 2026 (Asia/Calcutta). These are archived measurements and
verification records, not a claim that all experiments were rerun together.

## What KubeSentinel AI does

**Observe → normalize → explain → evaluate policy → approve when required →
execute within bounds → verify → audit.**

The dashboard exposes telemetry, incidents, anomaly explanations and recovery
evidence. The backend persists operational records; diagnostic recommendations
remain advisory. The scoped operator independently checks policy, workload
identity, freshness, availability and approval before mutation. It defaults to
dry-run, protects system scope and records rejection as well as execution.

## Measured results

| Experiment | Recorded outcome | Source and limit |
| --- | --- | --- |
| Rules | Precision/recall/F1: 1.000/1.000/1.000 | [Evaluation JSON](phase-05/evaluation.json); 177 synthetic windows and two fault incidents |
| Robust statistics | Precision/recall/F1: 0.875/0.350/0.500 | Same held-out fixture; missed one of two incidents |
| Isolation Forest | Precision/recall/F1: 0.667/0.900/0.766; nine false positives | Same fixture; uncalibrated scores, no production accuracy claim |
| Kubernetes actions | Succeeded 2, Rejected 4, DryRun 1, RolledBack 1 | [Eight action records](phase-06/all-actions.json); heterogeneous outcomes, not repeated recovery trials |
| Approved scale example | 10 s observation-to-apply; 36 s apply-to-success | [Action audit](phase-06/approved-scale.json); one example including approval/polling |
| Health-only API load | 900 requests; zero errors; trial p95 23.59–122.61 ms; throughput 94.44–227.53 req/s | [Summary](release-audit/health-loopback-summary.json), [raw CSV](release-audit/health-loopback-raw.csv); no DB/cluster paths |
| Correlation/retrieval | 12 expected directed links found; 8/8 runbook matches | [Synthetic fixtures](phase-10/results.json); not real-world root-cause accuracy |
| Security remediation | No HIGH/CRITICAL findings or detected secrets in five application images at the recorded scan | [Scan summary](release-audit/security-remediation.json); MEDIUM/LOW/UNKNOWN findings remain |

The detector and action inputs are available at snapshot
`3d77f959fdf43e4da2f504fecbe8e8cf58d1295b`. The health-load report records its own
source revision `38e3e5a0c3bc7dde41e0bf6527aea8dae4cd086f`. Historical runs are
not pooled into a single system benchmark. The earlier
[Phase 09 health experiment](../benchmarks/phase-09/loopback/summary.json) is a
different run; its latency range must not be substituted for the release-audit
experiment used above.

## Test evidence

The installer PR head `6b0b81e2cadf28a4828314ca97727b00c9800629` passed 24 GitHub
checks, including Windows/Linux API tests, frontend, migrations, container,
Kubernetes, telemetry, recovery, ML reproducibility and security checks.
[PR #28](https://github.com/manikantbindass/KubeSentinel-AI/pull/28) merged as
`c451d7d4023a6db750b8a21e3991aa5607066658`.
[Inspect checks for that reviewed commit](https://github.com/manikantbindass/KubeSentinel-AI/commit/6b0b81e2cadf28a4828314ca97727b00c9800629/checks).
New commits require their own checks; a historical green run does not certify a
later revision or production readiness.

The local Windows suite recorded 85 passes and one skipped real-PostgreSQL test
because `TEST_DATABASE_URL` was unset. CMD orchestration includes five tests
against a recording Docker stub. The local Docker Linux engine was unavailable,
so those CMD tests do not prove a fresh Windows container startup.

## Final outcome and remaining requirements

**KubeSentinel AI is an inspectable development prototype that combines
observability, explainable detection, incident investigation and policy-governed
Kubernetes recovery. Its available evidence includes successful recovery,
deliberate rejection, dry-run and rollback outcomes.**

It is not established that one real incident traversed every telemetry, ML,
backend, operator and dashboard stage in a continuous verified experiment.
Production data generalization, matched native-recovery comparisons, full-stack
load, HA/restore, tenant-specific OIDC and live AWS/Argo deployment remain open.
No paid AWS resources were created and no release publication is claimed.
