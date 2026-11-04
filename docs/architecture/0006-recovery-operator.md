# ADR 0006: fenced, namespace-scoped recovery execution

- Status: accepted for isolated local Phase 06 validation
- Date: 2026-11-03

Use Go 1.26.8, controller-runtime 0.23.3 and Kubernetes 0.35.0 libraries, consistent with the original operator boundary. Use typed namespaced CRDs for policy, immutable action/approval plans and verified revisions. Keep execution independent of Python ML output and revalidate actual Kubernetes/service evidence before every initial action.

Use Lease leadership plus one reconciliation worker, target UID/resourceVersion/generation tests, durable pre-mutation intent and conservative holds for uncertain outcomes. This favors operator intervention over potentially repeated destructive work. Kubernetes etcd is the local durable action/audit store; an external immutable export remains a production requirement.

Require offline Ed25519 signatures for scale, rollback and automatic undo. Runtime holds public keys only. RBAC denies arbitrary workload mutation, pod deletion, secret reading and self approval. Both global and policy execution must be enabled explicitly; defaults are dry-run. A fully unavailable deployment cannot bypass the minimum-availability guard.

Use exact previously verified template snapshots rather than blind `rollout undo` against unverified ReplicaSets. Verify replica availability and bounded HTTP error/p95 samples after each effect. Escalate instead of inferring that a patch succeeded. Pressure/latency alone are alert-only. Alternatives include OPA/admission enforcement, external approvals and transactional SQL action storage; these remain later production hardening work, not implicitly delivered here.

See [architecture](recovery-operator.md), [runbook](../runbooks/recovery-operator.md) and [acceptance evidence](../reports/phase-06-validation.md).
