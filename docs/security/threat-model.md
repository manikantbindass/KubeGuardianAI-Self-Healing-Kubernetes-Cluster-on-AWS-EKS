# Threat model

Status: Phase 00 design analysis. Controls below are **required future work**, not implemented protections. Revisit per phase and before connecting any cluster or external provider.

## Assets, actors, and assumptions

Protect cluster availability, workload data, credentials, policy/approval integrity, incident evidence, audit history, model/dataset lineage, and cloud spend. Actors include authorized responders/approvers, tenant users, malicious external users, compromised workloads/collectors, compromised CI/dependencies, and insiders with excessive permissions.

Assume telemetry and retrieved documents can be malicious or stale, clients can forge scope fields, queues can replay messages, networks can partition, and a service can be compromised. Cloud IAM, product authorization, and Kubernetes RBAC are distinct. A single-tenant prototype does not prove multi-tenant isolation.

## Threats and required controls

| Boundary / threat | Impact | Required mitigation and acceptance evidence |
| --- | --- | --- |
| Browser spoofing / stolen sessions | Unauthorized incident access or action request | OIDC signature/issuer/audience/expiry validation, PKCE, secure HttpOnly SameSite cookies, session expiry/revocation; invalid-token and session tests |
| Cookie request forgery / UI injection | Forged approval or credential theft | CSRF/origin checks, output escaping, CSP, no raw telemetry HTML; mutation and XSS fixtures |
| Scope/role tampering | Cross-tenant or cross-cluster access | Trusted identity-to-scope mapping, object-level authorization on every REST/SSE path, policy and operator recheck; isolation matrix tests |
| Collector compromise / telemetry poisoning | False diagnoses, data exfiltration | Read-only collector RBAC, workload identity/mTLS, redaction, provenance, payload/cardinality/rate limits; forged/malformed/stale event tests |
| Unsafe remediation / approval replay | Cluster disruption and privilege escalation | Default deny, immutable approval digest, expiry, target UID/resourceVersion, allowlists, budgets, cooldowns, kill switch, idempotency; stale/duplicate/denial tests |
| Policy or database outage | Execution without authority or missing history | Fail closed before side effects, durable intent/outbox, no Redis-only authority, reconcile unknown results; partition/restart tests |
| Audit tampering / repudiation | Hidden unauthorized actions | Least-privilege append-only application role, actor/policy/evidence lineage, immutable export/tamper detection; modification denial and restore tests |
| Queue duplication / notification injection | Duplicate actions or leaked incident data | SQL action uniqueness, idempotent consumers, approved destinations, signed callbacks, redacted summaries, bounded retries; replay/SSRF tests |
| Secret or personal data exposure | Credential compromise / privacy harm | Secret references and rotation, encrypted transport/storage, bounded retention, field redaction, access logs; secret scanning and deletion/export tests |
| Dependency / CI / GitOps compromise | Malicious images or broad cluster access | Protected review, lockfiles, vulnerability gates, SBOM, signatures/attestations, short-lived OIDC, scoped Argo CD; provenance/admission tests |
| Model poisoning / drift / leakage | Misleading incident scores | Provenance, immutable dataset hashes, temporal/lineage splits, baseline comparison, drift alarms, rollback; reproducibility and adversarial fixtures |
| Assistant prompt injection | Disclosure or fabricated action advice | Treat retrieved text as data, redact egress, citations/uncertainty, no execution tools, provider privacy review; injection/grounding evaluations |
| Resource exhaustion / cloud cost abuse | Availability loss and unexpected bills | Ingress/queue/storage quotas, backpressure, bounded work, retention, budgets/alerts; load tests and cost review |

## Remediation safety invariants

1. No prediction, event, prompt, or assistant output grants permission.
2. Every action is allowlisted, scoped, expiring, uniquely identified, and auditable before execution.
3. Approval binds immutable content and current policy; editing or expiry invalidates it.
4. Authorization/policy/audit failure denies new execution. Partial or unknown effects trigger observation before retry.
5. Verification, bounded rollback, escalation, and a stop mechanism accompany activation.
6. Recovery cannot mutate its own permissions or policy to expand authority.

## Residual risks and review gates

Compromised cluster administrators or cloud administrators can bypass product controls; isolate roles and audit externally. Immutable storage does not guarantee truthful initial evidence. Human approval can be mistaken. Rollback may be impossible for some actions, which must remain disabled until explicitly reviewed. Model confidence is not a safety guarantee.

Open decisions: identity provider, tenant isolation model, secret manager/KMS policy, audit retention/immutability, data residency, RPO/RTO, and allowed action catalog. Each needs an ADR, named owner during implementation review, and linked tests before production. See [SECURITY](../../SECURITY.md) for private reporting and [architecture](../architecture/system-overview.md) for trust boundaries.
