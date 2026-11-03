# Operations dashboard

Phase 07 delivers a Next.js operations workspace backed by the FastAPI read model. Its twelve routes cover inventory, metrics, anomaly evidence, incidents, recovery, policies, insights, audit, cost scenarios and preferences. The canvas-neutral overview contains an illustrative cluster visualization, collected workload gallery and recovery toolkit. Geometry is artwork, not a discovered network topology. All controls navigate, inspect, query, export or perform an authorized API operation.

Real mode is the default, including deployments. Synthetic mode is a separate, explicitly enabled fixture partition. Missing telemetry stays empty/offline; it never switches to synthetic data. The public Phase 01 greeting/health surface is retained at `/status`.

## Prerequisites

Use the pinned Node/npm/Python/uv versions in the root README. Docker Desktop must use Linux containers on Windows/macOS; Linux needs Docker Engine and Compose v2. Native development needs PostgreSQL and Redis. Kubernetes collection additionally needs kubectl, the optional Python `ops` dependency group and an explicitly selected cluster context. No AWS resources are required.

## Windows PowerShell

```powershell
Copy-Item .env.example .env
npm ci
uv sync --frozen --extra ops
uv run python scripts/setup/operations_env.py --development --demo
docker compose -f docker-compose.yml -f docker-compose.operations.yml up --build --wait --wait-timeout 180
uv run python scripts/seed_operations_demo.py
```

Open `http://localhost:3000`. Enter the `OPS_DEV_TOKEN` from your ignored `.env` in the password field. Use `OPS_DEV_VIEWER_TOKEN` to check read-only access. Select **Synthetic demo** explicitly to view fixtures. A fresh configuration without `--demo` keeps the selector unavailable; set `OPS_DEMO_ENABLED=false` to disable an already enabled fixture partition. Keep tokens and signing keys out of issues, recordings and screenshots.

## Linux/macOS

```sh
cp .env.example .env
npm ci
uv sync --frozen --extra ops
uv run python scripts/setup/operations_env.py --development --demo
docker compose -f docker-compose.yml -f docker-compose.operations.yml up --build --wait --wait-timeout 180
uv run python scripts/seed_operations_demo.py
```

The generated signing key is mode 0600. The local Compose override runs the API as its unprivileged native owner using generated `OPS_RUNTIME_UID/GID`; never set UID 0. If running setup as root, configure an unprivileged key owner explicitly. Windows Docker bind mounts use host ACLs; restrict `.cache/operations` to your development account. The operator must separately trust the generated public key before approvals can execute. Generating a key does not enable execution.

## Native hot reload

Start backing stores with `docker compose up -d postgres redis`, then:

```sh
uv run alembic -c apps/api/alembic.ini upgrade head
uv run uvicorn kubesentinel_api.main:app --app-dir apps/api --reload --host 127.0.0.1 --port 8000 --no-access-log
```

In another terminal, `uv run python scripts/setup/run_operations_dashboard.py --port 4317` starts Next.js with root `.env` loaded and a matching trusted origin. Open `http://127.0.0.1:4317`. This launcher works in PowerShell, bash and zsh; no shell-specific environment syntax is required. Port 4317 avoids Windows reserved port ranges that can cause EACCES on port 3000.

For explicitly synthetic UI development without Docker, run `uv run python scripts/operations_preview.py` instead of the real API. It requires explicit local development authentication, uses SQLite and a test-only process limiter, and seeds only demo records. **This preview does not validate PostgreSQL, Redis, cluster connectivity or production readiness.** Do not deploy it.

## Actual Kubernetes data

The bridge collects bounded node, pod, deployment, event, action and policy snapshots into PostgreSQL. It sends no credentials, environment values, Secret objects or deployment templates to the browser. Run one bridge instance; duplicate deliveries are fenced/idempotent but distributed command claiming is not implemented.

For the isolated lab, first follow [operator installation](recovery-operator.md). Then:

```sh
kubectl --context kind-kubesentinel-recovery apply -f infrastructure/kubernetes/operations/bridge-rbac.yaml
uv run python scripts/run_operations_bridge.py --context kind-kubesentinel-recovery --impersonate system:serviceaccount:sentinel-lab:sentinel-operations-bridge
```

