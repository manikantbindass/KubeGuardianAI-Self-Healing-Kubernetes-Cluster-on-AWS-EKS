# Verification record

Date: 2026-11-02. Environment: Windows PowerShell, Node 24.14.1, npm 11.11.0, Python 3.12.4, uv 0.13.6, Docker client 29.4.0 / Compose 5.1.1. Commands ran from repository root. The installed uv executable lives in `.venv/Scripts/uv`; Python tools also ran directly from `.venv/Scripts` to avoid sandbox cache restrictions. TestClient tests ran outside the Windows sandbox after sandbox execution stalled.

## Results

| Command / check | Result |
| --- | --- |
| `git clone <existing repository> .` | Preserved original single commit and LICENSE; no reinitialization |
| `npm ci` | Clean locked install passed; later script/advisory fixes refreshed the lock with `npm install` |
| `uv lock` and `uv sync --frozen` | Passed; explicit direct pins and uv lock installed |
| `npm run lint` | Passed, ESLint with zero warnings |
| `npm run typecheck` | Passed, strict TypeScript |
| `npm test` | 10 passed across page/client/proxy tests |
| `npm run build` | Production Next.js webpack build passed; page prerender and dynamic proxy compiled |
| `uv run ruff check .` / direct Ruff | Passed |
| `uv run ruff format --check .` / direct Ruff | Passed after formatting |
| `uv run mypy` / direct mypy | Passed strict checking |
| `uv run pytest` / `.venv/Scripts/python -m pytest -q` | 9 passed, 1 explicitly skipped (real PostgreSQL migration test) |
| `python -m alembic -c apps/api/alembic.ini upgrade head --sql` | Passed; generates PostgreSQL DDL for job table/index and migration revision; does not prove server execution |
| `npm run lint:docs` | Passed, zero issues |
| `npm run diagrams` | Five Mermaid diagrams parsed successfully |
| `docker compose config --quiet` | Passed |
| `docker compose -f docker-compose.yml -f docker-compose.dev.yml config --quiet` | Passed |
| `docker manifest inspect postgres:17.10-bookworm --verbose` and Redis 8.2.2 equivalent | Registry tags resolve; no image startup implied |
| Native Uvicorn + HTTP `/api/v1/health`, `/version`, `/ready` | 200 healthy, 200 version, 503 with both unavailable dependencies, respectively |
| Built Next.js dashboard on port 3100 + HTTP `/`, `/api/backend/health`, `/api/backend/ready` | 200 rendered page, 200 actual API health, 503 actual dependency readiness |
| `npm audit --omit=dev` | Zero runtime-dependency vulnerabilities reported |
| `npm start` with `PORT=3100` | Standalone production wrapper starts, copies static assets and binds loopback |
| `python scripts/setup/smoke.py --dashboard http://127.0.0.1:3100 --expect-unavailable` | Passed after stopping API; dashboard serves and proxy returns 503 |
| YAML parse of Compose, CI, Dependabot and issue templates | Passed using installed `js-yaml` |
| `python scripts/validate_repository.py` | Passed required docs, local file links and original LICENSE checks |
| `git diff --cached --check` | Passed complete staged changes, including new files |

The validator deliberately does not check external URL availability or Markdown heading anchors. Mermaid parsing checks grammar, not visual rendering. Component tests check accessible names/navigation/live-state behavior, not comprehensive WCAG compliance or a real browser session.

## Blockers and limitations

- `docker desktop start --detach` accepted the start request, but no Docker engine became reachable. `docker compose up --build --wait --wait-timeout 180` failed on the missing Windows engine pipe; `docker --context desktop-linux compose up --build --wait --wait-timeout 180` failed on the missing Linux engine pipe. No global Docker context was changed.
- Therefore full container startup, greeting completion against real PostgreSQL/Redis, PostgreSQL migration upgrade/downgrade, Redis outage recovery with actual services, and container hardening behavior are **not verified locally**. CI defines these checks on a Linux Docker host, but no CI run is claimed before publication.
- Windows denied binding port 3000 with EACCES. Native dashboard HTTP checks used port 3100. Change local port or `.env` host mapping as described in the development guide.
- `npm audit` reports 16 moderate findings in the ESLint/minimatch development chain. No high/critical findings remain after patch-compatible documentation dependency overrides. Runtime audit is clean. Do not apply `npm audit fix --force` blindly: the suggested downgrades break the selected tooling. Revisit upstream fixes through dependency updates.
- GitHub CLI credentials for the repository owner's stored account are invalid. The connected account has `pull=true`, `push=false`, `admin=false`. Local commit is authorized; remote publication requires working write access. No rename, branch protection update, cloud provisioning, or AWS API call was performed.

Phase 01 implementation is present, but full acceptance requires a Linux Docker host to run the blocked integration checks. Refer to the [development guide](development-guide.md) and [CI workflow](../.github/workflows/checks.yml) for exact reproduction commands.
