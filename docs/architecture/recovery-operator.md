# Policy-driven recovery architecture

The [recovery state machine](../diagrams/recovery-state-machine.mmd) is implemented in `operator/internal/recovery`. This is a trusted, isolated development operator for Deployments, not a general production remediation authority. API/ML scoring and action execution remain separate trust boundaries.

## Incident and decision pipeline

The namespace-scoped controller reads Deployment, owned ReplicaSet/Pod state and a workload-bound ClusterIP service. Native waiting/termination/readiness conditions produce typed incidents with deterministic workload/generation/evidence identities. Only pods controlled by a ReplicaSet controlled by the exact Deployment UID count. A minimum sustain interval is measured from the durable action creation time; native evidence must still match before execution. Stale, resolved or changed incidents are rejected. Historical incident text or an arbitrary ML score cannot become a mutation request.

| Scenario | Independent evidence | Fixed response |
| --- | --- | --- |
| CrashLoopBackOff | Owned container waiting reason | Verified previous-template rollback, signed approval |
| OOMKilled | Recent owned-container OOM termination | Verified previous-template rollback, signed approval; no blind memory increase |
| Readiness failure | Running container passed startup but not ready | Rollout restart only under safe rollout/availability constraints |
| Stuck rollout | ProgressDeadlineExceeded | Verified previous-template rollback, signed approval |
| Excessive restarts | At least three restarts and not ready | Restart subject to all guards; crash/OOM evidence takes priority |
| Replica shortage | Observed generation and fewer available than desired | Bounded scale-up, signed approval |
| Sustained resource pressure | Owned unschedulable/evicted pod held through sustain interval | Alert-only escalation; scaling could worsen saturation |
| Service degradation | Repeated live service sample above error/latency SLO | Alert-only escalation; latency alone never chooses a cluster change |

The incident ID and evidence are durable inside `RemediationAction`. Phase 04's PostgreSQL incidents remain a separate source of observation/history; this operator does not trust an arbitrary backend/Alertmanager/ML payload to execute. A future correlation bridge must retain independent native revalidation, workload identity and signed-plan gates. CPU/memory percentage thresholds from Phase 05 are not automatically converted into execution rights.

## Policy and approval boundaries

Exactly one matching policy is required. Installation has an independent workload-name allowlist enforced again by Deployment patch RBAC `resourceNames`. The Deployment must carry `recovery.kubesentinel.ai/enabled: "true"`, match explicit policy labels, and not be a KubeSentinel/system-priority workload. Policy namespace allowlists cannot grant rights outside the installation namespace. `default`, `kube-*`, `kubesentinel`, telemetry, Argo CD, ingress and cert-manager namespaces are protected in installation, Helm and decision code. Administrators must extend this denylist for organization-specific critical namespaces.

Policies contain allowed incidents/actions, minimum severity, dry-run, explicit UTC maintenance windows, cooldown, namespace-wide policy action budgets, replica/scale bounds, minimum healthy replicas, incident age, sustain time, escalation reference, verification and rollback rules. Empty maintenance windows deny execution. Global execution defaults false; policy dry-run defaults true; approval defaults true. Scale is upward only, within explicit step/min/max. Rollout restart/rollback require RollingUpdate with maxUnavailable=0 and nonzero maxSurge. Fully unavailable deployments are escalated because the minimum healthy replica guard takes priority over aggressive recovery.

Action specs bind policy UID/resourceVersion, workload UID/generation/template digest/replicas, incident identity/time, action parameters, expiry, revision snapshot and rollback consent/budget. CRD transition CEL rejects spec edits. Policies changed while approval/verification is underway invalidate the original plan. Multiple policies or conflicting actions fail closed.

Approvals are immutable resources containing an Ed25519 signature over protocol version, namespace, action UID, full plan digest, expiry and key ID. The signing CLI runs outside the cluster; private keys never enter the controller. The controller mounts only public keys. Approval apply permission alone cannot forge consent. Controller RBAC cannot create approvals, read secrets, modify policy/approval specs or change trusted keys. Approval identity is a configured key ID, not an invented Kubernetes user attribution. Key custody and administrator identity mapping remain operating responsibilities. An approval may authorize the explicitly described rollback once after failed verification; it is not reusable for another action.

## Durable execution and concurrency

