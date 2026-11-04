"""Import the explicitly synthetic fixture into demo mode, never into real records."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))
from kubesentinel_api.config import get_settings  # noqa: E402
from kubesentinel_api.operations.bridge import api_call  # noqa: E402
from kubesentinel_api.operations.demo import fixture  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    token = get_settings().ops_bridge_token.get_secret_value()
    if not token:
        raise SystemExit("OPS_BRIDGE_TOKEN is required")
    result = api_call(args.api, token, "internal/snapshots", fixture())
    print(f"Imported {result['accepted']} explicitly synthetic records into DEMO mode only.")
