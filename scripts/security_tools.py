"""Install checksum-verified tools; no shell installers or cloud credentials."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def install(name: str) -> Path:
    lock = json.loads((ROOT / ".github/security/tools.lock.json").read_text(encoding="utf-8"))
    if platform.machine().lower() not in {"amd64", "x86_64"}:
        raise ValueError("Tool lock supports Linux/Windows x86_64 only")
    if platform.system() not in {"Linux", "Windows"}:
        raise ValueError("Tool lock supports Linux/Windows only")
    windows = os.name == "nt"
    needle = "windows" if windows else "linux"
    asset = next(a for a in lock[name]["assets"] if needle in a["name"].lower())
    target = ROOT / ".tools/delivery" / name
    target.mkdir(parents=True, exist_ok=True)
    binary = target / (name + (".exe" if windows else ""))
    archive = target / asset["name"]
    expected = asset["sha256"]
    if len(expected) != 64:
        raise ValueError("Missing pinned asset checksum")
    if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        with urllib.request.urlopen(asset["url"], timeout=90) as response:
            content = response.read(300_000_000)
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError("Tool checksum mismatch")
        archive.write_bytes(content)
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zipped:
            binary.write_bytes(zipped.read(binary.name))
    elif archive.name.endswith(".tar.gz"):
        with tarfile.open(archive) as zipped:
            member = zipped.extractfile(binary.name)
            if member is None:
                raise ValueError("Tool binary missing")
            binary.write_bytes(member.read())
    elif archive != binary:
        binary.write_bytes(archive.read_bytes())
    binary.chmod(0o755)
    return binary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "tools", nargs="+", choices=["actionlint", "gitleaks", "trivy", "cosign", "kubeconform"]
    )
    args = parser.parse_args()
    for name in args.tools:
        binary = install(name)
        print(binary)
        if os.environ.get("GITHUB_PATH"):
            with Path(os.environ["GITHUB_PATH"]).open("a", encoding="utf-8") as output:
                output.write(str(binary.parent) + "\n")


if __name__ == "__main__":
    main()
