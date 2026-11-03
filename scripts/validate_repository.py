"""Validate local documentation links, required files, and original license preservation."""

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "Makefile",
    ".env.example",
    ".editorconfig",
    ".gitignore",
    "docs/architecture/system-overview.md",
    "docs/roadmap.md",
    "docs/development-guide.md",
    "docs/security/threat-model.md",
    "docs/costs/aws-cost-considerations.md",
    "KubeSentinel-AI-Presentation.pptx",
    "KubeSentinel-AI-Technical-Report.pdf",
    "docs/presentations/KubeSentinel-AI-Presentation.pdf",
    "docs/portfolio/content.json",
    "docs/portfolio/artifact-manifest.json",
)


def broken_links(path: Path, root: Path) -> list[str]:
    errors = []
    body = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
    for match in re.finditer(r"\[[^\]]*\]\(([^)\s]+)\)", body):
        target = match.group(1).strip("<>")
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        destination = (path.parent / unquote(parsed.path)).resolve()
        if not destination.is_relative_to(root.resolve()) or not destination.exists():
            errors.append(f"{path.relative_to(root)}: broken local link: {target}")
    return errors


def main() -> int:
    errors = [f"Missing required file: {path}" for path in REQUIRED if not (ROOT / path).is_file()]
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    paths = [ROOT / name for name in result.stdout.decode().split("\0") if name]
    markdown = [path for path in paths if path.suffix == ".md" and path.is_file()]
    for path in markdown:
        errors.extend(broken_links(path, ROOT))
    license_blob = subprocess.run(
        ["git", "hash-object", "LICENSE"], cwd=ROOT, text=True, capture_output=True, check=True
    ).stdout.strip()
    if license_blob != "261eeb9e9f8b2b4b0d119366dda99c6fd7d35c64":
        errors.append("Original LICENSE content changed")
    for error in errors:
        print(f"FAIL: {error}", file=sys.stderr)
    if errors:
        return 1
    print(
        f"PASS: {len(markdown)} Markdown files, local file links, essential docs, original LICENSE"
    )
    print("Limits: no external URL or anchor validation; Mermaid uses npm run diagrams")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
