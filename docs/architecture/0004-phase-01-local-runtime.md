# ADR 0004: Phase 01 local runtime and durable greeting work

Status: Accepted implementation | Date: 2026-11-02

## Context and decision

The Phase 01 scope includes real PostgreSQL persistence, Redis caching/background processing, migrations and a connected dashboard. A greeting job exercises these components without introducing cluster actions.

Use SQLAlchemy/Alembic over psycopg with PostgreSQL. Durable job rows are authoritative. Redis provides bounded wake-up hints and a 30-second cache for immutable completed results. An independent worker claims queued SQL rows with `FOR UPDATE SKIP LOCKED`, writes a deterministic greeting and commits. When Redis fails, SQL polling resumes work. This is a small demo queue, not a general broker or production task service.

Compose runs an explicit one-shot migrator after PostgreSQL is healthy, then starts API and worker; the dashboard waits for API readiness. Readiness checks the expected migration revision and both stores, while process liveness stays independent. Applications use non-root multi-stage images. A separate overlay supports hot reload. API inputs/settings and frontend response contracts are typed and validated; the browser uses an allowlisted same-origin server proxy and TanStack Query.

## Alternatives and consequences

FastAPI in-process background tasks are simpler but do not survive process termination. Redis-only queues make work recovery depend on Redis durability. A full task broker adds complexity for one deterministic action. SQL locking serializes ownership and supports restart recovery, but measured throughput and failure experiments are required before extending this model. Unit SQLite tests do not prove PostgreSQL lock behavior; container and migration tests are required acceptance evidence.

AuthN/AuthZ, durable audit export, arbitrary job execution, cluster telemetry and remediation remain out of scope. The local environment is unauthenticated and must stay on loopback. See the [verification record](../validation.md) for blocked real-service tests; design and implementation do not imply complete runtime verification.
