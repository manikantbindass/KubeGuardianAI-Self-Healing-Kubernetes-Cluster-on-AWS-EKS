# ADR 0002: Durable state and safe execution

Status: Accepted design | Date: 2026-11-02

## Decision

PostgreSQL owns incidents, policy versions, approvals, action state, transactional outbox, and audit index. Redis owns only bounded transient caches/coordination/delivery hints. Recover pending work from SQL after Redis loss. Retention and schema/migration choices require implementation-phase evidence.

Separate anomaly evidence, proposal generation, policy authorization, human approval, and operator execution. Default deny; no new execution on unavailable policy/audit state. Bind approvals to immutable content, policy version, scope, target identity, and expiry. Revalidate at execution. Use durable intent, unique action IDs, Kubernetes preconditions, idempotent reconciliation, budgets, cooldowns, verification, and bounded rollback/escalation. Initial mode is disabled, then dry-run; activation requires operator acceptance gates.

## Alternatives and consequences

Redis-only authorization risks loss of durable approvals. A separate message broker may become useful at higher volume but is not justified yet. Direct remediation from an API or model collapses the privilege boundary and is rejected. SQL transactions and an independent operator add coordination work; at-least-once delivery still requires idempotency and cannot guarantee exactly-once external effects. Immutable audit export and restore tests are prerequisites for production, not existing controls.
