"""Build, scan and optionally publish source-pinned images after protected approval."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from delivery import REPO, ROOT, validate_release, write

DOCKERFILES = {
    "api": "apps/api/Dockerfile",
    "dashboard": "apps/dashboard/Dockerfile",
    "operator": "operator/Dockerfile",
    "detector": "services/anomaly-detector/Dockerfile",
    "demo-workload": "apps/demo-workload/Dockerfile",
}


def run(*args: str) -> None:
    subprocess.run(list(args), check=True, cwd=ROOT)


def build(name: str, source: str, output: Path) -> str:
    if name not in DOCKERFILES or not re.fullmatch(r"[a-f0-9]{40}", source):
        raise ValueError("Invalid build component/source")
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if source != actual:
        raise ValueError("Build source does not match checked-out commit")
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=normal"], text=True
    ).strip()
    if dirty:
        raise ValueError("Release builds require a clean checkout")
    epoch = subprocess.check_output(
        ["git", "show", "-s", "--format=%ct", source], text=True
    ).strip()
    image = f"kubesentinel/{name}:{source}"
    output.mkdir(parents=True, exist_ok=True)
    run(
        "docker",
        "buildx",
        "build",
        "--platform",
        "linux/amd64",
        "--load",
        "--provenance=false",
        "--sbom=false",
        "--build-arg",
        f"SOURCE_DATE_EPOCH={epoch}",
        "--label",
        f"org.opencontainers.image.revision={source}",
        "--label",
        f"org.opencontainers.image.source=https://github.com/{REPO}",
        "-f",
        DOCKERFILES[name],
        "-t",
        image,
        ".",
    )
    scan(image, name, output)
    return image


def scan(image: str, name: str, output: Path) -> None:
    # Always preserve raw findings; the repository gate applies exact, expiring exceptions.
    report = output / f"{name}-scan.json"
    run(
        "trivy",
        "image",
        "--scanners",
        "vuln,secret",
        "--format",
        "json",
        "--output",
        str(report),
        image,
    )
    run(
        "trivy",
        "image",
        "--format",
        "cyclonedx",
        "--output",
        str(output / f"{name}-sbom.cdx.json"),
        image,
    )
    run("python", "scripts/security_gate.py", "trivy", str(report))


def publish(version: str, prefix: str, output: Path) -> None:
    source = os.environ["GITHUB_SHA"]
    if (
        os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
    ):
        raise ValueError("Publishing is allowed only by manual dispatch on main")
    if not re.fullmatch(
        r"[0-9]{12}\.dkr\.ecr\.[a-z]{2}-[a-z]+-[0-9]\.amazonaws\.com/[a-z][a-z0-9-]{2,35}", prefix
    ):
        raise ValueError("Invalid approved ECR account/region/project prefix")
    release: dict[str, Any] = {
        "schema_version": 1,
        "version": version,
        "source_commit": source,
        "run_id": os.environ["GITHUB_RUN_ID"],
        "repository": REPO,
        "images": {},
    }
    # Validate the version and complete shape before building or writing to ECR.
    validate_release(
        {**release, "images": {name: f"{prefix}/{name}@sha256:{'0' * 64}" for name in DOCKERFILES}}
    )
    for name in DOCKERFILES:
        image = build(name, source, output)
        target = f"{prefix}/{name}:{version}-{source[:12]}-{release['run_id']}"
        run("docker", "tag", image, target)
        run("docker", "push", target)
        manifest = json.loads(
            subprocess.check_output(
                [
                    "docker",
                    "buildx",
                    "imagetools",
                    "inspect",
                    target,
                    "--format",
                    "{{json .Manifest}}",
                ],
                text=True,
            )
        )
        pinned = f"{prefix}/{name}@{manifest['digest']}"
        # Re-scan the immutable registry object, then sign/attest that same digest.
        scan(pinned, name, output)
        run("cosign", "sign", "--yes", pinned)
        run(
            "cosign",
            "attest",
            "--yes",
            "--type",
            "cyclonedx",
            "--predicate",
            str(output / f"{name}-sbom.cdx.json"),
            pinned,
        )
        predicate = {
            "buildDefinition": {
                "buildType": "https://github.com/manikantbindass/KubeSentinel-AI/build/v1",
                "externalParameters": {"source_commit": source, "component": name},
                "internalParameters": {},
                "resolvedDependencies": [
                    {"uri": f"git+https://github.com/{REPO}", "digest": {"gitCommit": source}}
                ],
            },
            "runDetails": {
                "builder": {
                    "id": f"https://github.com/{REPO}/.github/workflows/release.yml@refs/heads/main"
                },
                "metadata": {
                    "invocationId": f"https://github.com/{REPO}/actions/runs/{release['run_id']}"
                },
            },
        }
        path = output / f"{name}-provenance.json"
        write(path, predicate)
        run(
            "cosign",
            "attest",
            "--yes",
            "--type",
            "https://slsa.dev/provenance/v1",
            "--predicate",
            str(path),
            pinned,
        )
        release["images"][name] = pinned
    validate_release(release)
    write(output / "release.json", release)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    image = sub.add_parser("build")
    image.add_argument("--component", choices=sorted(DOCKERFILES), required=True)
    image.add_argument("--source", required=True)
    image.add_argument("--output", type=Path, default=Path(".cache/delivery/images"))
    release = sub.add_parser("publish")
    release.add_argument("--version", required=True)
    release.add_argument("--prefix", required=True)
    release.add_argument("--output", type=Path, default=Path(".cache/delivery/release"))
    args = parser.parse_args()
    if args.command == "build":
        build(args.component, args.source, args.output)
    else:
        publish(args.version, args.prefix, args.output)


if __name__ == "__main__":
    main()
