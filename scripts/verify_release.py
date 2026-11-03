"""Verify trusted release origin, keyless signatures and source-bound attestations."""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
from pathlib import Path
from typing import Any

from delivery import REPO, check_source, read, validate_release


def verify_origin(release: Any, run: Any) -> None:
    validate_release(release)
    expected = {
        "id": int(release["run_id"]),
        "event": "workflow_dispatch",
        "head_branch": "main",
        "head_sha": release["source_commit"],
        "path": ".github/workflows/release.yml",
        "status": "completed",
        "conclusion": "success",
    }
    if any(run.get(k) != v for k, v in expected.items()):
        raise ValueError("Release must originate from a successful main-branch release workflow")
    if run.get("repository", {}).get("full_name") != REPO:
        raise ValueError("Release workflow belongs to another repository")


def verify_predicate(envelope: Any, release: Any, component: str) -> None:
    statement = json.loads(base64.b64decode(envelope["payload"], validate=True))
    if statement.get("predicateType") != "https://slsa.dev/provenance/v1":
        raise ValueError("Incorrect provenance predicate")
    expected_digest = release["images"][component].split("@sha256:")[1]
    if not any(s.get("digest", {}).get("sha256") == expected_digest for s in statement["subject"]):
        raise ValueError("Provenance subject mismatch")
    predicate = statement["predicate"]
    parameters = predicate["buildDefinition"]["externalParameters"]
    if parameters != {"source_commit": release["source_commit"], "component": component}:
        raise ValueError("Provenance source/component mismatch")
    details = predicate["runDetails"]
    if (
        details["builder"]["id"]
        != f"https://github.com/{REPO}/.github/workflows/release.yml@refs/heads/main"
    ):
        raise ValueError("Untrusted provenance builder")
    if (
        details["metadata"]["invocationId"]
        != f"https://github.com/{REPO}/actions/runs/{release['run_id']}"
    ):
        raise ValueError("Provenance came from a different invocation")


def verify(release: Any) -> None:
    raw = subprocess.check_output(
        ["gh", "api", f"repos/{REPO}/actions/runs/{release['run_id']}"], text=True
    )
    verify_origin(release, json.loads(raw))
    check_source(release["source_commit"])
    identity = f"https://github.com/{REPO}/.github/workflows/release.yml@refs/heads/main"
    options = [
        "--certificate-identity",
        identity,
        "--certificate-oidc-issuer",
        "https://token.actions.githubusercontent.com",
    ]
    for component, image in release["images"].items():
        subprocess.run(["cosign", "verify", *options, image], check=True)
        subprocess.run(
            ["cosign", "verify-attestation", *options, "--type", "cyclonedx", image], check=True
        )
        output = subprocess.check_output(
            [
                "cosign",
                "verify-attestation",
                *options,
                "--type",
                "https://slsa.dev/provenance/v1",
                image,
            ],
            text=True,
        )
        # Cosign emits one JSON envelope per line; all must be valid JSON.
        envelopes = [json.loads(line) for line in output.splitlines() if line.strip()]
        matched = False
        for envelope in envelopes:
            try:
                verify_predicate(envelope, release, component)
                matched = True
            except (ValueError, KeyError):
                continue
        if not matched:
            raise ValueError("No source/run-bound provenance attestation")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", required=True, type=Path)
    args = parser.parse_args()
    verify(validate_release(read(args.release)))
