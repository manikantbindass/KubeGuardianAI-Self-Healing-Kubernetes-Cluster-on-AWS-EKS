# Development guide

This guide preserves the Phase 01 public greeting/health slice at `/status`, PostgreSQL, Redis, one-shot migrator and worker. For the Phase 07 authenticated operations UI, explicit demo mode, cluster bridge and approval setup, follow the [operations guide](runbooks/operations-dashboard.md). The legacy slice does not acquire global OIDC protection from the new operations routes. No cloud resources are required. Never expose these services publicly. The [verification record](validation.md) distinguishes checked commands from blocked integration tests.

## Toolchain

- Node 24.22.2 (`.nvmrc`) and npm 11.11.0. Linux/macOS: `nvm install && nvm use`; Windows: use nvm-windows or the Node installer. Run `npm install --global npm@11.11.0` if needed.
- Python 3.12 recommended; project range is 3.12-3.14. Install uv 0.13.6 with `python3 -m pip install uv==0.13.6` (Linux/macOS) or `py -3.12 -m pip install uv==0.13.6` (Windows). If pip is unavailable, create a tool virtual environment with `py -3.12 -m venv .tools` and use `.tools\Scripts\python -m pip install uv==0.13.6`.
- Docker Engine/Compose v2 or Docker Desktop with a running **Linux** engine. Make is optional.

All commands below start in repository root unless stated. No activation is required for uv. `.env` is ignored; never commit real secrets. npm uses `package-lock.json`; uv uses `uv.lock`; use frozen installs in CI.

Run `npm run check:lock` after dependency changes. npm can omit other operating systems' optional native packages when updating a lock against an existing install. If this check fails, regenerate the lock in an isolated directory containing the root/workspace package manifests and `.npmrc`, with no `node_modules`, then copy the lock back and verify clean installs on CI. Do not commit a Windows-only lockfile or repair it by adding Linux-only packages as mandatory dependencies.

## Container startup

```sh
# Linux/macOS
cp .env.example .env
docker compose config --quiet
docker compose up --build --wait --wait-timeout 180
python3 scripts/setup/smoke.py
```

```powershell
# Windows PowerShell
Copy-Item .env.example .env
docker compose config --quiet
docker compose up --build --wait --wait-timeout 180
py -3.12 scripts/setup/smoke.py
```

PostgreSQL becomes healthy, the migrator runs `alembic upgrade head`, then API/worker start. Readiness checks PostgreSQL connectivity, expected migration revision, and Redis ping. Dashboard liveness is independent of backend availability. Published ports bind `127.0.0.1`; hostnames `postgres`, `redis`, and `api` are only for containers.

For hot reload use `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build --wait --wait-timeout 180` or `make dev`. API and dashboard reload; restart the worker after changing worker code (`docker compose restart worker`). The development overlay uses a writable dependency stage for Next.js and mounts source separately from dependencies; it is not the production image. Change dependencies with a rebuild and remove stale overlay dependency volumes only when necessary.

## Native hot reload

Start only backing stores, install locks, and migrate:

```sh
docker compose up -d --wait postgres redis
npm ci
uv sync --frozen
uv run alembic -c apps/api/alembic.ini upgrade head
uv run uvicorn kubesentinel_api.main:app --app-dir apps/api --reload --host 127.0.0.1 --port 8000 --no-access-log
```

Second terminal (worker) and third terminal (dashboard):

```sh
# Linux/macOS, repository root
PYTHONPATH=apps/api uv run python -m kubesentinel_api.worker
# Separate terminal:
npm run dev
```

```powershell
# Windows PowerShell, repository root
$env:PYTHONPATH='apps/api'
uv run python -m kubesentinel_api.worker
# Separate terminal:
npm run dev
```

API, migrator, and worker read root `.env` using Pydantic Settings. Next.js does not load a root `.env` when running in the workspace: default API URL is `http://127.0.0.1:8000`. Override with `export API_BASE_URL=http://127.0.0.1:8001` (Linux/macOS) or `$env:API_BASE_URL='http://127.0.0.1:8001'` (PowerShell) before `npm run dev`, or use `apps/dashboard/.env.local`. Do not use `NEXT_PUBLIC_*` for internal URLs. Restart Next.js after changing environment values.

## Configuration

| Variable | Meaning / default |
| --- | --- |
| `APP_ENV`, `LOG_LEVEL` | API version response environment; JSON log threshold (`local`, `INFO`) |
| `DATABASE_URL` | Native SQLAlchemy psycopg URL; percent-encode reserved password characters |
| `REDIS_URL` | Native Redis URL; connection/command timeouts are bounded |
| `CORS_ORIGINS` | JSON list of permitted direct browser origins; no wildcard or credentialed CORS |
| `API_BASE_URL` | Server-only Next.js upstream; Compose overrides with `http://api:8000` |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Initial Compose database credentials/name, local-only defaults |
| `DASHBOARD_PORT`, `API_PORT`, `POSTGRES_PORT`, `REDIS_PORT` | Loopback host ports; container ports remain fixed |
| `TEST_DATABASE_URL` | Optional destructive migration test target, database name must end `_test` |

