# Phase 06 validation

Date: 2026-11-03, Asia/Kolkata. Branch: `feat/phase-06-policy-operator`. This record is updated with actual acceptance results; no AWS resources are provisioned.

## Completed local checks

- Pinned Go 1.26.8 toolchain, controller-runtime 0.23.3 and Kubernetes API/apimachinery 0.35.0 dependencies resolved with `go.mod`/`go.sum`.
- `go test ./... -count=1`: policy matrix, approval signatures, cooldown/budget/conflict checks, dry-run, guarded scale reconciliation, verification, ambiguity/failure hold and protected-target tests passed locally.
- `go vet ./...` passed. Structural CRD/deep-copy generation with controller-tools 0.20.1 completed. Chart copies are generated from the same typed contracts.
- Helm lint/template passed for namespace `sentinel-lab`. kubeconform validated eight standard Kubernetes resources; four CRDs are delegated to real API server admission rather than falsely claiming standard schema coverage.
- Python Ruff/format and strict mypy passed after adding the recovery lab/test scripts. Existing application regression tests are rechecked in CI.

## Live local-cluster acceptance

The dedicated [Recovery operator workflow](https://github.com/manikantbindass/KubeSentinel-AI/actions/workflows/operator.yml) runs an isolated kind cluster, actual operator/demo images, API admission, RBAC checks and fault injection. The draft PR must retain failed runs until fixes and a complete successful run are recorded here. No successful live recovery is claimed solely from unit tests or chart rendering.

The acceptance script tests real crash dry-run; OOM approval waiting; invalid-signature refusal; signed verified-template rollback; rollout/replica/SLI success; duplicate reconciliation; failed readiness-restart verification with approved undo; cooldown/maintenance rejection and immutable action plans. It saves action specs/status/audit/measurements in `.cache/operator/evidence`. CI uploads only that directory, never the private signing key.

Local Windows Docker remains unavailable, so live acceptance is performed in Linux CI. Unit scaling tests use the Kubernetes fake client; do not describe those as live scaling until independently exercised. Source fixtures and model tests are not production fault evidence.

## Limits and safety gates

The default installation/policy remain dry-run. Only named, opted-in Deployments in a single non-critical namespace can be patched; no pod deletion, arbitrary Deployment, system namespace, secret read or self-approval permission exists. Ed25519 approval is mandatory for Scale/Rollback/automatic undo. Native/service evidence is independent of ML output. Uncertain mutations or failed verification hold further actions and escalate.

Actions/audit persist in Kubernetes etcd, not an immutable external compliance store. Health-endpoint samples are bounded verification, not production-wide SLO proof. Escalation destinations are recorded but external notifications are not sent. Stateful/data rollback, automated resource-limit tuning, public approval UX, signed registry promotion and production admission hardening remain out of scope. Existing base-image vulnerability findings require separate review; passing recovery tests does not certify image security or production readiness.
