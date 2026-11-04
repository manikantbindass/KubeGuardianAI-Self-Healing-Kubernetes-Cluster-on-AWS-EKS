# Easy installation using Windows CMD

These commands are for **Command Prompt (`cmd.exe`)**, not PowerShell. The setup
script uses the existing locked container build and operations overlay. It needs
Git for Windows and Docker Desktop with **Linux containers**, Docker Compose v2,
and working WSL 2 or virtualization. Host Python, Node, npm, uv and Make are not
required for this container installation.

## Install prerequisites once

In CMD, if Windows Package Manager is available:

```bat
winget install --id Git.Git --exact --source winget
winget install --id Docker.DockerDesktop --exact --source winget
```

Complete the installers and any administrator, license or restart prompts
yourself. Open Docker Desktop, finish its first-run setup and select Linux
containers. Open a new CMD window so Git and Docker are on PATH. Organization
Docker licensing and host virtualization requirements still apply; the script
does not accept license agreements or change system security settings.

## One line to clone and start a labeled demonstration

Run this in a directory where you want the new checkout:

```bat
git clone --branch main https://github.com/manikantbindass/KubeSentinel-AI.git && cd KubeSentinel-AI && scripts\setup\install.cmd --demo
```

The installer was merged into `main` through
[PR #28](https://github.com/manikantbindass/KubeSentinel-AI/pull/28).
The default clone directory must not already exist. For an existing checkout
that includes the installer,
run `scripts\setup\install.cmd --demo` from its root. From another batch file,
use `call scripts\setup\install.cmd --demo` so control returns to the caller.

Open `http://localhost:3000`. Sign in using `OPS_DEV_TOKEN` from the ignored local
`.env` file; open it with `notepad .env`. Select **Synthetic demo** explicitly.
Do not paste credentials into issues, chats or screenshots. Demo records are
synthetic and cannot execute Kubernetes changes. The script does not install an
operator, provision AWS or connect to a cluster.

## Start without synthetic data

```bat
scripts\setup\install.cmd
```

For a fresh checkout, the API defaults to real data mode and the operations UI
stays empty until an explicitly configured bridge collects telemetry. This
script enables trusted local development authentication. It refuses to replace
nonlocal or configured OIDC authentication; use the [operations runbook](operations-dashboard.md)
for those installations. Existing `.env` settings, keys and database volumes are
preserved. An already enabled synthetic partition is not silently disabled.

## Check, inspect and stop

```bat
scripts\setup\install.cmd --check
docker compose -f docker-compose.yml -f docker-compose.operations.yml ps
curl.exe http://localhost:8000/api/v1/health
curl.exe http://localhost:8000/api/v1/ready
docker compose -f docker-compose.yml -f docker-compose.operations.yml logs --tail 80
docker compose -f docker-compose.yml -f docker-compose.operations.yml down
```

`down` preserves database volumes. The setup runs Alembic migrations before the
API/worker and executes the actual HTTP greeting/worker smoke script from a
one-shot container. A failure exits nonzero without deleting data. First builds
need internet access and can take several minutes. The installer does not
automatically open a browser or display secret values.

For nondefault ports, edit `.env` before running the installer and keep
`APP_PUBLIC_URL`, `CORS_ORIGINS`, `DASHBOARD_PORT` and any native API URLs
consistent. The printed localhost links assume default ports; use your configured
port otherwise. Internal smoke checks use service DNS and fixed container ports.

## Docker engine and port errors

If the engine is offline, start Docker Desktop and verify:

```bat
docker --context desktop-linux info
```

The script tries the current Linux engine, then `desktop-linux`. Any fallback
context applies only to the setup process; it does not change the globally
selected Docker context. For later commands in the same CMD window, if needed:

```bat
set DOCKER_CONTEXT=desktop-linux
```

If a port is in use, stop only the conflicting local service or choose unused
ports in `.env`. Do not delete PostgreSQL volumes to fix a socket/port error.
If PostgreSQL credentials were changed after first startup, reconcile its role
deliberately; editing `.env` does not rewrite an initialized database password.

## Validation scope

The CMD orchestration has Windows tests for paths containing spaces, option
handling, fail-fast behavior and explicit demo seeding using a fake Docker
command. These tests do not prove container startup. The underlying Compose,
migrations and HTTP smoke are exercised by Linux CI. A fresh end-to-end run of
this CMD installer additionally requires a working Windows Linux Docker engine;
no successful Windows startup is implied when that dependency is unavailable.

Local validation on 4 November 2026: 85 Python tests passed (including the five
CMD tests); one PostgreSQL migration test was skipped because `TEST_DATABASE_URL`
was unset. Ruff, mypy, Markdown lint, repository file-link checks and Compose
configuration validation passed. `install.cmd --check` exited 1 with
`A running Linux Docker Engine is required`; a fresh Windows container startup
remains unverified until Docker Desktop is available.