Set `OPS_NAMESPACES=["sentinel-lab"]` in `.env` and restart the API for this lab-only identity. Impersonation requires the local lab administrator and is a test/development launcher, not a production credential strategy. For a dedicated in-cluster process, use `--in-cluster` with a scoped projected service-account identity and secret-supplied bridge token; the script never silently selects a default context. The supplied RBAC grants node reads, namespaced resource reads, guarded CRD patches and approval creation. It cannot patch Deployments, delete pods, read secrets or access kube-system pods. Adapt namespace bindings deliberately for another environment.

`OPS_BRIDGE_TOKEN` is a separate internal ingestion/delivery credential. It is never accepted as an end-user token or forwarded by the browser proxy. Snapshot refreshes emit durable SSE change cursors. The browser reconnects using EventSource and falls back to the saved polling interval; streams expire after approximately 60 seconds and reauthenticate on reconnect.

## Telemetry and logs

Configure `PROMETHEUS_URL` for the API process/container. CPU and memory queries use the configured namespace allowlist; request/latency queries use the application's bounded metric names. `/ops/metrics/{cpu,memory,latency,requests}` permits 15–360 minute windows and fixed queries only. No arbitrary PromQL proxy exists.

`OPS_DETECTOR_URL` enables model/drift metadata. No live false-positive rate or calibrated confidence is invented. Feature bars display deviations, not causal contributions. The insights graph links shared resource names within namespaces; it is a heuristic relationship view, not proof of root cause or a connected LLM.

`OPS_LOKI_URL` enables **Load pod logs** in Pod details. Queries are scoped to the authorized pod/namespace, last 15 minutes, up to 100 lines. Loki must receive `service_name`, `k8s_namespace_name` and `k8s_pod_name` resource metadata; the existing application-only log pipeline may not populate every pod. Missing metadata gives an empty result. Outages return an error with no synthetic fallback. Logs can contain sensitive application text: collect/redact upstream and restrict viewer membership.

## OIDC and authorization

Deployed mode uses OIDC authorization-code flow with PKCE S256, encrypted flow cookies, state and nonce checks, issuer/audience/signature/expiry validation. Configure an RS256 provider with JWT access tokens. Opaque access tokens and automatic refresh are not supported; expired sessions require sign-in again. Access tokens must fit the bounded HttpOnly cookie (3800 characters maximum).

Configure Next.js `OIDC_ISSUER`, `OIDC_CLIENT_ID`, optional `OIDC_CLIENT_SECRET`, random `AUTH_SESSION_SECRET` (at least 32 characters), exact external `APP_PUBLIC_URL`, and HTTPS/secure cookies. Register `${APP_PUBLIC_URL}/api/auth/callback` at the provider. Configure API `OPS_OIDC_ISSUER` (the Compose overlay maps `OIDC_ISSUER`), `OPS_OIDC_AUDIENCE`, `OPS_OIDC_JWKS_URL` and `OPS_OIDC_ROLES_CLAIM`. Use trusted HTTPS issuer/JWKS endpoints. `OIDC_ALLOW_HTTP_LOCAL=true` is reserved for local provider tests and is not a deployment default. External provider interoperability has not been certified with a live tenant.

| Role | Authorized operations |
| --- | --- |
| viewer | Scoped reads, exports, cost calculation, own preferences |
| operator | Viewer capabilities plus incident review notes |
| approver | Viewer capabilities plus exact-plan approval/rejection |
| admin | All listed capabilities, including four bounded policy settings |

Roles come from the configured access-token claim, e.g. `kubesentinel_roles: ["viewer", "approver"]`. The API validates every operational mutation independently of UI visibility. A user's roles currently apply to the installation's configured namespace allowlist; per-user namespace claims are a future extension. Local admin/viewer tokens work only with `OPS_AUTH_MODE=development` and `APP_ENV=local`. Defaults contain no token or production bypass.

Operational POSTs through the Next.js proxy require the configured same origin. A Redis atomic counter limits persistent mutations to 20/user/minute; Redis failure disables mutations. Reads remain separately bounded. General public-ingress DoS protection belongs at the gateway. The legacy hello/telemetry interfaces retain their existing local/token contracts; do not expose them publicly as though OIDC now wraps the entire application.

## Approval and policy flow

