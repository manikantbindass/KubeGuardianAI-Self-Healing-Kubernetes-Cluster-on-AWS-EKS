# ADR 0007: Authenticated operations read model and command outbox

- Status: accepted for local Phase 07; production identity review remains required
- Date: 2026-11-03

## Context

The operations UI needs actual inventory and durable incidents without giving browser sessions Kubernetes credentials or allowing scores to mutate workloads. Cluster and telemetry outages must remain visible. The earlier hello-world dashboard must stay available for existing smoke tests.

## Decision

Use a same-origin Next.js backend-for-frontend with HttpOnly token cookies, OIDC code/PKCE and an independently validating FastAPI API. Use PostgreSQL for redacted snapshots, per-user preferences, review notes, command outbox and audit. Redis limits user mutations atomically. A separately credentialed, namespace-scoped Kubernetes bridge mirrors resources and delivers only version-fenced CRD decisions. The existing Go operator remains the sole Deployment mutation authority and verifies signed approvals and all policy constraints.

SSE carries durable change cursors and triggers typed TanStack Query refreshes. Polling remains the fallback. Streams reconnect periodically so authorization is rechecked. Fixed Prometheus/Loki queries bound scope, time, response bytes and timeout. Synthetic fixtures use a different mode partition, require explicit enablement, and never replace failed real sources.

The overview's canvas, gallery and recovery toolkit are a visual presentation of selected records. Illustrative geometry has no invented topology semantics. Metrics, model evaluation, cost and root-cause language distinguish measured evidence from uncalibrated scores, heuristics and user-entered scenarios.

## Consequences

The UI/API have no Deployment mutation RBAC. Compromising an approver session can authorize plans within the operator's independent limits; compromising the API signing key is therefore material. Store/mount it separately, restrict approver membership, rotate trust explicitly and retain operator plus API audits. Database audit is durable but not immutable or externally anchored.

The bridge is currently a single logical delivery worker without distributed claims. Commands expire after five minutes and compare live object versions; failures may require manual review. Reads are bounded (100 objects/kind/namespace per collection and 1000 resources per view), and wider clusters need server-side paging, capacity testing and retention automation. OIDC refresh, opaque tokens, per-user namespace grants and a live provider certification are follow-up gates.

## Alternatives

Direct browser Kubernetes access exposes credentials and duplicates safety checks. Next.js-only authorization gives no independent API boundary. WebSockets add bidirectional session state where one-way invalidation is enough. A broker/event bus offers scale but adds local operational cost; PostgreSQL outbox plus existing Redis is adequate for this bounded slice. A hosted art-platform template would abandon repository-based functionality; use code-native SVG/CSS artwork and the existing shadcn components instead.
