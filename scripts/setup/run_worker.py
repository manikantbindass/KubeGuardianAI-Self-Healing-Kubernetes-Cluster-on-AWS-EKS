"""Run the worker from repository root so .env and imports resolve consistently."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

from kubesentinel_api.worker import main  # noqa: E402

if __name__ == "__main__":
    main()
