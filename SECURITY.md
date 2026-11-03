# Security policy

## Status and reporting

The repository remains a development platform, not a production release. Phase 07 operations routes validate OIDC/local development credentials and server-side roles; legacy greeting/health and ingestion routes retain their documented public or token contracts. See the [operations trust boundaries](docs/architecture/0007-operations-read-model.md). Do not expose the API, dashboard, PostgreSQL, or Redis publicly. Compose publishes only loopback ports. The example database password is deliberately local-only. Security fixes target the latest `main`; no response SLA is established.

Use GitHub **Security > Report a vulnerability** if private reporting is enabled. Otherwise contact the owner through a private channel they publish on their GitHub profile and request a reporting channel. Do not publish exploit details, credentials, or sensitive logs in public issues. Private reporting availability has not been verified; enabling it is a maintainer follow-up.

## Design requirements

The [threat model](docs/security/threat-model.md) defines planned OIDC, scoped RBAC, tenant/cluster isolation, encryption, secret references, redaction, audit export, supply-chain verification, and least-privilege operator permissions. OIDC-compatible operations access, scoped bridge RBAC, guarded operator execution and durable local audit are implemented in their respective slices. Tenant isolation, live provider certification, immutable audit export and production promotion remain future gates. Current controls include typed input/configuration, explicit CORS allowlists, bounded store/proxy connection timeouts, sanitized errors with correlation IDs, and non-root application images. The dashboard proxy only forwards allowlisted routes to a trusted server-side base URL.

Recovery begins disabled and in dry-run mode. Execution requires default-deny policy, action/namespace allowlists, approval, expiry, idempotency, cooldowns, budgets, verification, and rollback/failure paths. Recheck authorization at execution. Telemetry, predictions, prompts, and assistant output cannot directly authorize a Kubernetes action.

Never commit `.env`, credentials, kubeconfig, Terraform state, cloud keys, or raw production telemetry. Ignore patterns are not a secret scanner. Review diffs before pushing. Dependencies require pins and lockfiles; add image/software scans and signed artifacts before production. No AWS or Kubernetes resources are provisioned in Phase 00.

## Operations identity and signing keys

Use trusted HTTPS issuer/JWKS endpoints, explicit audience/roles, exact external origin and secure cookies. Development authentication is forbidden outside `APP_ENV=local`. Do not expose the local preview server. Approver membership and API signing-key custody are security-sensitive: an approved API request can sign a plan within the independently checked operator policy. Keep the private key API-only, trust its public key explicitly, rotate/revoke key IDs deliberately and retain both API and operator audit evidence. Demo mode is separately enabled and never dispatches cluster commands.

Kubernetes events and queried application logs may include sensitive text; redact at collection and restrict viewer membership. The API has no arbitrary PromQL/LogQL/URL proxy. Redis outages disable operational mutations. Snapshot bounds and timeouts do not replace gateway denial-of-service controls. See the [deployment and limitations guide](docs/runbooks/operations-dashboard.md) before any external exposure.

## Delivery controls

See [secure delivery](docs/runbooks/secure-delivery.md) for read-only PR jobs, source-bound ECR OIDC release signing, protected environments, main-only subject constraints, scoped promotion tokens, expiry-enforced exceptions and manual Argo sync. Seven proposed cost/static-analysis Terraform exceptions expire 2026-12-03; review [issue #10](https://github.com/manikantbindass/KubeSentinel-AI/issues/10) before enabling delivery. Secret findings and unsigned/unverified releases must block promotion. No live cloud delivery has been certified.
