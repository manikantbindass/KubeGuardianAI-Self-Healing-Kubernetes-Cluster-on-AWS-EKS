# Recovery policy ownership

Phase 06 implements the initial deterministic policy/decision pipeline inside the [Go operator](../../operator/README.md), beside its independently guarded execution and verification code. There is no separate running recovery-engine microservice. Typed CRDs bind evidence, workload/policy versions, expiry, approvals, cooldowns, budgets and verified rollback snapshots. Defaults remain dry-run; isolated local execution requires explicit global/policy enablement and risk-appropriate signed approval.

See [architecture](../../docs/architecture/recovery-operator.md), [runbook](../../docs/runbooks/recovery-operator.md) and [actual acceptance](../../docs/reports/phase-06-validation.md). A future extraction must preserve these safety boundaries rather than let ML or an assistant choose executable actions directly.
