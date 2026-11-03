# Actual local-cluster observability captures

Captured automatically by Playwright in successful [Linux kind run 41562202925](https://github.com/manikantbindass/KubeSentinel-AI/actions/runs/41562202925), source commit `19c0645`, 2026-11-03 UTC. Downloaded without image editing and visually inspected. These are a disposable local CI cluster, not AWS or production. Full acceptance details: [Phase 04 record](../../reports/phase-04-validation.md).

| Capture | Observed content |
| --- | --- |
| [Cluster overview](cluster-overview.png) | Real node capacity, namespace CPU/memory and pressure |
| [Namespace/workload](namespace-workload.png) | Actual restarts, readiness, replicas and OOM fault |
| [Application](application-performance.png) | Sample request traffic, latency and received OTLP spans |
| [Incident timeline](incident-timeline.png) | Durable incident counts and actual JSON logs from Loki |
| [Recovery history](recovery-history.png) | Zero outcomes and explicit absence of an executor |
| [SLI/error budget](slo-error-budget.png) | Short-window diagnostics; no compliance claim |
| [Connected dashboard](incident-app.png) | Ready API/stores, historical startup warnings and resolved fault alerts |

The connected dashboard capture predates the Phase 05 footer wording correction; its model-status sentence is historical. Startup Warning records intentionally remain historical/open; Alertmanager fault alerts demonstrate resolution. No-data 5xx/pending panels reflect no matching series during capture. No simulated curves, fabricated recovery counts or edited fault evidence are included.
