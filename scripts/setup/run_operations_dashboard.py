"""Launch Next.js with repository-root local configuration, without exposing secrets."""

import argparse
import os
import shutil
import subprocess
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    values = {k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None}
    executable = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not executable:
        raise SystemExit("npm is not on PATH")
    environment = {**os.environ, **values}
    if args.port:
        environment["PORT"] = str(args.port)
        environment["APP_PUBLIC_URL"] = f"http://127.0.0.1:{args.port}"
    subprocess.run([executable, "run", "dev"], cwd=ROOT, env=environment, check=True)
