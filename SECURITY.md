# Security policy

## Status and reporting

Phase 01 is an unauthenticated local development environment, not a production release. Do not expose the API, dashboard, PostgreSQL, or Redis publicly. Compose publishes only loopback ports. The example database password is deliberately local-only. Security fixes target the latest `main`; no response SLA is established.

Use GitHub **Security > Report a vulnerability** if private reporting is enabled. Otherwise contact the owner through a private channel they publish on their GitHub profile and request a reporting channel. Do not publish exploit details, credentials, or sensitive logs in public issues. Private reporting availability has not been verified; enabling it is a maintainer follow-up.

## Design requirements

The [threat model](docs/security/threat-model.md) defines planned OIDC, scoped RBAC, tenant/cluster isolation, encryption, secret references, redaction, audit export, supply-chain verification, and least-privilege operator permissions. These controls remain future work. Current controls include typed input/configuration, explicit CORS allowlists, bounded store/proxy connection timeouts, sanitized errors with correlation IDs, and non-root application images. The dashboard proxy only forwards allowlisted routes to a trusted server-side base URL.

Recovery begins disabled and in dry-run mode. Execution requires default-deny policy, action/namespace allowlists, approval, expiry, idempotency, cooldowns, budgets, verification, and rollback/failure paths. Recheck authorization at execution. Telemetry, predictions, prompts, and assistant output cannot directly authorize a Kubernetes action.

Never commit `.env`, credentials, kubeconfig, Terraform state, cloud keys, or raw production telemetry. Ignore patterns are not a secret scanner. Review diffs before pushing. Dependencies require pins and lockfiles; add image/software scans and signed artifacts before production. No AWS or Kubernetes resources are provisioned in Phase 00.
