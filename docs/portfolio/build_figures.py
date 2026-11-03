"""Render only recorded measurements; never synthesize missing benchmark series."""

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import matplotlib
from provenance import source_digest

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/portfolio/figures"
OUT.mkdir(parents=True, exist_ok=True)
SOURCES = [
    "docs/reports/phase-05/evaluation.json",
    "docs/reports/phase-06/all-actions.json",
    "docs/reports/phase-06/approved-scale.json",
    "docs/benchmarks/phase-09/loopback/summary.json",
    "docs/reports/phase-10/results.json",
    "docs/costs/eks-estimate.md",
]


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8-sig"))


plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.facecolor": "white",
        "savefig.dpi": 180,
    }
)
COLORS = ["#168778", "#6761b0", "#c87926"]
evaluation = read(SOURCES[0])
detectors = evaluation["detectors"]
labels = ["Rules", "Robust statistics", "Isolation Forest"]
fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.2), layout="constrained")
for offset, metric in enumerate(["precision", "recall"]):
    axes[0].bar(
        [i + offset * 0.32 for i in range(3)],
        [value[metric] for value in detectors.values()],
        width=0.3,
        label=metric.title(),
        color=COLORS[offset],
    )
axes[0].set(xticks=[0.16, 1.16, 2.16], xticklabels=labels, ylim=(0, 1.15), ylabel="Score")
axes[0].legend(frameon=False)
axes[0].set_title("Synthetic held-out windows (n=177)")
matrix = detectors["isolation_forest"]["confusion_matrix"]
axes[1].imshow(matrix, cmap="Greens")
for row in range(2):
    for col in range(2):
        axes[1].text(
            col,
            row,
            str(matrix[row][col]),
            ha="center",
            va="center",
            fontsize=24,
            color="white" if matrix[row][col] > 75 else "#18251f",
        )
axes[1].set(
    xticks=[0, 1],
    yticks=[0, 1],
    xticklabels=["Normal", "Anomaly"],
    yticklabels=["Normal", "Anomaly"],
    xlabel="Predicted",
    ylabel="Actual",
    title="Isolation Forest confusion matrix",
)
fig.savefig(OUT / "ml.png")
plt.close(fig)

fig, ax = plt.subplots(figsize=(10.5, 3.5), layout="constrained")
for idx, model in enumerate(detectors):
    curve_path = ROOT / f"docs/reports/phase-05/{model}-precision-recall.csv"
    with curve_path.open(newline="", encoding="utf-8") as stream:
        curve = list(csv.DictReader(stream))
    ax.plot(
        [float(row["recall"]) for row in curve],
        [float(row["precision"]) for row in curve],
        label=labels[idx],
        color=COLORS[idx],
    )
    SOURCES.append(str(curve_path.relative_to(ROOT)).replace("\\", "/"))
ax.set(
    xlabel="Recall",
    ylabel="Precision",
    xlim=(0, 1.02),
    ylim=(0, 1.05),
    title="Synthetic precision-recall curves; no production accuracy estimate",
)
ax.legend(frameon=False)
fig.savefig(OUT / "precision-recall.png")
plt.close(fig)

actions = read(SOURCES[1])
outcomes = Counter(a["status"]["phase"] for a in actions)
types = Counter(a["spec"]["incident"]["type"] for a in actions)
severities = Counter(a["spec"]["incident"]["severity"] for a in actions)
fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), layout="constrained")
axes[0].bar(list(outcomes), list(outcomes.values()), color=COLORS[0])
axes[0].set(title="Eight action records: terminal state", ylabel="Action records")
axes[0].tick_params(axis="x", labelrotation=20)
axes[1].barh(list(types), list(types.values()), color=COLORS[1])
axes[1].set(title="Incident types attached to actions", xlabel="Action records")
axes[2].bar(list(severities), list(severities.values()), color=COLORS[2])
axes[2].set(title="Severity attached to actions", ylabel="Action records")
fig.savefig(OUT / "recovery.png")
plt.close(fig)

