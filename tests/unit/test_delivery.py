"""Negative security boundaries and isolated staging promotion, with synthetic references."""

from __future__ import annotations

import base64
import copy
import json
import shutil
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from delivery import ROOT, digest, promote, validate_receipt, validate_release, write
from security_gate import exceptions, findings
from validate_delivery import fixture_release
from verify_release import verify_origin, verify_predicate


def test_staging_promotion_preserves_all_production_files(tmp_path: Path) -> None:
    source = ROOT / "infrastructure/argocd/environments"
    target = tmp_path / "infrastructure/argocd/environments"
    shutil.copytree(source, target)
    before = {p.name: p.read_bytes() for p in (target / "production").iterdir()}
    release = fixture_release()
    outputs = promote(release, "staging", tmp_path)
    assert len(outputs) == 3
    assert all(p.parent.name == "staging" for p in outputs)
    assert before == {p.name: p.read_bytes() for p in (target / "production").iterdir()}
    app = json.loads((target / "staging/application.json").read_text())
    assert app["spec"]["sources"][0]["targetRevision"] == release["source_commit"]
    assert "automated" not in app["spec"]["syncPolicy"]
    with pytest.raises(FileNotFoundError):
        promote(release, "production", tmp_path)


@pytest.mark.parametrize("mutation", ["tag", "foreign", "missing", "source", "version", "extra"])
def test_reject_untrusted_release_contract(mutation: str) -> None:
    release = fixture_release()
    if mutation == "tag":
        release["images"]["api"] = release["images"]["api"].split("@")[0] + ":latest"
    elif mutation == "foreign":
        release["images"]["api"] = release["images"]["api"].replace("123456789012", "999999999999")
    elif mutation == "missing":
        del release["images"]["dashboard"]
    elif mutation == "source":
        release["source_commit"] = "main"
    elif mutation == "version":
        release["version"] = "v1.0.0;echo bad"
    else:
        release["approval"] = True
    with pytest.raises(ValueError):
        validate_release(release)


def receipt(release: Any, observed: datetime) -> dict[str, Any]:
    return {
        "status": "verified",
        "namespace": "sentinel-staging",
        "observed_at": observed.isoformat(),
        "release_sha256": digest(release),
        "deployments": {
            name: {"image": release["images"]["api" if name == "worker" else name], "ready": 2}
            for name in ("api", "dashboard", "worker")
        },
    }


def test_production_requires_same_release_and_fresh_complete_staging(tmp_path: Path) -> None:
    shutil.copytree(
        ROOT / "infrastructure/argocd/environments", tmp_path / "infrastructure/argocd/environments"
    )
    release, now = fixture_release(), datetime.now(UTC)
    root = tmp_path / "infrastructure/argocd/environments/staging"
    promote(release, "staging", tmp_path)
    evidence = receipt(release, now)
    for update in (
        {"observed_at": (now - timedelta(hours=25)).isoformat()},
        {"release_sha256": "incorrect"},
        {"namespace": "sentinel-production"},
    ):
        with pytest.raises(ValueError):
            validate_receipt({**evidence, **update}, release, now)
    wrong = copy.deepcopy(evidence)
    wrong["deployments"]["api"]["ready"] = 1
    with pytest.raises(ValueError):
        validate_receipt(wrong, release, now)
    write(root / "verification.json", evidence)
    assert len(promote(release, "production", tmp_path)) == 3
    altered = copy.deepcopy(release)
    altered["version"] = "v9.0.0"
    with pytest.raises(ValueError):
        promote(altered, "production", tmp_path)


def test_fail_closed_scanner_reports_and_exact_exceptions(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        findings("trivy", {})
    with pytest.raises(ValueError):
        findings("checkov", {"results": {"parsing_errors": ["broken"]}})
    result = findings(
        "trivy",
        {
            "SchemaVersion": 2,
            "Results": [
                {
                    "Target": "api",
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-fixture",
                            "PkgName": "fixture",
                            "InstalledVersion": "1",
                            "Severity": "HIGH",
                        }
                    ],
                }
            ],
        },
    )
    assert result == [("CVE-fixture", "api|fixture|1")]
    exception = {
        "scanner": "trivy",
        "id": "CVE-fixture",
        "scope": "api|fixture|1",
        "reason": "Synthetic test",
        "owner": "test",
        "issue": "https://github.com/test/repo/issues/1",
        "expires": "2026-11-10",
    }
    path = tmp_path / "exceptions.json"
    write(path, {"version": 1, "exceptions": [exception]})
    assert len(exceptions(path, date(2026, 11, 3))) == 1
    with pytest.raises(ValueError):
        exceptions(path, date(2026, 11, 11))
    for update in ({"scope": "*"}, {"expires": "2027-11-10"}, {"expire": "2026-11-10"}):
        write(path, {"version": 1, "exceptions": [{**exception, **update}]})
        with pytest.raises(ValueError):
            exceptions(path, date(2026, 11, 3))


def test_untrusted_release_workflow_and_provenance_denied() -> None:
    release = fixture_release()
    run = {
        "id": 123,
        "event": "workflow_dispatch",
        "head_branch": "main",
        "head_sha": release["source_commit"],
        "path": ".github/workflows/release.yml",
        "status": "completed",
        "conclusion": "success",
        "repository": {"full_name": release["repository"]},
    }
    verify_origin(release, run)
    for update in (
        {"event": "pull_request"},
        {"head_branch": "attacker"},
        {"conclusion": "failure"},
    ):
        with pytest.raises(ValueError):
            verify_origin(release, {**run, **update})
    statement = {
        "predicateType": "https://slsa.dev/provenance/v1",
        "subject": [{"digest": {"sha256": "b" * 64}}],
        "predicate": {
            "buildDefinition": {
                "externalParameters": {
                    "source_commit": release["source_commit"],
                    "component": "api",
                }
            },
            "runDetails": {
                "builder": {
                    "id": f"https://github.com/{release['repository']}/.github/workflows/release.yml@refs/heads/main"
                },
                "metadata": {
                    "invocationId": f"https://github.com/{release['repository']}/actions/runs/123"
                },
            },
        },
    }
    envelope = {"payload": base64.b64encode(json.dumps(statement).encode()).decode()}
    verify_predicate(envelope, release, "api")
    with pytest.raises(ValueError):
        verify_predicate(envelope, release, "dashboard")
