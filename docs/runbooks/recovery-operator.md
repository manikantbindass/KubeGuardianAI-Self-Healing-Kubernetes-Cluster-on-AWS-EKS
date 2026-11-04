# Install and operate the recovery controller

This operator is for a dedicated local kind lab. It never provisions AWS and never uses your default kubectl context. Read the [architecture and limitations](../architecture/recovery-operator.md) before enabling mutation. The installer uses cluster `kubesentinel-recovery`, context `kind-kubesentinel-recovery` and namespace `sentinel-lab`; it refuses an existing cluster during bootstrap.

## Toolchain and validation

Install Docker with Linux containers, kind 0.31.0, kubectl compatible with Kubernetes 1.35, Helm 3.19.0, Python 3.12 and Go 1.26.8. `operator/go.mod` pins the toolchain and Kubernetes/controller-runtime versions; `go.sum` locks downloaded module checksums. Go may download the specified toolchain when an older supported Go launcher is used.

From the repository root on Linux/macOS or Windows PowerShell:

```sh
go -C operator mod verify
go -C operator test ./... -count=1
go -C operator vet ./...
python scripts/recovery_lab.py generate
helm lint infrastructure/helm/recovery-operator --namespace sentinel-lab
helm template sentinel-recovery infrastructure/helm/recovery-operator --namespace sentinel-lab --include-crds
```

Use `python3` on Linux/macOS or `py -3.12` on Windows if `python` is not on PATH. Make is optional; equivalent `operator-test`, `operator-generate`, `operator-lab` and `operator-clean` targets are in the root Makefile. The generator pins controller-tools 0.20.1 and copies generated CRDs into the chart; commit both copies and generated deep-copy code. CI rejects generation drift. Go unit tests exercise decisions, signatures, no-op/dry-run reconciliation, guarded scaling, verification, ambiguity holds and failure handling. The real API server validates CRD structural schemas/CEL in the isolated lab.

## Start with dry-run

```sh
python scripts/recovery_lab.py bootstrap
kubectl --context kind-kubesentinel-recovery -n sentinel-lab get pods,remediationpolicies,verifiedrevisions
```

This builds non-root operator/demo images, loads them into kind, derives exact API server Service/endpoint CIDRs, installs namespace-scoped RBAC, two controller replicas and a Lease, then deploys two healthy demo replicas and the [dry-run policy](../../operator/policies/dry-run.yaml). It generates a local Ed25519 approver key in ignored `.cache/operator/approver.key` and mounts **only its public key** in the controller. Neither global execution nor the policy is enabled by default.

Key generation uses exclusive creation and owner-only permissions on Unix. On Windows, NTFS ACLs follow the workspace inheritance rules; restrict the key file to the intended approver account. Do not upload `.cache`, private keys or kubeconfig as CI artifacts. CI publishes only selected action/audit records. Never put approver keys into a Kubernetes Secret accessible to the operator.

## Execute the isolated acceptance test

On a fresh disposable lab, use:

```sh
python scripts/recovery_lab.py bootstrap --execute
python -u scripts/test_operator.py
```

If already bootstrapped in dry-run, either clean and rebuild explicitly or run `python scripts/recovery_lab.py install --execute` to change global enablement on this same dedicated context. The test expects a fresh policy/action history. It explicitly changes the demo policy to execute, signs only local test plans, injects crash/OOM/readiness faults and restores the demo workload. **These are real local mutations**, authorized only for the dedicated disposable lab. No production namespace or AWS is targeted.

The test checks actual `kubectl auth can-i` denials, a certified healthy revision, crash dry-run, real OOM approval gating, invalid-signature rejection, approved template rollback with rollout/SLI verification, duplicate reconciliation, failed restart followed by approved verified undo, cooldown/maintenance rejection, immutable-plan CEL and approved bounded scale-up during a deliberately slow-starting replica shortage. Evidence is in `.cache/operator/evidence`; the [validation record](../reports/phase-06-validation.md) distinguishes completed live tests from local unit checks. Test failure prints lab diagnostics. Cleanup is explicit:

```sh
python scripts/recovery_lab.py clean
```

Cleanup deletes only kind cluster `kubesentinel-recovery`, including its etcd/audit data. Export evidence first. Do not use this cleanup script for cloud infrastructure.

## Review and approve one plan manually

Inspect the action spec, policy version, target UID/generation, native incident, age, allowed action, replica bounds and rollback consent. Verify that the before snapshot and budget cover the proposed effects. An approval is not a blanket policy exemption.

```sh
kubectl --context kind-kubesentinel-recovery -n sentinel-lab get remediationactions
kubectl --context kind-kubesentinel-recovery -n sentinel-lab get remediationaction ACTION_NAME -o json > .cache/operator/action.json
go -C operator run ./cmd/approval --action ../.cache/operator/action.json
kubectl --context kind-kubesentinel-recovery -n sentinel-lab apply -f .cache/operator/approval.json
kubectl --context kind-kubesentinel-recovery -n sentinel-lab get remediationaction ACTION_NAME -o yaml
```

The signer accepts only an unexpired `AwaitingApproval` action with a Kubernetes UID and binds its exact spec. It expires within five minutes or sooner at incident expiry. For Windows PowerShell 5.1, use `Out-File -Encoding utf8` for exported JSON and a Python conversion to remove BOM if needed; PowerShell 7 and Linux/macOS redirection produce UTF-8. The private key stays on the approver's machine. In team use, bind `sentinel-recovery-approver` Role only to explicit authorized users and configure their reviewed public keys through Helm. No approver RoleBinding is created automatically.

