"""Offline workflow, Argo schema, chart and staging-promotion contract checks."""

from __future__ import annotations

import copy
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from delivery import COMPONENTS, REPO, ROOT, digest, promote, read, write
from security_gate import exceptions


def fixture_release() -> dict[str, Any]:
    """Explicit synthetic references for offline rendering only; never published."""
    return {
        "schema_version": 1,
        "version": "v0.0.0-rc.1",
        "source_commit": "a" * 40,
        "run_id": "123",
        "repository": REPO,
        "images": {
            name: f"123456789012.dkr.ecr.ap-south-1.amazonaws.com/sentinel/{name}@sha256:{'b' * 64}"
            for name in COMPONENTS
        },
    }


def main() -> None:
    # Installed only in the separate, locked security environment.
    import jsonschema  # type: ignore[import-untyped]

    locks = read(ROOT / ".github/security/actions.lock.json")
    for path in (ROOT / ".github/workflows").glob("*.yml"):
        content = path.read_text(encoding="utf-8")
        if "pull_request_target:" in content or "permissions: write-all" in content:
            raise ValueError(f"Unsafe workflow event/permissions: {path}")
        for action, sha in re.findall(r"uses:\s*([^\s@]+)@([^\s#]+)", content):
            if not re.fullmatch(r"[a-f0-9]{40}", sha):
                raise ValueError(f"Unpinned action: {action}@{sha}")
            if action not in locks or locks[action]["sha"] != sha:
                raise ValueError(f"Action absent from reviewed lock: {action}")
        if not re.search(r"(?m)^permissions:\n  contents: read", content):
            raise ValueError(f"Workflow needs read-only default: {path}")
    exceptions(ROOT / ".github/security/exceptions.json")
    schema_root = ROOT / ".github/security/schemas"
    argocd = ROOT / "infrastructure/argocd/environments"
    for path in argocd.glob("*/*.json"):
        item = read(path)
        if path.name not in {"application.json", "project.json"}:
            continue
        schema = read(
            schema_root
            / ("application.json" if item["kind"] == "Application" else "appproject.json")
        )
        jsonschema.Draft7Validator(schema).validate(item)
        environment = path.parent.name
        spec = item["spec"]
        if item["kind"] == "Application":
            if "automated" in spec["syncPolicy"] or "ignoreDifferences" in spec:
                raise ValueError("Environment sync must remain reviewed and drift visible")
            if spec["destination"]["namespace"] != "sentinel-" + environment:
                raise ValueError("Cross-environment application destination")
            revision = spec["sources"][0]["targetRevision"]
            if revision != "release-not-configured" and not re.fullmatch(r"[a-f0-9]{40}", revision):
                raise ValueError("Chart revision must be immutable")
        elif spec["clusterResourceWhitelist"] or spec["destinations"] != [
            {"server": "https://kubernetes.default.svc", "namespace": "sentinel-" + environment}
        ]:
            raise ValueError("Argo project may not manage cluster resources/other environments")
    helm = shutil.which("helm") or str(ROOT / ".tools/helm/windows-amd64/helm.exe")
    conform = shutil.which("kubeconform") or str(ROOT / ".tools/kubeconform/kubeconform.exe")
    chart = ROOT / "infrastructure/helm/kubesentinel"
    synthetic = fixture_release()
    with tempfile.TemporaryDirectory(prefix="sentinel-gitops-") as name:
        temporary = Path(name)
        shutil.copytree(argocd, temporary / "infrastructure/argocd/environments")
        production_before = digest(
            read(temporary / "infrastructure/argocd/environments/production/application.json")
        )
        outputs = promote(copy.deepcopy(synthetic), "staging", temporary)
        if production_before != digest(
            read(temporary / "infrastructure/argocd/environments/production/application.json")
        ):
            raise ValueError("Staging promotion changed production")
        rendered_count = 0
        for environment in ("staging", "production"):
            values = argocd / environment / "values.json"
            images = temporary / "infrastructure/argocd/environments/staging/images.json"
            args = [helm, "lint", str(chart), "-f", str(values), "-f", str(images)]
            subprocess.run(args, check=True)
            manifest = subprocess.check_output(
                [
                    helm,
                    "template",
                    "sentinel",
                    str(chart),
                    "--namespace",
                    "sentinel-" + environment,
                    "-f",
                    str(values),
                    "-f",
                    str(images),
                ],
                text=True,
            )
            if ":phase02" in manifest or "@sha256:" not in manifest:
                raise ValueError("Mutable deployment image rendered")
            output = temporary / (environment + ".yaml")
            output.write_text(manifest, encoding="utf-8")
            subprocess.run(
                [
                    conform,
                    "-strict",
                    "-summary",
                    "-kubernetes-version",
                    "1.35.0",
                    "-schema-location",
                    str(schema_root / "kubernetes/{{.ResourceKind}}{{.KindSuffix}}.json"),
                    str(output),
                ],
                check=True,
            )
            rendered_count += 1
        try:
            promote(copy.deepcopy(synthetic), "production", temporary)
        except (ValueError, FileNotFoundError):
            pass
        else:
            raise ValueError("Production accepted an unverified staging release")
        print(
            f"PASS: {len(outputs)} staging files prepared; production unchanged; "
            f"{rendered_count} charts validated"
        )
    write(
        ROOT / ".cache/delivery/gitops-validation.json",
        {
            "mode": "offline-synthetic-contract-test",
            "environments_rendered": ["staging", "production"],
            "staging_promotion": "passed",
            "production_unchanged": True,
            "unverified_production_promotion": "denied",
            "live_sync": False,
        },
    )


if __name__ == "__main__":
    main()
