"""Cross-platform entry point; raw data/model artifacts live in ignored .cache by default."""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

from kubesentinel_ml.collection import collect  # noqa: E402
from kubesentinel_ml.dataset import read_dataset, synthetic  # noqa: E402
from kubesentinel_ml.evaluation import evaluate  # noqa: E402
from kubesentinel_ml.features import windows  # noqa: E402
from kubesentinel_ml.model import Bundle  # noqa: E402
from kubesentinel_ml.training import train  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["generate", "collect", "train", "evaluate"])
    parser.add_argument("--data", type=Path, default=Path(".cache/ml/synthetic.jsonl"))
    parser.add_argument("--model", type=Path, default=Path(".cache/ml/model.json"))
    parser.add_argument("--output", type=Path, default=Path(".cache/ml/evaluation"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--trees", type=int, default=64)
    parser.add_argument("--max-samples", type=int, default=256)
    parser.add_argument("--window-seconds", type=int, default=60)
    parser.add_argument("--minutes", type=int, default=900)
    parser.add_argument("--prometheus", default="http://127.0.0.1:9090")
    parser.add_argument("--loki", default="http://127.0.0.1:3100")
    parser.add_argument("--start", type=datetime.fromisoformat)
    parser.add_argument("--end", type=datetime.fromisoformat)
    parser.add_argument("--dataset-id")
    parser.add_argument("--kube-context")
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args()
    if args.command in {"generate", "collect"}:
        if args.command == "generate":
            observations = synthetic(args.seed, args.minutes)
            metadata = {
                "provenance": "synthetic",
                "generator": "synthetic-v1",
                "seed": args.seed,
                "minutes": args.minutes,
            }
        else:
            if not args.start or not args.end or not args.dataset_id:
                parser.error("collect requires --start, --end and --dataset-id")
            observations, metadata = collect(
                args.prometheus, args.loki, args.start, args.end, args.dataset_id, args.kube_context
            )
        args.data.parent.mkdir(parents=True, exist_ok=True)
        raw = "".join(row.model_dump_json() + "\n" for row in observations).encode()
        args.data.write_bytes(raw)
        metadata["sha256"] = hashlib.sha256(raw).hexdigest()
        args.data.with_suffix(".metadata.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps({"observations": len(observations), **metadata}, indent=2))
        return
    observations, digest = read_dataset(args.data)
    size = (
        args.window_seconds if args.command == "train" else Bundle.load(args.model).window_seconds
    )
    feature_windows = windows(observations, size)
    if args.command == "train":
        bundle = train(
            feature_windows,
            digest,
            seed=args.seed,
            trees=args.trees,
            max_samples=args.max_samples,
            seconds=size,
        )
        args.model.parent.mkdir(parents=True, exist_ok=True)
        bundle.save(args.model)
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "model-metadata.json").write_text(
            json.dumps(
                {
                    "model_version": bundle.model_version,
                    "feature_version": bundle.feature_version,
                    "feature_order": bundle.feature_order,
                    "window_seconds": bundle.window_seconds,
                    "statistical_threshold": bundle.statistical_threshold,
                    "forest_threshold": bundle.forest_threshold,
                    **bundle.metadata,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    else:
        bundle = Bundle.load(args.model)
        if digest != bundle.metadata["dataset_sha256"]:
            raise ValueError("Evaluation dataset hash differs from recorded temporal split")
    report = evaluate(bundle, feature_windows, args.output, not args.no_plots)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
