@echo off
setlocal DisableDelayedExpansion
if /I "%~1"=="--help" goto help
if /I "%~1"=="--demo" goto argsok
if /I "%~1"=="--check" goto argsok
if not "%~1"=="" goto badargs
:argsok
if not "%~2"=="" goto badargs
set "MODE=%~1"
pushd "%~dp0..\.." || exit /b 1
where docker >nul 2>nul
if errorlevel 1 goto nodocker
call docker compose version >nul 2>nul
if errorlevel 1 goto nocompose
call docker info --format "{{.OSType}}" 2>nul | findstr /x /c:"linux" >nul
if not errorlevel 1 goto engineok
call docker --context desktop-linux info --format "{{.OSType}}" 2>nul | findstr /x /c:"linux" >nul
if errorlevel 1 goto noengine
set "DOCKER_CONTEXT=desktop-linux"
:engineok
call docker compose -f docker-compose.yml -f docker-compose.operations.yml config --quiet
if errorlevel 1 goto failed
if /I "%MODE%"=="--check" goto checked
echo Building the pinned API image for local setup...
call docker compose build api
if errorlevel 1 goto failed
set "DEMO_OPTION="
if /I "%MODE%"=="--demo" set "DEMO_OPTION=--demo"
echo Preparing ignored local configuration without printing credentials...
call docker compose run --rm --no-deps --volume "%CD%:/workspace" --workdir /workspace --entrypoint python api scripts/setup/operations_env.py --development %DEMO_OPTION%
if errorlevel 1 goto failed
echo Starting PostgreSQL, Redis, migrator, API, worker and dashboard...
call docker compose -f docker-compose.yml -f docker-compose.operations.yml up --build --wait --wait-timeout 180
if errorlevel 1 goto failed
if /I not "%MODE%"=="--demo" goto smoke
echo Importing explicitly synthetic demonstration records...
call docker compose -f docker-compose.yml -f docker-compose.operations.yml run --rm --no-deps --volume "%CD%:/workspace:ro" --workdir /workspace --entrypoint python api scripts/seed_operations_demo.py --api http://api:8000
if errorlevel 1 goto failed
:smoke
call docker compose -f docker-compose.yml -f docker-compose.operations.yml run --rm --no-deps --volume "%CD%:/workspace:ro" --workdir /workspace --entrypoint python api scripts/setup/smoke.py --api http://api:8000 --dashboard http://dashboard:3000
if errorlevel 1 goto failed
echo.
echo Setup and HTTP smoke checks completed successfully.
echo Open http://localhost:3000 and sign in using OPS_DEV_TOKEN from your local .env.
echo Existing .env values and database volumes are preserved.
if /I "%MODE%"=="--demo" echo Select Synthetic demo explicitly in the dashboard.
echo For custom ports or a configured OIDC tenant, see docs\runbooks\windows-cmd.md.
popd
exit /b 0
:checked
echo PASS: Linux Docker Engine, Compose v2 and project configuration are available.
popd
exit /b 0
:nodocker
echo ERROR: Docker is not on PATH. Install Docker Desktop and restart CMD.
goto stop
:nocompose
echo ERROR: Docker Compose v2 is required. Update Docker Desktop.
goto stop
:noengine
echo ERROR: A running Linux Docker Engine is required.
echo Start Docker Desktop, select Linux containers, and finish WSL 2 setup if required.
echo Then retry this command. No project data was deleted.
goto stop
:failed
echo ERROR: Setup stopped because the preceding command failed.
echo Inspect: docker compose -f docker-compose.yml -f docker-compose.operations.yml logs --tail 80
echo No automatic cleanup or volume deletion was performed.
:stop
popd
exit /b 1
:badargs
echo ERROR: Unsupported arguments. Use --help, --check, --demo, or no option.
exit /b 2
:help
echo KubeSentinel local installation for Windows CMD
echo Usage: scripts\setup\install.cmd [--demo ^| --check ^| --help]
echo Requires Docker Desktop with Linux Engine and Compose v2. No host Python or Node needed.
echo Default: trusted local authentication, real data mode, empty until collection.
echo --demo additionally imports labeled synthetic records. It never enables cluster mutation.
echo --check only verifies Docker and Compose configuration; no build or startup.
exit /b 0
