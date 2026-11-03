# Phase 07 validation

## Scope

Implemented the twelve-section operations UI, canvas-neutral design, authenticated typed read model, persistent preferences/reviews/audit/command outbox, scoped Kubernetes bridge, server-side role and version checks, signed approval transport, SSE reconnect/polling, bounded metrics/log queries and explicit synthetic demo mode. No AWS resources were created. Original LICENSE and ancestry are preserved.

## Local evidence

Windows, Node 24.14.1/npm 11.11.0, Python 3.12.4 and installed Microsoft Edge:

| Command | Observed result |
| --- | --- |
| `uv run pytest -m "not postgres" -q` | 57 passed, PostgreSQL test deselected |
| `npm run lint` | Passed |
| `npm run typecheck` | Passed |
| `npm test` | 16 passed, including namespace-safe evidence, read-only controls, encrypted flow-cookie integrity and same-origin checks |
| `npm run build` | Optimized Next.js build passed, including dynamic auth/proxy/section routes |
| `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` | Passed: Ruff check/format and strict mypy (61 source files) |
| `go -C operator test ./... -count=1`, `go -C operator vet ./...` | Passed with Go 1.26.8, including rejection-before-mutation regression |
| `PLAYWRIGHT_CHANNEL=msedge npm run test:e2e:operations` | Six flows passed in 36.8 seconds against explicit local SQLite preview and Next.js development server |
| `helm lint infrastructure/helm/kubesentinel` | Passed |
| `docker compose -f docker-compose.yml -f docker-compose.operations.yml config --quiet` | Passed configuration validation; engine startup unavailable |
| `kubeconform -strict -summary -kubernetes-version 1.35.0` on rendered operations chart and bridge RBAC | 23 valid resources, no errors or skipped schemas |
| `npm run check:lock`, Markdown/diagram/local-link checks | Passed; 60 Markdown files, 11 diagrams, original LICENSE verified |
| `helm template ... --set operations.enabled=true --set operations.approvalSecretName=sentinel-approver` | Rendered successfully |

The Playwright suite covers default real/empty mode, separate synthetic mode, all twelve views, search/dialog keyboard behavior, persistent preferences, cost calculation, demo decision audit, server-side viewer denial, CSRF rejection, controlled API outage/recovery, and desktop/tablet/mobile. Axe WCAG A/AA checks run across all twelve views and all three viewport sizes. Responsive screenshots are actual browser captures of **synthetic fixtures**, not a live cluster. The suite checks no horizontal document overflow, reduced motion and a 12 MB development transfer ceiling; this is not a Lighthouse score or production latency benchmark.

- [Desktop capture](../screenshots/phase-07/desktop.png)
- [Tablet capture](../screenshots/phase-07/tablet.png)
- [Mobile capture](../screenshots/phase-07/mobile.png)

## Production-browser evidence

Runtime source: `024ee9c6cd31e154e2d906e687ac7ae523a9252c`. The [actual browser job](https://github.com/manikantbindass/KubeSentinel-AI/actions/runs/41607540612/job/125821029497) passed all six flows in 27.93 seconds against the production Next.js build and the real PostgreSQL 17.10/Redis 8.2.2 API. There were no skipped, unexpected or flaky tests. [Archived results](phase-07/browser-results.json) contain source provenance and observed test results. The committed responsive screenshots are from this CI run and show explicitly synthetic fixtures persisted through the real API; they are not screenshots of genuine cluster telemetry.

The first production-browser attempt caught a real changed-preference feedback bug. Saving a new polling interval remounted the form and removed its success message. The form now mounts after initial preferences load, remains mounted after a save, and the E2E test resets the prior value to ensure a genuine change is exercised.

## CI and acceptance boundaries

The Operations dashboard workflow starts the actual migrated PostgreSQL/Redis FastAPI application and production Next.js build for the same browser suite. Its separate disposable kind job checks real collection, denied Deployment/pod/Secret privileges, API rejection, Python-signed plan approval accepted by the Go operator, scale recovery, verification and durable command evidence. All 16 checks passed for runtime source `024ee9c6cd31e154e2d906e687ac7ae523a9252c`: [archived check links and results](phase-07/checks.json). The [real kind evidence](phase-07/cluster-results.json) records 80 collected resources, a rejected action, and an approved scale action reaching `Succeeded` with four available replicas. Container startup, database migration round-trip, local Kubernetes, operator recovery, observability ingestion and ML reproducibility checks also passed in Linux CI. This evidence-only documentation follow-up does not change runtime code; its own newly triggered checks are separate. The existing migration round-trip job now checks revision `0004_operations` and its snapshot table. No unauthenticated public telemetry or fabricated cluster screenshot is substituted for this evidence.

Local Docker startup remains blocked: the Windows Docker Desktop engine pipe is unavailable. Therefore local PostgreSQL/Redis/container/kind acceptance is not claimed. OIDC signature/claim checks and BFF cryptographic/CSRF behavior have automated tests, but no live enterprise identity-provider tenant has been certified. Review issuer/client configuration and externally exposed legacy routes before deployment.

Remaining product limits: no OIDC refresh/opaque-token introspection, no per-user namespace claims, no container exec/terminal, bounded inventory, no automatic audit retention/immutable sink, single logical bridge worker, no external cloud billing integration, no independent live false-positive measurement or causal root-cause model. Raw pod logs require Loki metadata collection. All empty/offline/unconfigured states disclose the missing source.