Action/status/audit and verified snapshots persist as Kubernetes custom resources in etcd. This provides restart survival and optimistic concurrency, not immutable external compliance storage. Status transitions record actor, state/reason and timestamp; spec links incident/policy/action/target. Kubernetes UID/resourceVersion and JSON Patch tests fence stale target mutations. Intent/attempt time is stored before changing the Deployment; crash recovery trusts only a matching action marker, template digest and replica count. An uncertain patch outcome or external edit produces a safety hold that blocks subsequent actions on that UID until an administrator investigates. It never repeats an uncertain mutation automatically.

Two controller replicas use a namespaced Lease; one active reconciliation serializes decision/budget checks. Leader-loss cancellation and bounded API/probe timeouts limit stale work. Independent changes use optimistic API preconditions, not blind merge patches. This is not a general transactional exactly-once guarantee across Kubernetes objects. Durable action markers and conservative holds provide at-most-one intentional attempt, with manual resolution of ambiguous outcomes. Execution attempts consume reserved budget even if the API result is uncertain. Automatic undo reserves two actions in advance; failures cannot create unbounded retry/rollback loops.

Action retention is capped operationally at 1000 records per namespace; the controller refuses new work above that count. Audit transition lists cap at 64. Administrators must export/archive records while retaining the full cooldown/budget horizon; deleting recent records weakens those guards. No operator RBAC deletion rights exist. CRDs have no owner-reference garbage collection, so workload deletion does not erase audit history. Back up etcd and export audit records before teardown.

## Recovery verification and rollback

Successful API patch is not successful recovery. Verification checks observed generation, exact expected template/replicas, updated/ready/available replica counts, no unavailable replicas, and repeated service SLI samples. The same-name ClusterIP service must select `app=deployment-name` and match pod labels. ExternalName/headless/redirects and arbitrary URLs are rejected. HTTP uses no proxy/redirect following, bounded reads and two-second requests. Network policy permits only API server CIDRs and opted-in workload probe ports.

Before/after samples record error count, requests and p95 milliseconds. Absolute error/latency SLOs and non-regression apply; relative latency uses a 20 ms baseline floor to avoid millisecond jitter dominating a healthy baseline. These sampled health/ready endpoints do not prove production application-wide Prometheus SLO compliance. Each success requires consecutive observations across reconciliation cycles. The poll interval is approximately five seconds plus probe/API duration.

A verified revision is captured only after all replicas are healthy and a service sample passes; the Deployment is re-read to ensure its generation did not change during sampling. Snapshot spec includes exact pod template/digest, workload UID and Deployment revision. Rollback accepts only a recent controller-certified snapshot for that UID; it is not an arbitrary ReplicaSet/image. This in-memory-template rollback restores configuration, not external/database state. Images with mutable tags can drift and must be digest-pinned before real use.

If restart/scale verification fails, undo is possible only with explicit policy enablement, signed rollback-inclusive approval, reserved second budget unit, unchanged policy, valid maintenance time, minimum availability and a fresh verified snapshot. Undo has its own intent, API preconditions and verification deadline. `RolledBack` means verified undo, not successful original recovery. Without those conditions—or if undo fails—the controller escalates and holds. Escalation destinations are durable routing references; external email/chat/pager delivery is not implemented and no external messages are sent.

## Failure modes and limits

API outages stop progress rather than authorizing actions. Lost approval keys mean no risky action; remove global execution as a kill switch. Full service outage, PDB/HPA/GitOps conflicts, unavailable spare capacity, startup faults, altered policy and target drift can prevent recovery. The operator does not delete pods, alter resource limits, mutate Services/Secrets, handle StatefulSets/DaemonSets, manage databases or override critical resources. PDBs do not constrain Deployment-controller rollouts; explicit maxUnavailable/min-availability guards are therefore required. HPA/GitOps writers can change generation and trigger conservative holds; coordinate ownership instead of fighting them.

RBAC cannot constrain the fields of an allowed Deployment patch; a compromised controller could alter more than its intended fields on those named workloads. Limit namespace/workload permissions, sign/scan images, review policy/key administration and add admission controls before production use. No public approval UI, external immutable audit sink, trusted key revocation service or production promotion is claimed.

The [installation/runbook](../runbooks/recovery-operator.md), [ADR](0006-recovery-operator.md) and [validation](../reports/phase-06-validation.md) define operating gates. Kubernetes references: [Deployment rollback](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#rolling-back-a-deployment), [Lease leadership](https://kubernetes.io/docs/concepts/architecture/leases/) and [CEL validation](https://kubernetes.io/docs/reference/using-api/cel/).
