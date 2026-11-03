"""Record intentional portfolio exports after rendering and review."""

import json
import subprocess
from pathlib import Path

from provenance import source_digest

ROOT = Path(__file__).resolve().parents[2]
FILES = [
    "KubeSentinel-AI-Presentation.pptx",
    "KubeSentinel-AI-Technical-Report.pdf",
    "docs/presentations/KubeSentinel-AI-Presentation.pdf",
    "docs/presentations/preview.png",
    "docs/portfolio/content.json",
    "docs/portfolio/build_figures.py",
    "docs/portfolio/build_report.py",
    "docs/portfolio/build_presentation.mjs",
    "docs/portfolio/export_slides.ps1",
    "docs/portfolio/evidence-manifest.json",
    "docs/portfolio/provenance.py",
    "docs/portfolio/pyproject.toml",
    "docs/portfolio/uv.lock",
    "docs/portfolio/write_manifest.py",
    "docs/portfolio/validate_artifacts.py",
]
manifest = {
    "hash_normalization": "UTF-8 text uses Git LF line endings; binaries use exact bytes",
    "generation_date": "2026-11-03",
    "base_source_commit": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip(),
    "working_tree_changes": True,
    "toolchain": {
        "artifact_tool": "2.8.106",
        "authoring_node": "24.22.1",
        "codex_primary_runtime": "26.1026.10807",
        "reportlab": "4.4.9",
        "matplotlib": "3.11.2",
        "font": "Arial",
        "slide_pdf_export": "installed Microsoft PowerPoint, Windows",
    },
    "reproducibility": (
        "Pinned inputs and editable generation source; not byte-identical Office export"
    ),
    "files": [
        {
            "path": file,
            "sha256": source_digest(ROOT / file),
            "bytes": (ROOT / file).stat().st_size,
        }
        for file in FILES
    ],
}
(ROOT / "docs/portfolio/artifact-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print("Updated artifact hashes; inspect rendered output and validate before committing")
