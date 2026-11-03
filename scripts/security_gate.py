"""Fail closed on scanner findings; narrowly scoped exceptions expire automatically."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def exceptions(path: Path, today: date | None = None) -> list[dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if set(document) != {"version", "exceptions"} or document["version"] != 1:
        raise ValueError("Invalid exception document")
    result: list[dict[str, Any]] = document["exceptions"]
    now = today or datetime.now(UTC).date()
    seen: set[tuple[str, str, str]] = set()
    for item in result:
        if set(item) != {"scanner", "id", "scope", "reason", "owner", "issue", "expires"}:
            raise ValueError("Exception fields must be exact")
        if item["scanner"] not in {"trivy", "checkov"}:
            raise ValueError("Unsupported scanner exception")
        if any(not isinstance(v, str) or not v.strip() for v in item.values()):
            raise ValueError("Exception fields must be non-empty strings")
        expiry = date.fromisoformat(item["expires"])
        if expiry < now or (expiry - now).days > 90:
            raise ValueError("Exception expired or exceeds 90 days")
        if "*" in item["scope"] or not item["issue"].startswith("https://github.com/"):
            raise ValueError("Exception needs exact scope and tracking issue")
        key = item["scanner"], item["id"], item["scope"]
        if key in seen:
            raise ValueError("Duplicate exception")
        seen.add(key)
    return result


def findings(scanner: str, document: Any) -> list[tuple[str, str]]:
    if scanner == "checkov":
        reports = document if isinstance(document, list) else [document]
        if not reports or not all("results" in report for report in reports):
            raise ValueError("Missing Checkov results")
        result: list[tuple[str, str]] = []
        for report in reports:
            data = report["results"]
            if data.get("parsing_errors") or data.get("skipped_checks"):
                raise ValueError("Checkov parse errors or inline suppressions are forbidden")
            result.extend((c["check_id"], c["resource"]) for c in data["failed_checks"])
        return result
    if scanner == "trivy":
        if document.get("SchemaVersion") != 2 or not isinstance(document.get("Results"), list):
            raise ValueError("Missing Trivy schema")
        result = []
        for target in document.get("Results", []):
            if target.get("Secrets"):
                raise ValueError("Secrets cannot be excepted")
            for vuln in target.get("Vulnerabilities", []):
                if vuln["Severity"] in {"HIGH", "CRITICAL"}:
                    scope = f"{target['Target']}|{vuln['PkgName']}|{vuln['InstalledVersion']}"
                    result.append((vuln["VulnerabilityID"], scope))
            for finding in target.get("Misconfigurations", []):
                if finding["Severity"] in {"HIGH", "CRITICAL"} and finding["Status"] == "FAIL":
                    result.append((finding["ID"], target["Target"]))
        return result
    raise ValueError("Unsupported scanner")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scanner", choices=["trivy", "checkov"])
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    allowed = exceptions(ROOT / ".github/security/exceptions.json")
    failed = findings(args.scanner, json.loads(args.report.read_text(encoding="utf-8-sig")))
    blocked = [
        f
        for f in failed
        if not any(e["scanner"] == args.scanner and (e["id"], e["scope"]) == f for e in allowed)
    ]
    print(
        json.dumps({"scanner": args.scanner, "findings": len(failed), "blocked": blocked}, indent=2)
    )
    if blocked:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
