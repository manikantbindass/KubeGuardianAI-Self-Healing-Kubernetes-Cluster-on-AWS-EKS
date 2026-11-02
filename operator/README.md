# Kubernetes operator (future)

Planned Go/controller-runtime controller, versioned CRDs, scoped RBAC and default-deny execution policy. No controller or CRD is implemented or installed. Controllers must reconcile immutable approved requests, check target preconditions and policy expiry, bound retries/cooldowns/budgets, audit intent/results, verify effects and stop on ambiguous state. Separate policy/approval from detection and execution. Activation requires Phase 07 evidence in the [roadmap](../docs/roadmap.md).
