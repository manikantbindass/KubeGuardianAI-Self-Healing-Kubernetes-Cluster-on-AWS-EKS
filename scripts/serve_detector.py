"""Native loopback server; no shell-specific PYTHONPATH setup needed."""

import os
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "ml"), str(ROOT / "services/anomaly-detector")]
os.environ.setdefault("DETECTOR_MODEL_PATH", str(ROOT / ".cache/ml/model.json"))

if __name__ == "__main__":
    uvicorn.run("kubesentinel_detector.main:app", host="127.0.0.1", port=8010, access_log=False)