Changing host ports requires matching native URLs and smoke `--api` / `--dashboard` options. Changing initialized PostgreSQL credentials in `.env` does not rewrite existing database roles. Compose uses its explicit database variables to construct the container URL; native processes use `DATABASE_URL`. Keep them aligned. Live backend readiness returns 503 when dependencies or migration revision are unavailable; `/health` still returns 200 for process liveness.

## API examples

```sh
# Linux/macOS (Windows: use curl.exe instead of PowerShell's curl alias)
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/ready
curl http://localhost:8000/api/v1/version
curl -H 'Content-Type: application/json' -d '{"name":"Ada"}' http://localhost:8000/api/v1/jobs
curl http://localhost:8000/api/v1/jobs
```

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health
Invoke-RestMethod http://localhost:8000/api/v1/ready
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/jobs -ContentType 'application/json' -Body '{"name":"Ada"}'
```

`POST /api/v1/jobs` returns 202 with a queued job. `GET /api/v1/jobs/{id}` returns current state; completed jobs cache for 30 seconds. `GET /api/v1/jobs` returns the latest 20 records. PostgreSQL is authoritative; Redis hints are bounded to 1,000 entries, and the worker polls SQL after Redis failure. The deterministic greeting runs under a SQL row lock with `SKIP LOCKED`; this is a demo queue, not a general task execution engine. No arbitrary code or cluster action is accepted. Polling in the dashboard is not a streaming incident feed.

OpenAPI lives at `/openapi.json` and interactive docs at `/docs`. Errors use `{error: {code, message}, correlation_id}`. Request IDs are accepted only as 1-64 alphanumeric/underscore/hyphen characters; otherwise the API creates a UUID. Requests log JSON with method, path, status and ID, without body/credentials. Run Uvicorn with `--no-access-log` to avoid duplicate plain-text access logs. Lifecycle logs from the process runner may still use its own formatter.

## Checks and migration test

```sh
npm run lint
npm run typecheck
npm test
npm run build
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
npm run lint:docs
npm run diagrams
uv run python scripts/validate_repository.py
git diff --check
```

Unit API tests use isolated SQLite sessions and mocked Redis. They do not prove PostgreSQL migration or row-lock semantics. The real migration test upgrades, downgrades, and upgrades an explicitly disposable database and runs twice to check startup idempotency:

```sh
docker compose exec postgres createdb -U sentinel sentinel_test
# Linux/macOS:
TEST_DATABASE_URL=postgresql+psycopg://sentinel:sentinel_local@127.0.0.1:5432/sentinel_test uv run pytest -m postgres
```

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://sentinel:sentinel_local@127.0.0.1:5432/sentinel_test'
uv run pytest -m postgres
Remove-Item Env:TEST_DATABASE_URL
```

Never point this test at application data. Without the variable, pytest reports a skip. CI supplies a disposable PostgreSQL service, plus a separate Compose startup/job/API-outage/recovery smoke job. CI is configured, not claimed as executed until a pushed commit produces results.

## Troubleshooting and cleanup

| Symptom | Resolution |
| --- | --- |
| Docker named pipe/socket unavailable | Start Docker Desktop/Engine; select Linux containers. Check `docker context ls`, `docker --context desktop-linux info`. A client install alone is insufficient. If WSL/virtualization is unavailable, fix host prerequisites before startup. |
| Database connection refused | Check `docker compose ps` and `docker compose logs postgres`; verify native host/port versus container DNS. |
| Authentication failed | Compare URL and initialized role/password; changing `.env` does not change an existing PostgreSQL volume. Update the role deliberately or reset disposable data with informed deletion. |
| Readiness 503 / missing relation | Run `uv run alembic -c apps/api/alembic.ini upgrade head` natively or `docker compose run --rm migrate`. Do not use ORM create_all as a migration substitute. |
| Migrator fails | Inspect `docker compose logs migrate`; check DB connection, migration revision and privileges. Do not start worker/API against an unmigrated schema. |
| Greeting remains queued | Start/restart worker, inspect its logs and DB connectivity. Redis outages are tolerated via SQL polling. |
| UI offline/error | Check API health, server-only `API_BASE_URL`, and correlation ID in API logs. Browser must never target a Docker-only service name. |
| Port collision or Windows EACCES | Change `.env` host ports; use `npm run dev --workspace @kubesentinel/dashboard -- --port 3100` natively. For production `npm run build` then `PORT=3100 npm start` (PowerShell: `$env:PORT='3100'; npm start`). Update CORS/smoke flags as needed. |
| Windows file changes not detected | Prefer native processes for hot reload; check Docker bind mount sharing. Worker needs restart after changes. |

Stop services with `docker compose down --remove-orphans` (`make clean`); data volumes remain. For the hot reload stack use the same two `-f` files when stopping. To deliberately erase **only this disposable project's data**, run `docker compose down --volumes --remove-orphans` after reviewing the impact. Do not use global prune. Stop native processes with Ctrl+C. No AWS cleanup is needed because none is provisioned.

Application images use non-root users, dropped capabilities, read-only filesystems and writable temporary paths; datastore images use their official startup/volume behavior. Image versions are explicit, not digest-pinned yet. Future hardening includes identity, authorization, TLS, secrets management, image scanning/signing, and production database/cache policies.
