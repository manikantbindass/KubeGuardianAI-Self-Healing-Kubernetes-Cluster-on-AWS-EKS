# System overview

Status: target architecture accepted as the Phase 00 design baseline on 2026-11-02. Phase 01 now implements the local dashboard, API, greeting worker, PostgreSQL schema/migration, and Redis cache/wake-ups; see the [local service diagram](../diagrams/local-services.mmd) and [verification record](../validation.md). Later phases add local cluster orchestration, telemetry/incidents, advisory detection, the guarded recovery operator and the [authenticated operations read model](0007-operations-read-model.md). The [Phase 07 guide](../runbooks/operations-dashboard.md) and phase validation records distinguish shipped slices from the remaining target architecture. Notifications, broader correlation, immutable audit export, live identity-provider certification, GitOps promotion and cloud deployment remain future gates. Significant changes require an ADR.

## Purpose and scope

KubeSentinel AI will help operators understand Kubernetes incidents, propose bounded remediation, and verify approved actions. AWS EKS is an eventual deployment target, not a dependency for development. Detection provides evidence; policy grants authority; the operator performs narrowly scoped execution. Human operators remain able to deny, stop, or override automated actions.

## C4 views

The editable Mermaid sources describe the **target**, not deployed resources. They use Mermaid flowcharts with explicit C4 people, systems, containers, and components, avoiding a renderer-specific C4 extension.

- [C4 context](../diagrams/c4-context.mmd): people and external systems.
- [C4 container](../diagrams/c4-container.mmd): deployable processes and stores.
- [C4 component](../diagrams/c4-component.mmd): backend internals and execution boundary.
- [Remediation sequence](../diagrams/remediation-sequence.mmd): authorization, execution, audit, and verification.

A C4 container is a process/store boundary, not a promise of one Docker service per directory. Early Python components can share a process; extraction requires measured scaling, ownership, or isolation needs. The operator remains an independent privilege boundary.

## Technology choices and alternatives

| Area | Proposed choice and rationale | Reasonable alternative / decision trigger |
| --- | --- | --- |
| Web frontend | Next.js, TypeScript strict mode, Tailwind; typed UI, server-side API mediation, accessible incident views | React/Vite for a simpler SPA if SSR/server routes provide no value |
| Backend / gateway | FastAPI with Pydantic/OpenAPI; Python matches ML tooling and supports explicit contracts; ingress handles TLS/routing | Go for measured CPU/concurrency needs; separate gateway only when multiple external APIs justify it |
| Authentication | OIDC authorization-code flow with PKCE through a maintained library/provider; secure HttpOnly session cookie at web boundary | Managed Cognito for AWS operations; Keycloak for local/self-hosted control; select provider in Phase 02 ADR |
| Authorization | Backend RBAC plus cluster/namespace/action scopes; policy engine and operator independently recheck execution permission | External OPA/Cedar if policy complexity or organization standards justify it; not required for Phase 01 |
| Telemetry | OpenTelemetry Collector for normalization; Prometheus metrics, Kubernetes events, redacted logs | Managed ADOT/CloudWatch where operational burden outweighs cost; avoid duplicate ingestion |
| Metrics / logs / events | Prometheus for local metric windows, Loki for redacted logs, PostgreSQL for normalized incident/event metadata; S3-compatible object archive later | Managed Prometheus/Grafana or CloudWatch; object archive for high-volume events rather than unbounded SQL rows |
| Durable state | PostgreSQL for incidents, policy versions, approvals, action state, transactional outbox, audit index; migrations before first persistent feature | Managed RDS on AWS; SQLite only for isolated test fixtures, not equivalent concurrency/production evidence |
| Transient state | Redis for bounded caches, rate limits, deduplication hints, stream delivery acceleration | PostgreSQL queue/outbox alone initially; a separate broker only after throughput/backpressure measurement |
| Detection | Python baseline thresholds/statistics before scikit-learn models; deterministic windows, versioned features and models | PyTorch only for an experimentally justified model; rules may remain preferable on sparse labels |
| Correlation | Deterministic topology/time grouping and deduplication; evidence-linked incident state | Graph store only if relational queries cannot meet measured requirements |
| Remediation policy | Typed proposals and default-deny rules; narrow allowlists, budgets, expiry, approvals | OPA policies after an ADR; no LLM-based authorization |
| Kubernetes operator | Go with controller-runtime/Kubebuilder, versioned CRDs, reconciliation and scoped RBAC | Python operator framework for prototype speed; choose Go for established controller patterns and independent execution boundary |
| Notification / audit | Outbox-driven notifications with adapter contracts; audit events committed with state and exported to immutable storage | Managed SNS/SES or webhook adapters when destinations/consent are defined; no destination credentials in source |
| Infrastructure | Terraform modules/environments, EKS, private worker networking, managed PostgreSQL/Redis options, workload identity | Local kind first; k3d alternative; CDK/Pulumi if team skills justify a different IaC ADR |
| GitOps / CI | GitHub Actions validates/builds; Helm packages; Argo CD reconciles reviewed image digests | Flux for a smaller GitOps controller; Actions must not hold long-lived cluster-admin credentials |

