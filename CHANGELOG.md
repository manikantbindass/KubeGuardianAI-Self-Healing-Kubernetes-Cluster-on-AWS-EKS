# Changelog

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
