# Policy-driven recovery operator

Phase 06 implements a Go/controller-runtime controller for explicitly allowlisted Deployments in one non-critical namespace. Typed CRDs define policies, immutable action plans, signed approvals and independently verified template snapshots. Two replicas share a Lease; only the leader reconciles, with one active reconciliation and optimistic API mutation preconditions.

Execution requires both `--execute` and policy `dryRun: false`. Scale, rollback and automatic undo always require offline Ed25519 approval. ML/LLM outputs cannot select or execute actions. No pod deletion, system-namespace mutation, secret read or self-approval permission exists.

See [installation and safety runbook](../docs/runbooks/recovery-operator.md), [architecture](../docs/architecture/recovery-operator.md), [state machine](../docs/diagrams/recovery-state-machine.mmd), [example policy](policies/dry-run.yaml) and [validation](../docs/reports/phase-06-validation.md). The default example is dry-run. The separate recovery kind lab is disposable and never targets AWS.
