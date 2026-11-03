"""Start the actual PostgreSQL/Redis API and production dashboard, then run Playwright."""

import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    values = {k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None}
    env = {**values, **os.environ, "PORT": "4317", "APP_PUBLIC_URL": "http://127.0.0.1:4317"}
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    assert npm
    logs = ROOT / ".cache/operations"
    logs.mkdir(parents=True, exist_ok=True)
    processes = []
    try:
        with (logs / "api.log").open("w") as api_log, (logs / "web.log").open("w") as web_log:
            for command, output in [
                (
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "kubesentinel_api.main:app",
                        "--app-dir",
                        "apps/api",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "8000",
                        "--no-access-log",
                    ],
                    api_log,
                ),
                ([npm, "run", "start"], web_log),
            ]:
                processes.append(
                    subprocess.Popen(
                        command, cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT
                    )
                )
            for url in ("http://127.0.0.1:8000/api/v1/ready", "http://127.0.0.1:4317"):
                deadline = time.monotonic() + 90
                while True:
                    try:
                        with urllib.request.urlopen(url, timeout=5) as response:
                            assert response.status == 200
                        break
                    except (OSError, AssertionError):
                        if time.monotonic() > deadline or any(
                            p.poll() is not None for p in processes
                        ):
                            raise RuntimeError(
                                "Local test service unavailable; inspect .cache/operations logs"
                            ) from None
                        time.sleep(1)
            subprocess.run(
                [sys.executable, "scripts/seed_operations_demo.py"],
                cwd=ROOT,
                env=env,
                check=True,
                timeout=30,
            )
            subprocess.run(
                [npm, "run", "test:e2e:operations"], cwd=ROOT, env=env, check=True, timeout=600
            )
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
