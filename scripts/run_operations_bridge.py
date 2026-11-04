"""Launch the explicit-context/in-cluster bridge without shell-specific PYTHONPATH syntax."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))
# Avoid scripts/kubernetes.py shadowing the official SDK when launched as a file.
sys.path[:] = [p for p in sys.path if Path(p).resolve() != ROOT / "scripts"]

from kubesentinel_api.operations.bridge import main  # noqa: E402

if __name__ == "__main__":
    main()