fig, axes = plt.subplots(1, 2, figsize=(11.2, 4), layout="constrained")
axes[0].bar(labels, [v["mean_detection_delay_seconds"] for v in detectors.values()], color=COLORS)
axes[0].set(title="Synthetic detection delay; misses excluded", ylabel="Seconds")
axes[0].tick_params(axis="x", labelrotation=12)
scale = read(SOURCES[2])["status"]
observed_at = scale["audit"][0]["at"]


def delta(a, b):
    return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds()


intervals = [
    delta(observed_at, scale["attemptedAt"]),
    delta(scale["verificationStartedAt"], scale["completedAt"]),
]
axes[1].bar(["Observe to apply", "Verification"], intervals, color=COLORS[:2])
axes[1].set(title="One kind scale action; includes approval/polling", ylabel="Seconds")
fig.savefig(OUT / "timing.png")
plt.close(fig)

trials = read(SOURCES[3])["summaries"]
fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.2), layout="constrained")
for idx, concurrency in enumerate([1, 4, 8]):
    selected = [t for t in trials if t["concurrency"] == concurrency]
    xs = [concurrency - 0.15, concurrency, concurrency + 0.15]
    axes[0].scatter(
        xs,
        [t["requests_per_second"] for t in selected],
        color=COLORS[idx],
        s=50,
        label=f"c={concurrency}",
    )
    for percentile, marker in [("p50_ms", "o"), ("p95_ms", "^"), ("p99_ms", "s")]:
        axes[1].scatter(
            xs,
            [t[percentile] for t in selected],
            marker=marker,
            color=COLORS[idx],
            s=35,
            label=percentile.removesuffix("_ms") if idx == 0 else None,
        )
axes[0].set(
    title="Health-only throughput; three trials each",
    xlabel="Concurrency",
    ylabel="Requests / second",
    xticks=[1, 4, 8],
    ylim=(0, 750),
)
axes[1].set(
    title="Per-trial latency; no pooled percentiles",
    xlabel="Concurrency",
    ylabel="Milliseconds",
    xticks=[1, 4, 8],
    ylim=(0, 50),
)
axes[1].legend(frameon=False)
fig.savefig(OUT / "load.png")
plt.close(fig)

cost = {
    "EKS": [73, 73],
    "Nodes": [73, 146],
    "NAT + data": [37.5, 74],
    "EBS": [3, 6],
    "Allowance": [25, 25],
}
fig, ax = plt.subplots(figsize=(10.5, 4), layout="constrained")
bottom = [0, 0]
for idx, (label, values) in enumerate(cost.items()):
    ax.bar(
        ["Dev", "Demo"],
        values,
        bottom=bottom,
        label=label,
        color=["#168778", "#6761b0", "#c87926", "#849da1", "#bac5c4"][idx],
    )
    bottom = [a + b for a, b in zip(bottom, values, strict=True)]
ax.set(
    ylabel="Assumed USD / month",
    ylim=(0, 380),
    title="Illustrative budget assumptions; incomplete environment",
)
ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(1, 1))
for idx, total in enumerate(bottom):
    ax.text(idx, total + 8, f"${total:.2f}", ha="center", fontweight="bold")
fig.savefig(OUT / "cost.png")
plt.close(fig)

manifest = {
    "hash_normalization": "UTF-8 text uses Git LF line endings; binaries use exact bytes",
    "scope": "Recorded synthetic evaluations and lab/loopback observations; costs are assumptions",
    "sources": [{"path": s, "sha256": source_digest(ROOT / s)} for s in SOURCES],
    "action_outcomes": dict(outcomes),
    "action_incident_types": dict(types),
    "action_severities": dict(severities),
    "missing_measurements": [
        "CPU/memory overhead",
        "HPA scaling",
        "production incident frequency",
        "repeated native-vs-sentinel recovery",
        "database/queue saturation",
    ],
}
(OUT.parent / "evidence-manifest.json").write_text(
    json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
)
print("Generated six evidence figures and source SHA-256 manifest")
