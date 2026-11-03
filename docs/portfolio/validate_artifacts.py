"""Check delivered artifact structure, source lineage and declared evidence limits."""

import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from provenance import source_digest
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}


def digest(path):
    return source_digest(path)


def main():
    content = json.loads((ROOT / "docs/portfolio/content.json").read_text(encoding="utf-8"))
    assert len(content["slides"]) == 25
    for slide in content["slides"]:
        for ref in slide["source"].split(";"):
            assert (ROOT / ref.strip()).exists(), f"Missing slide reference: {ref}"
    for chapter in content["chapters"]:
        for ref in chapter["refs"]:
            assert (ROOT / ref).exists(), f"Missing report reference: {ref}"
    evidence = json.loads((ROOT / "docs/portfolio/evidence-manifest.json").read_text())
    for source in evidence["sources"]:
        assert digest(ROOT / source["path"]) == source["sha256"], source["path"]
    manifest = json.loads((ROOT / "docs/portfolio/artifact-manifest.json").read_text())
    for artifact in manifest["files"]:
        assert digest(ROOT / artifact["path"]) == artifact["sha256"], artifact["path"]
    deck = ROOT / "KubeSentinel-AI-Presentation.pptx"
    with ZipFile(deck) as package:
        assert package.testzip() is None
        names = package.namelist()
        slides = [n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]
        notes = [n for n in names if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", n)]
        charts = [n for n in names if re.fullmatch(r"ppt/slides/charts/chart\d+\.xml", n)]
        workbooks = [n for n in names if n.startswith("ppt/embeddings/") and n.endswith(".xlsx")]
        assert len(slides) == len(notes) == 25
        assert len(charts) == len(workbooks) == 5
        images = [n for n in names if n.startswith("ppt/media/") and n.endswith(".png")]
        assert any(package.read(n).startswith(b"\x89PNG\r\n\x1a\n") for n in images)
        note_text = " ".join(package.read(n).decode() for n in notes)
        assert "synthetic" in note_text and "no AWS deployment" in note_text
        for slide in slides:
            xml = ET.fromstring(package.read(slide))
            assert xml.findall(".//a:t", NS), f"Slide has no editable text: {slide}"
    report = PdfReader(ROOT / "KubeSentinel-AI-Technical-Report.pdf")
    slide_pdf = PdfReader(ROOT / "docs/presentations/KubeSentinel-AI-Presentation.pdf")
    assert len(slide_pdf.pages) == 25
    assert 18 <= len(report.pages) <= 35
    text = " ".join(page.extract_text() for page in report.pages)
    for required in ["Abstract", "Threat", "Appendix", "synthetic", "blocked"]:
        assert required.lower() in text.lower(), required
    assert all(page.extract_text().strip() for page in report.pages)
    print(
        f"PASS: 25 slides/notes, 5 editable charts/workbooks, embedded PNG, "
        f"{len(report.pages)} report pages, 25 slide-PDF pages, references and SHA-256 lineage"
    )
    print("Limits: structural and content checks; visual inspection is a separate requirement")


if __name__ == "__main__":
    main()
