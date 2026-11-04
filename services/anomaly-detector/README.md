# Advisory anomaly detector

Phase 05 implements a FastAPI service with bounded batch scoring, real telemetry polling, rules/robust-statistics/Isolation Forest options, JSON models and rule fallback. Rules are the default because the synthetic benchmark does not justify promoting ML above them. No Kubernetes write or remediation interface exists.

See the [operating guide](../../docs/runbooks/anomaly-detection.md), [model card](../../ml/models/model-card.md), [validation](../../docs/reports/phase-05-validation.md) and [architecture](../../docs/architecture/anomaly-detection.md). Synthetic telemetry/models are separated from live incident publishing.
