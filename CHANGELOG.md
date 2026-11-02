# Changelog

## Unreleased - Phase 03

- Add pinned Terraform/AWS provider configuration and Windows/Linux provider locks, reusable VPC/EKS/IAM/ECR/logging/Pod Identity/DNS modules, dev/demo profiles and separate S3/KMS state bootstrap.
- Define private nodes/API defaults, scoped access entries, repository-and-branch-bound GitHub OIDC publishing, encryption, retention, explicit AMI/add-on pins and configurable NAT/endpoint tradeoffs.
- Add synthetic provider-mocked guardrail tests and static-only CI; no AWS credentials, apply, destroy or live plan.
- Add module reference, state/deployment/rollback/teardown runbooks, cost model and local/cloud matrix. Expose controlled Helm CORS/network overrides and skip platform-owned RBAC in cloud profiles.

## Unreleased - Phase 02

- Add kind configuration, cross-platform lifecycle/build/scan scripts, Helm local/dev/prod profiles, migration Jobs, service discovery, PVC-backed local stores, namespace policy, scoped RBAC, network isolation, resources, probes, optional API PDB/HPA and ingress templates.
- Add worker heartbeat probes and numeric non-root application image users.
- Add Kubernetes schema/lint/deployment/scan CI and orchestration runbook/diagram. Local live tests remain blocked by an unavailable Docker engine; no AWS resources created.
- Add animated, locally maintained SVG banners at the README top and bottom.

## 0.1.0 - Phase 01 (2026-11-02)

- Add versioned FastAPI health/readiness/version APIs, typed Pydantic settings/schemas, structured JSON request logging, correlation IDs, sanitized exception handling, CORS, and OpenAPI.
- Add SQLAlchemy models, Alembic migration, durable greeting jobs, Redis completed-result cache/wake-ups, and a SQL-backed worker with Redis-outage fallback.
- Add Next.js App Router dashboard, TypeScript, Tailwind, shadcn-style reusable components, TanStack Query, connectivity/readiness and greeting views, accessible loading/error/offline/empty states.
- Add multi-stage non-root app images, PostgreSQL/Redis Compose, one-shot migration dependency, hot reload overlay, Make targets, locked dependencies, backend/frontend/migration/smoke checks, and CI.

## Phase 00 foundation (included)

- Audit the original repository; preserve its Apache 2.0 LICENSE and single-commit ancestry.
- Establish component boundaries, branch/commit standards, policies, editor/ignore settings, issue/PR templates, and documentation CI.
- Document C4 context/container/component views, service contracts, trust boundaries, failure modes, environments, and technology alternatives.
- Add roadmap, development guide, threat model, cost considerations, ADRs/template, and manual rename steps.
- Add locked Markdown/Mermaid tooling, repository validation, and tests for the validator.

Cluster telemetry, anomaly models, Kubernetes controllers, remediation, identity, and cloud provisioning are not implemented.
