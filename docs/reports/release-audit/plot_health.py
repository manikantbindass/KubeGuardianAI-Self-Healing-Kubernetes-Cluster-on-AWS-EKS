"""Plot recorded loopback trials; no extrapolation to database or cluster capacity."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent
report = json.loads((ROOT / "health-loopback-summary.json").read_text(encoding="utf-8"))
rows = report["summaries"]
fig, axes = plt.subplots(1, 2, figsize=(10, 4))
for axis, key, label in zip(
    axes,
    ("p95_ms", "requests_per_second"),
    ("Per-trial p95 latency (ms)", "Requests / second"),
    strict=True,
):
    for repetition in range(3):
        points = [row for row in rows if row["repetition"] == repetition]
        axis.scatter(
            [row["concurrency"] for row in points],
            [row[key] for row in points],
            label=f"Trial {repetition + 1}",
        )
    axis.set(xlabel="Client concurrency (not replicas)", ylabel=label, xticks=[1, 4, 8])
    axis.grid(alpha=0.2)
axes[0].legend()
fig.suptitle("Windows loopback health only · 900 requests · no database/cluster")
fig.tight_layout()
fig.savefig(ROOT / "health-loopback.png", dpi=150)
plt.close(fig)