Node 24 and Python 3.12 are the Phase 01 toolchains, with explicit application pins and npm/uv locks. Compose pins PostgreSQL 17.10 and Redis 8.2.2 images. Go/operator, collectors, charts, Terraform/providers, and models require version selection before implementation. Redis licensing and managed offerings require deployment-specific review; no blanket licensing claim is made here.

## Data flow

1. An operator signs in through OIDC. The backend validates session/token issuer, audience, expiry, and role/scope mapping. The browser receives no cluster credentials. State-changing cookie-authenticated requests need CSRF protection and origin checks.
2. A scoped collector reads cluster telemetry, labels provenance/UTC event time/schema version, redacts sensitive fields, and submits authenticated batches. Limit payload size, label cardinality, tenant scope, and ingestion rate before persistence.
3. Prometheus/Loki retain time-series/log data under explicit retention. PostgreSQL stores normalized event pointers and durable business state. Feature windows use event-time rules and a bounded late-arrival policy. Raw telemetry is untrusted evidence.
4. Detection emits a score, model/feature version, threshold, confidence/limitations, and evidence references. Correlation deduplicates signals into incident lifecycle states. A prediction is not permission to act.
5. Recovery creates a typed proposal. Policy evaluates workload scope, action allowlist, risk, budgets, cooldown, current health, and approval requirements. Persist proposal, policy version, decision, and audit/outbox entries in one SQL transaction.
6. A human approves where required. The approved content hash, identity, role, scope, policy version, and expiry bind the authorization. Any edit, expiry, changed policy, or stale target invalidates approval.
7. The operator obtains an approved remediation CR with a unique action ID. It validates scope and policy/approval proof, rechecks target UID/resourceVersion and preconditions, and reconciles one allowlisted action. API/policy unavailability denies new execution. Kubernetes RBAC also constrains the action.
8. Verification checks postconditions within a bounded deadline. Record success, failed verification, timeout, or rollback. A rollback is another scoped action, not a blanket privilege. Exhausted budgets or ambiguous state stop automation and escalate.
9. Notification consumes durable outbox events with retry/backoff and deduplication. Delivery failure cannot erase audit history or cause action replay. The dashboard reads incidents and receives authorized SSE updates; reconnect uses cursor-based recovery, bounded buffers, and polling fallback.
10. An optional assistant retrieves redacted evidence/runbooks, cites sources, and expresses uncertainty. It cannot approve or execute remediation. Provider egress and retention need privacy review.

## Service interfaces (proposed, not endpoints currently available)

| Producer → consumer | Contract | Delivery / access |
| --- | --- | --- |
| Browser → backend | Versioned REST `/api/v1/incidents`, `/proposals`, `/approvals`; SSE `/events` | TLS, validated session, RBAC, CSRF for mutation, cursor pagination |
| Collector → ingestion | `/internal/v1/telemetry/batches`: schema, provenance, cluster/tenant, UTC times, payload limits | Workload identity/mTLS, idempotent batch key, 429/backoff, bounded buffering |
| Detector → correlator | `anomaly.v1`: score, window, feature/model version, evidence IDs | Durable outbox; at-least-once delivery, idempotent consumers |
| Correlator → policy/recovery | `incident.v1` and `proposal.v1`: incident, action enum, target UID, preconditions, rollback plan | SQL transaction/outbox, schema validation, no arbitrary shell commands |
| Approval/policy → operator | Proposed `RemediationRequest` CR, version initially `v1alpha1`: action ID, scope, approved content digest, expiry; status conditions | Operator-scoped Kubernetes API, admission/schema validation, default deny, recheck before execution |
| Operator → backend/audit | `action-result.v1`: action ID, observed target version, timestamps, result, verification and rollback | Authenticated callback or CR watch adapter; durable retry and deduplication |
| Outbox → notification | `notification.v1`: incident/action reference, recipient routing key, redacted summary | Approved destinations, signed webhooks where applicable, delivery ID, retry/dead-letter |
| All stateful components → audit | Actor, action, decision, policy version, evidence IDs, correlation ID, UTC time | Durable append-only application contract, restricted DB role, immutable export; tamper detection before production |

Common envelope: `schema_version`, `event_id`, `occurred_at`, `received_at`, `tenant_id`, `cluster_id`, `namespace`, workload UID, `correlation_id`, and provenance. Enforce tenant scope using trusted identity mapping, never just a submitted field. Requests use explicit timeouts, body limits, stable error codes, pagination, and redacted structured logs. Version breaking changes and keep OpenAPI/event/CRD compatibility fixtures.