Both `executionEnabled: true` and policy `dryRun: false` are needed. `approvalRequired: false` can permit only low-risk Restart; Scale, Rollback and automatic undo still require a signature. Before every initial mutation the operator re-reads Deployment/policy, rechecks native evidence, cooldown, budget, maintenance window and availability, and stores intent. Approval cannot override a rejection.

## Helm and CRD configuration

| Setting | Default / meaning |
| --- | --- |
| `image.repository`, `image.tag` | `kubesentinel/operator:phase06-local`; use a reviewed digest-pinned artifact before real use |
| `replicas` | 2, one elected leader; Deployment reconciliation concurrency stays 1 |
| `executionEnabled` | false, global kill switch |
| `workloads` | `[demo-recovery]`, independent name allowlist and RBAC patch resourceNames |
| `approvalPublicKeys` | Key ID → base64 Ed25519 public key, empty by default |
| `apiServerCIDRs` | Empty/fail-closed; installer discovers exact local API IPs |
| `probePorts` | `[8080]`, opted-in workload HTTP probe egress |
| `resources` | Bounded non-root controller requests/limits |

Policy schema and defaults are in [generated CRDs](../../operator/crds). [Dry-run example](../../operator/policies/dry-run.yaml) includes every policy field. Maintenance uses UTC weekday numbers 0–6 and non-wrapping start/end hours. An overnight interval requires two windows. Empty windows deny execution. Replica changes only increase by `scaleStep` within min/max; there is no automatic scale-down. Cooldown is per workload UID across policies. Budgets count attempted mutations per policy UID across its namespace. Undo reserves two units before any action; deleting/recreating policy/action objects can erase history and is an administrative safety responsibility.

CRDs install once through Helm's `crds/`; Helm does not automatically upgrade them. Before changing schemas, disable execution, review a compatibility/backup plan, apply the reviewed CRDs with administrator credentials, and roll out matching controller code. Do not delete CRDs to upgrade: that destroys durable records. Policy/action/approval/revision mutation permissions are intentionally split.

## Recovery, verification and escalation

Only `Succeeded` after repeated healthy rollout/replicas and sampled SLI checks means verified recovery. `Applying` means intent, `Verifying` means an effect is still being assessed, `RolledBack` means the original attempt failed and approved undo was verified. Never present a successful patch as a recovered service.

`Escalated`/`Failed` with `hold: true` blocks new actions for that workload UID. Inspect the deployment generation/template/replicas/action marker, audit timestamps, policy and service before deciding whether any effect occurred. Do not delete the action or clear the hold just to make a test green. A trusted administrator may clear a hold via status only after recording the investigation externally; the operator has no automatic hold-clearing path. Stopping the controller does not undo a Deployment-controller rollout already in progress.

The configured escalation destination is recorded durably for external routing; this phase does not send Slack/email/pager messages. Export action/status records for a notification/audit integration rather than granting arbitrary webhook URLs to policies. No external messages are sent by these scripts.

## Troubleshooting and emergency stop

- No action: check installation workload names, opt-in labels, protected namespaces, exactly one matching policy, native evidence, sustain time and leader Lease. Healthy replicas may still need a service matching `app=deployment-name` before a revision can be certified.
- `DryRun`: expected unless both execution switches are enabled. Dry-run never patches a Deployment.
- `AwaitingApproval`: check trusted public key ID, exact plan digest/UID, namespace and expiry. An invalid or wrong-key signature cannot authorize execution.
- `WorkloadChanged`/`PolicyChanged`: review a new plan against current state; approvals do not follow target edits or policy changes.
- `MinimumHealthyReplicasAtRisk`: retain availability rather than forcing recovery; fully down workloads require manual incident response.
- `NoVerifiedPreviousRevision`: restore a known-good configuration manually; never fabricate verified status. Snapshots are only captured from healthy replicas with passing service samples.
- `VerificationFailed`: inspect actual readiness, desired/updated/available replicas, health sample errors/p95, capacity and SLO bounds. HTTP samples are not full production traffic SLOs.
- API outage: restore connectivity/RBAC. Pending work must not execute without fresh reads. `MutationOutcomeUncertain` requires human inspection because the request may have reached the API server.
- Competing HPA/GitOps: coordinate ownership; generation drift triggers holds instead of a reconciliation fight.
- Emergency stop: set Helm `executionEnabled=false` and roll out, or scale **operator** replicas to zero as an administrator. Also disable affected policies. Existing kube-controller rollouts may continue; inspect them separately.
- Leader failover: inspect the `kubesentinel-recovery` Lease and both controller logs. Standby liveness is not proof it owns leadership. No release-on-cancel shortcut is used.
- Capacity/retention: archive audit records with a verified backup and preserve the full cooldown/budget horizon. More than 1000 records blocks new work intentionally.

Production promotion still needs admission controls for allowed patch fields, signed/scanned runtime images, immutable external audit export, actual notification delivery, policy/key governance, broader failure/performance testing and explicit authorized workload ownership. See [architecture](../architecture/recovery-operator.md) and [validation](../reports/phase-06-validation.md).
