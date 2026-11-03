# Phase 06 validation

Date: 2026-11-03, Asia/Kolkata. Branch: `feat/phase-06-policy-operator`. This record is updated with actual acceptance results; no AWS resources are provisioned.

## Completed local checks

- Pinned Go 1.26.8 toolchain, controller-runtime 0.23.3 and Kubernetes API/apimachinery 0.35.0 dependencies resolved with `go.mod`/`go.sum`.
- `go test ./... -count=1 -cover`: 13 top-level tests plus the policy matrix passed; recovery package statement coverage 67.4%. This does not claim complete coverage of CLI/manager wiring. Tests include signatures, policy-edit approval identities, cooldown/budget/conflicts, dry-run, guarded scale, exact-template undo, failed rollback, API outages, stable OOM identity and protected targets.
- `go vet ./...` passed. Structural CRD/deep-copy generation with controller-tools 0.20.1 completed. Chart copies are generated from the same typed contracts.
- Helm lint/template passed for namespace `sentinel-lab`. kubeconform validated eight standard Kubernetes resources; four CRDs are delegated to real API server admission rather than falsely claiming standard schema coverage.
- Python Ruff/format and strict mypy passed; `python -m pytest -q -m "not postgres"` passed 35 tests, with PostgreSQL explicitly deselected locally. Markdown lint, ten Mermaid diagrams and local links/original LICENSE checks passed.

## Live local-cluster acceptance

The dedicated [Recovery operator workflow](https://github.com/manikantbindass/KubeSentinel-AI/actions/workflows/operator.yml) runs an isolated kind cluster, actual operator/demo images, API admission, RBAC checks and fault injection. **Final implementation source `8860c3b` passed all fourteen PR checks.** [Recovery run 41567649861](https://github.com/manikantbindass/KubeSentinel-AI/actions/runs/41567649861) passed Windows/Linux Go tests, vet, module verification, generation consistency and complete actual recovery acceptance. The isolated cluster was deleted by the workflow after evidence upload.

The earlier successful [run 41566741080](https://github.com/manikantbindass/KubeSentinel-AI/actions/runs/41566741080), source `12f8356`, established the first live recovery result. Final source additionally verifies complete-template restoration, last-moment native revalidation, signer cache reuse and policy-version-specific approval identities. The final evidence below is downloaded from **41567649861**, not copied from that earlier run.

| Controlled test | Final recorded outcome | Evidence |
| --- | --- | --- |
| CrashLoopBackOff with default policy | DryRun, no mutation attempt | [dry-run.json](phase-06/dry-run.json) |
| Actual memory-limited OOM rollout | Signed Rollback Succeeded, one attempt, zero post-check errors | [approved-rollback.json](phase-06/approved-rollback.json) |
| Readiness fault whose restart cannot fix configuration | Original Restart did not succeed; approved undo independently verified, RolledBack, two attempts | [failed-restart-undo.json](phase-06/failed-restart-undo.json) |
| Deliberately slow-starting replica shortage | Signed bounded Scale to four replicas Succeeded; four available replicas asserted | [approved-scale.json](phase-06/approved-scale.json) |
| New fault inside cooldown | Rejected, CooldownActive, no attempt | [cooldown.json](phase-06/cooldown.json) |
| No authorized maintenance time / policy changed | Rejected without mutation | [all-actions.json](phase-06/all-actions.json) |

[Summary](phase-06/summary.json) records the exact dedicated context/namespace and eight durable action records. Records contain actual actor/approver, policy UID/version, native incident identity, target versions, signed-plan linkage, before/after sampled SLIs, result/timestamps and transition audit. They contain only controlled CI fixture information; private signing keys and kubeconfig are excluded. Small p95 values rounded to 0–1 milliseconds are real health-endpoint samples, not production latency guarantees.

The live test also asserted invalid-signature refusal, duplicate reconciliation, immutable action-spec CEL, and actual RBAC denial of pod deletion, secret access, arbitrary/system Deployment mutation, base action edits and operator self-approval. CRD admission succeeded in Kubernetes 1.35; standard-resource kubeconform checks alone were not treated as CRD validation.

The acceptance script tests real crash dry-run; OOM approval waiting; invalid-signature refusal; signed verified-template rollback; rollout/replica/SLI success; duplicate reconciliation; failed readiness-restart verification with approved undo; cooldown/maintenance rejection; immutable action plans and a signed scale-up during a controlled slow-starting shortage. It saves action specs/status/audit/measurements in `.cache/operator/evidence`. CI uploads only that directory, never the private signing key.

Local Windows Docker remains unavailable, so live acceptance is performed in Linux CI. Scaling was exercised in the actual cluster as well as the fake-client unit suite. Controlled lab fixtures are not production fault evidence.

The initial [run 41565896215](https://github.com/manikantbindass/KubeSentinel-AI/actions/runs/41565896215) failed because restart-count/reason churn invalidated pending OOM approval; the stable native identity and OOM precedence fix was then tested successfully. Later review added complete-template replacement, last-moment native revalidation, shared signer build caches and policy-version-specific approval identities. Superseded workflow runs may be canceled to preserve CI runner capacity; they are not reported as passing.

## Application regression checks

For implementation `8860c3b`, [foundation run 41567649876](https://github.com/manikantbindass/KubeSentinel-AI/actions/runs/41567649876) passed Windows/Linux API checks, frontend lint/types/tests/build, PostgreSQL migration round-trip and actual Compose startup/outage/recovery. [ML run 41567649927](https://github.com/manikantbindass/KubeSentinel-AI/actions/runs/41567649927) passed Windows/Linux reproducibility and detector trained/fallback container tests. [Kind run 41567649845](https://github.com/manikantbindass/KubeSentinel-AI/actions/runs/41567649845), [monitoring run 41567649853](https://github.com/manikantbindass/KubeSentinel-AI/actions/runs/41567649853) and [Terraform static run 41567649912](https://github.com/manikantbindass/KubeSentinel-AI/actions/runs/41567649912) passed. No cloud apply, destroy or paid provisioning was run.

The final evidence/text update does not change operator runtime, policy schemas or tested recovery behavior. It corrects the dashboard footer and legacy API/Grafana counter wording so zeros are not mistaken for operator outcomes. After those text-only edits, 35 Python tests, ten frontend tests, frontend lint/type checks, Ruff/format and strict mypy passed locally. Markdown/link/Mermaid checks also passed. A fresh CI cycle may run for that final evidence commit; completed runtime proof is tied explicitly to `8860c3b` above.

## Limits and safety gates

The default installation/policy remain dry-run. Only named, opted-in Deployments in a single non-critical namespace can be patched; no pod deletion, arbitrary Deployment, system namespace, secret read or self-approval permission exists. Ed25519 approval is mandatory for Scale/Rollback/automatic undo. Native/service evidence is independent of ML output. Uncertain mutations or failed verification hold further actions and escalate.

Actions/audit persist in Kubernetes etcd, not an immutable external compliance store. Health-endpoint samples are bounded verification, not production-wide SLO proof. Escalation destinations are recorded but external notifications are not sent. Stateful/data rollback, automated resource-limit tuning, public approval UX, signed registry promotion and production admission hardening remain out of scope. Existing base-image vulnerability findings require separate review; passing recovery tests does not certify image security or production readiness.