Redis is not the source of truth for approvals, policy, action state, or audit. Use a PostgreSQL outbox for durable work; stream consumers acknowledge only after durable processing. Recover pending work from SQL after Redis loss. At-least-once processing requires idempotency; do not promise exactly-once Kubernetes side effects. A SQL uniqueness constraint and operator reconciliation bound duplicates.

## Trust boundaries and access

| Boundary | Required controls before activation |
| --- | --- |
| Internet/browser → edge/web | TLS, rate limits, secure headers, session hardening, CSRF/origin checks, no internal addresses/tokens in errors |
| Web/backend → identity provider | Issuer/audience/signature validation, JWKS cache/rotation, short session lifetime; no implicit trust of role claims without mapping |
| Cluster telemetry → control plane | Read-only collector RBAC, workload identity/mTLS, redaction, schema/cardinality limits; no execution credentials |
| Control plane → stores | Per-service identities, namespace/tenant filtering, TLS, secret references, backup/restore, restricted audit writes |
| Policy/approval → operator | Narrow action contract, default deny, bound approval, target preconditions, independent revalidation, RBAC and admission controls |
| CI/GitOps → cluster | Protected review, build attestations/digests, short-lived cloud OIDC, scoped Argo CD projects; no Docker socket or cluster-admin in apps |
| Evidence → assistant/provider | Treat content as data; strip secrets; allowed egress; citations; no approval or execution tools |

Initial application phases may be single-tenant but must retain cluster/tenant identity in schemas. Multi-tenant production requires explicit isolation tests and an ADR for PostgreSQL row-level security versus separate stores. Cloud IAM, Kubernetes RBAC, and product roles are distinct authorization layers.

## Failure modes and safe behavior

| Failure | Required response |
| --- | --- |
| API unavailable | UI displays stale/unavailable state; bounded retries with jitter; no inferred healthy status |
| Identity provider/JWKS unavailable | Existing validated sessions only within explicit TTL policy; deny new authentication/unknown keys; never bypass validation |
| Telemetry late/missing/noisy | Mark evidence stale, expose ingestion lag, suppress unsafe remediation, cap cardinality and buffering |
| Detector unavailable or model drift | Fall back to a declared advisory baseline or disable scoring; show model/version gaps |
| PostgreSQL unavailable | Reject durable mutations/approvals/new actions; no approval from cache; alert and recover via tested backup strategy |
| Redis lost/partitioned | Rebuild transient work from SQL; deny actions needing unavailable coordination; no loss of durable authorization |
| Policy/approval stale or unreachable | Deny new execution; require refreshed approval; retain inspectable reason |
| Operator restarts or request duplicated | Reconcile by action ID and observed cluster state; never blindly replay a destructive operation |
| Kubernetes action times out | State becomes unknown pending observation; verify before retry; bounded rollback/escalation |
| Audit persistence fails | Fail closed before side effects; for an already-started action retain durable intent and reconcile outcome after recovery |
| Notification/provider unavailable | Retry/dead-letter with redacted summaries; UI/audit remain authoritative; no action replay |
| GitOps detects manual drift | Alert/reconcile reviewed desired state; remediation must not fight GitOps; action types must define ownership and escalation |

## Deployment environments

| Environment | Purpose / restrictions |
| --- | --- |
| Phase 00 workstation / CI | Docs and checks only; no runtime secrets, containers, clusters, or AWS |
| Phase 01 local native / Compose | Dashboard + API health vertical slice; loopback ports, non-root Linux containers; no auth or real cluster implied |
| CI integration | Ephemeral containers/local kind cluster when needed; deterministic fixtures, no production credentials; cloud tests require separate explicit gates |
| Local cluster lab | Isolated namespaces, resource limits, seeded demo faults; dry-run policy and operator tests before any execution |
| Staging EKS (future, separately authorized) | Dedicated account/environment/state, synthetic workloads, budgets, controlled egress, restricted access, teardown proof |
| Production EKS (future) | Multi-AZ design, SLOs, backup/restore, disaster recovery, strict promotion/rollback, security/cost review and on-call ownership |

No SLO values, capacity, performance, or recovery success rates have been measured. Choose thresholds from experiments and document them before activation. Persistence topology, RPO/RTO, retention, and workload sizing are Phase 03/05/10 decisions, not fabricated guarantees.

## Source references

- [Kubernetes controller model](https://kubernetes.io/docs/concepts/architecture/controller/) supports reconciliation against desired state.
- [Redis Streams](https://redis.io/docs/latest/develop/data-types/streams/) documents consumer groups; durable business state remains in PostgreSQL by this project's decision.
- [EKS pricing guidance](https://docs.aws.amazon.com/eks/latest/userguide/eks-pricing.html) informs the separate cost review. No price is asserted here.

Technology selections, controls, interfaces, and decomposition above are project design decisions, not claims made by those references or existing functionality.