A decision includes expected UID/resourceVersion, a reason and an idempotency key. Real snapshots must be at most 30 seconds old and actions must still await approval. In one transaction, PostgreSQL saves a command and actor/correlation audit record. The browser receives command metadata, never signing material or Kubernetes credentials.

For approval, the server signs the exact Go-compatible plan digest with its configured Ed25519 key. Mount it only in the API and explicitly register its public key with the operator. The bridge rechecks live UID/version/phase, creates the immutable approval, or applies a fenced rejection annotation. The operator revalidates policy, availability, expiry, signature and budgets before execution. Rejection applies before execution; it does not abort a mutation already in progress.

Policy editing exposes only dry-run, cooldown, action budget and maximum replicas. Broader selectors, workload allowlists and safety rules remain infrastructure-managed. Policy edits are admin-only and version-fenced; changing a policy invalidates old approval plans.

`pending`/`delivered` describes transport, **not recovery success**. Only operator `Succeeded` plus its verification evidence indicates recovery. Stale/conflicting/expired commands fail rather than guessing. Unknown transport outcomes require inspecting live CRDs; never blindly retry an altered plan. Demo decisions only create `demo_recorded` rows and are never delivered to Kubernetes.

## Helm configuration

The application chart's opt-in `operations.enabled=true` maps issuer/audience/JWKS, namespace scope, demo toggle, public URL, detector/Loki URLs and signing-key ID through ConfigMap settings. Supply existing Secret objects, never values-file credentials:

- `operations.apiSecretName`: `OPS_BRIDGE_TOKEN`; optional local tokens only in trusted local mode.
- `operations.dashboardSecretName`: `AUTH_SESSION_SECRET`, `OIDC_CLIENT_ID`, optional `OIDC_CLIENT_SECRET`.
- `operations.approvalSecretName`: optional file key `approver.key`; read-only mode 0440 with API fsGroup.

`operations.authMode` defaults to `oidc`; `demoEnabled` defaults false. The bridge is an explicit host/in-cluster process, not an implicitly privileged application Pod. The existing chart's egress policy must be deliberately extended for the exact OIDC, telemetry and external database endpoints using `networkPolicy.extraEgress`. Do not open arbitrary Internet egress. Root `.env` is not automatically imported by Kubernetes.

## Tests and troubleshooting

```sh
uv run pytest -m "not postgres"
npm test
npm run lint
npm run typecheck
npm run build
npm run test:e2e:operations
```

Playwright requires running API/UI with demo explicitly seeded and local auth enabled. Locally installed Edge works with `$env:PLAYWRIGHT_CHANNEL='msedge'` in PowerShell or `PLAYWRIGHT_CHANNEL=msedge npm run test:e2e:operations` on Linux/macOS. Otherwise install Chromium using `npx playwright install chromium`. CI starts the actual migrated PostgreSQL/Redis API and production UI via `uv run python scripts/test_operations_dashboard.py`. Screenshots and accessibility checks use labeled synthetic fixtures. [Validation](../reports/phase-07-validation.md) distinguishes these from real-cluster evidence.

- **401/503 sign-in:** compare frontend/backend auth mode, issuer, audience and role claim; check provider callback and clock. Never log access tokens.
- **403 mutation:** inspect role, namespace and same-origin configuration; a visible control does not grant permission.
- **409 decision:** refresh exact plan; check snapshot age, UID, resourceVersion and action phase.
- **503 mutation:** inspect Redis and signing-key readability; fail-closed is expected.
- **Empty inventory:** check explicit bridge context, namespace scope, RBAC, internal token and API URL. Collection errors never manufacture objects.
- **Offline charts/logs:** check service DNS, network policies, source ingestion and configured API-side URLs. Container localhost is the container itself.
- **Database errors:** migrate through `0004_operations` before startup; check PostgreSQL credentials and readiness. Take backups before production migrations.
- **Docker pipe error on Windows:** start Docker Desktop with Linux containers. No successful startup is implied by a rendered Compose file.

Stop the bridge before stopping the API. `docker compose -f docker-compose.yml -f docker-compose.operations.yml down` preserves durable volumes. Remove volumes only when deliberately discarding local data. For a dashboard rollback, retain the forward-compatible database schema and deploy the previous image; avoid downgrading `0004_operations` once audit records must be retained. The downgrade drops all five operations tables.
