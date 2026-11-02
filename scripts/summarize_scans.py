"""Summarize advisory Trivy reports; missing reports are an error, never a clean scan."""

import json
import sys
from collections import Counter
from pathlib import Path


def main() -> None:
    directory = Path(sys.argv[1])
    for image in ("api", "dashboard", "postgres", "redis"):
        report = json.loads((directory / f"{image}-scan.json").read_text(encoding="utf-8"))
        findings = [
            item
            for result in report.get("Results", [])
            for item in result.get("Vulnerabilities", [])
        ]
        counts = Counter(item["Severity"] for item in findings)
        print(f"{image}: {dict(counts)} ({len(findings)} HIGH/CRITICAL package findings)")
        for item in findings:
            print(
                f"  {item['VulnerabilityID']} {item['PkgName']} "
                f"{item['InstalledVersion']} -> {item.get('FixedVersion', 'no fix listed')}"
            )


if __name__ == "__main__":
    main()
