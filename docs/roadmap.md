# Development roadmap

## Executed request sequence

Phase 06 now implements the local guarded recovery operator: typed policies, signed plan approvals, durable CRD audit, native revalidation, verified mutations/undo and fail-closed safety holds. Its [validation record](reports/phase-06-validation.md) is the authority for completed tests; this does not authorize production or cloud execution. Production identity/admission, external audit/notifications and broader real-workload evaluation remain separate gates.

The current implementation requests use: 00 repository architecture, 01 full-stack foundation, 02 local Kubernetes, 03 AWS infrastructure code, 04 full-stack observability, and **05 advisory anomaly detection**. The historical milestone table below is retained as design history; its older phase numbers are not the current execution sequence.

Phase 05 delivers feature windows, baseline/statistical/Isolation Forest scoring, reproducible synthetic evaluation, a bounded advisory service and incident evidence. See its [acceptance record](reports/phase-05-validation.md) and [model card](../ml/models/model-card.md). Its synthetic ML results do not justify replacing rules or enabling remediation. Next gates are independently labeled real-workload validation, identity/tenant controls, durable incident lifecycle and separately authorized policy/operator work. No live AWS deployment or advanced sequence model is implied.

The executed sequence is Phase 00 foundation, Phase 01 full-stack local runtime, Phase 02 kind/Helm orchestration and Phase 03 AWS infrastructure **code only**. The earlier feature milestones below retain their original planning labels; those labels do not imply that telemetry or identity shipped in the actual Phase 02/03 execution. Future feature ordering needs a separate implementation request. No performance results are promised.

Phase 02 evidence is in its [validation record](reports/phase-02-validation.md). Phase 03 [static validation](reports/phase-03-validation.md) and [cost/operator gates](runbooks/aws-eks.md) do not authorize provisioning. The optional AWS pilot milestone below remains a future **live deployment**, distinct from the source code delivered now.

| Phase | Deliverables | Exit gate |
| --- | --- | --- |
| 00 - Foundation | Repository audit, C4 architecture, ADRs, standards, skeleton, threat model, costs, docs checks | Essential docs present; links/Markdown/diagrams validate; original LICENSE and history preserved; no runtime claims |
| 01 - Local vertical slice | Next.js/TypeScript/Tailwind dashboard, FastAPI hello and typed `/health`, connectivity/error UI, Dockerfiles/Compose, exact pins and locks, Windows/Linux/macOS setup, CI | Clean locked installs; lint/types/unit/build pass; native/container startup, API unavailable, and recovery smoke tests recorded; no cluster/AWS |
| 02 - Identity and local lab | OIDC provider ADR, session/CSRF/RBAC boundaries, kind/k3d ADR, isolated demo workload, deterministic faults and cleanup | Wrong issuer/audience/role/scope denied; local lab reproducible; resource/namespace isolation and teardown proven |
| 03 - Telemetry | Collector, metric/log/event schemas, provenance/redaction, retention, cardinality/backpressure limits, Prometheus/Loki evaluation | Known fixtures ingest with correct identities/time; outage/lag/loss behavior and overhead measured; no execution rights |
| 04 - Baseline anomaly detection | Deterministic feature windows, statistical rules, score/evidence schema, dataset provenance and temporal splits | Held-out evaluation records false positives, precision/recall and latency versus a declared baseline; no leakage |
| 05 - Incident state and durability | Correlation/deduplication, PostgreSQL migrations, Redis/outbox, incident API/SSE, audit index and notification adapter | Replay/reconnect deterministic; restart/Redis loss recover from SQL; notification retries do not replay actions; restore tests pass |
| 06 - Remediation policy | Typed proposals, risk/allowlists, approval binding/expiry, cooldowns/budgets, dry-run UX and audit | Denied/stale/duplicate/unapproved requests cannot execute; evidence and rollback shown; dry-run only |
| 07 - Operator | Scoped Go controller, CRDs/admission, RBAC, reconciliation, verification/rollback, kill switch | Isolated-cluster tests prove denial, idempotency, retry bounds, policy outage handling, target preconditions, audit and rollback; opt-in execution only |
| 08 - ML lifecycle | Reproducible training, versioned feature/model lineage, model registry metadata, drift and rollback | Held-out results beat declared baseline where justified; temporal/incident leakage excluded; model rollback demonstrated |
| 09 - AI assistant | Redacted retrieval, cited evidence/runbooks, privacy/provider ADR, prompt-injection/cost tests | Grounded answers with uncertainty; no approval/execution authority; evaluation and egress limits recorded |
| 10 - Production hardening | Tenant isolation, immutable audit export, auth review, SBOM/scanning/signing, SLOs, restore/DR, load/chaos/security tests | Security boundaries tested, operating/incident runbooks exercised, RPO/RTO measured, owners and alerts assigned |
| 11 - Optional AWS EKS pilot | Separately approved Terraform/EKS/network/IAM/state/cost design; Helm/Argo CD; staging monitoring | Written approval before apply; budgets, least privilege, synthetic workloads, drift and complete teardown proven |
| 12 - Evaluation and release | Reproducible fault matrix, overhead/cost/MTTR/recovery comparisons, limitations, report/deck, signed release | Successful and failed trials retained; evidence supports claims; deployment/rollback guide and release gates reviewed |

## Phase 01 handoff

Start from this branch's architecture and preserve existing files/history. Add runnable code only under a new reviewed phase change. Pin compatible package and container versions, produce npm and uv lockfiles, add lint/type/test/build configuration, and exercise native and Linux-container startup. Keep auth and cluster connectivity explicitly out of the initial health slice unless the phase is deliberately re-scoped. No AWS provisioning.

## Cross-cutting rules

- Link design, implementation, threat/cost review, test commands, and acceptance results for each phase.
- Detection is advisory; operator execution is independently authorized. Defaults remain disabled/dry-run until gates pass.
- Keep dataset provenance/licenses and redact telemetry. Split by time and incident lineage; report failed trials and false positives.
- Evaluate risk from telemetry gaps, correlated faults, privilege creep, unsafe loops, model drift, prompt injection, GitOps conflicts, and cloud cost.
- Pin dependencies and artifacts with locks/digests as components are introduced; update supported versions through reviewed changes.
