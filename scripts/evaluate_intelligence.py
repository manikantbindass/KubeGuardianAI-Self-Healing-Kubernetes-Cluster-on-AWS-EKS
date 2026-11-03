"""Reproduce a small explicitly synthetic correlation/retrieval contract evaluation."""

import argparse
import csv
import json
from pathlib import Path

from kubesentinel_api.intelligence import analyze


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".cache/intelligence-evaluation"))
    args = parser.parse_args()
    fixtures = [
        ("one", "lab", "checkout", "OOMKilled", "2026-11-03T10:00:00Z", "memory"),
        ("two", "lab", "checkout", "ReadinessFailure", "2026-11-03T10:01:00Z", "startup"),
        ("cross", "other", "checkout", "OOMKilled", "2026-11-03T10:00:00Z", "memory"),
        ("prefix", "lab", "checkout-api", "OOMKilled", "2026-11-03T10:00:00Z", "memory"),
        ("old", "lab", "checkout", "OOMKilled", "2026-11-02T10:00:00Z", "memory"),
        ("latency", "lab", "checkout", "LatencyDegradation", "2026-11-03T10:02:00Z", "latency"),
        ("unknown", "lab", "other-pod", "Unknown", "2026-11-03T10:00:00Z", "general"),
        ("duplicate", "lab", "checkout", "OOMKilled", "2026-11-03T10:00:30Z", "memory"),
    ]
    incidents = [
        {
            "id": i,
            "namespace": ns,
            "resource": r,
            "reason": reason,
            "first_seen": at,
            "severity": "warning",
        }
        for i, ns, r, reason, at, _ in fixtures
    ]
    result = analyze(incidents, [], [])
    group = {"one", "two", "latency", "duplicate"}
    expected = {(a, b) for a in group for b in group if a != b}
    observed = {(e.incident_id, related) for e in result.explanations for related in e.related_ids}
    true_positive = len(expected & observed)
    false_positive, false_negative = len(observed - expected), len(expected - observed)
    retrieved = {e.incident_id: e.runbooks[0].id for e in result.explanations}
    rows = [
        {
            "incident_id": i,
            "expected_runbook": expected_book,
            "observed_runbook": retrieved[i],
            "correct": expected_book == retrieved[i],
        }
        for i, _, _, _, _, expected_book in fixtures
    ]
    report = {
        "engine": "rules-v1",
        "provenance": "explicit synthetic hand-authored fixtures",
        "incidents": len(fixtures),
        "correlation_true_positives": true_positive,
        "correlation_false_positives": false_positive,
        "correlation_false_negatives": false_negative,
        "precision": true_positive / max(1, len(observed)),
        "recall": true_positive / len(expected),
        "retrieval_correct": sum(bool(r["correct"]) for r in rows),
        "retrieval_total": len(rows),
        "remote_requests": 0,
        "limitations": "Synthetic contract fixtures; no production accuracy estimate.",
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (args.output / "fixtures.json").write_text(
        json.dumps(incidents, indent=2) + "\n", encoding="utf-8"
    )
    with (args.output / "retrieval.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(report, indent=2))
    if false_positive or false_negative or any(not r["correct"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
