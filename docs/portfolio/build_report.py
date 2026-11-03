"""Typeset the technical report from shared, reviewable portfolio content."""

import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[2]
CONTENT = json.loads((ROOT / "docs/portfolio/content.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((ROOT / "docs/portfolio/evidence-manifest.json").read_text(encoding="utf-8"))
FONT_DIR = Path(__import__("os").environ.get("DOCS_FONT_DIR", "C:/Windows/Fonts"))
pdfmetrics.registerFont(TTFont("Portfolio", str(FONT_DIR / "arial.ttf")))
pdfmetrics.registerFont(TTFont("PortfolioBold", str(FONT_DIR / "arialbd.ttf")))
pdfmetrics.registerFontFamily("Portfolio", normal="Portfolio", bold="PortfolioBold")
styles = getSampleStyleSheet()
for style in styles.byName.values():
    style.fontName = "Portfolio"
styles.add(
    ParagraphStyle(
        "BodyPortfolio",
        fontName="Portfolio",
        fontSize=10.5,
        leading=16,
        textColor=colors.HexColor("#24312b"),
        spaceAfter=11,
        alignment=TA_LEFT,
    )
)
styles.add(
    ParagraphStyle(
        "ChapterPortfolio",
        fontName="PortfolioBold",
        fontSize=25,
        leading=30,
        textColor=colors.HexColor("#143f31"),
        spaceAfter=19,
    )
)
styles.add(
    ParagraphStyle(
        "SmallPortfolio",
        fontName="Portfolio",
        fontSize=8,
        leading=12,
        textColor=colors.HexColor("#4a5f54"),
        spaceAfter=7,
        splitLongWords=True,
    )
)
styles.add(
    ParagraphStyle(
        "CoverTitle", fontName="PortfolioBold", fontSize=42, leading=49, textColor=colors.white
    )
)
styles.add(
    ParagraphStyle(
        "CoverSubtitle",
        fontName="Portfolio",
        fontSize=20,
        leading=28,
        textColor=colors.HexColor("#a3edcb"),
        spaceAfter=25,
    )
)


def para(value, style="BodyPortfolio"):
    return Paragraph(escape(value).replace("\n", "<br/>"), styles[style])


def page(canvas, doc):
    canvas.saveState()
    if doc.page == 1:
        canvas.setFillColor(colors.HexColor("#101214"))
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#a3edcb"))
        canvas.rect(22 * mm, 253 * mm, 18 * mm, 2 * mm, fill=1, stroke=0)
    else:
        canvas.setStrokeColor(colors.HexColor("#cbd9d0"))
        canvas.line(22 * mm, 278 * mm, 188 * mm, 278 * mm)
        canvas.setFont("Portfolio", 8)
        canvas.setFillColor(colors.HexColor("#4a5f54"))
        canvas.drawString(22 * mm, 282 * mm, "KUBESENTINEL AI  /  TECHNICAL REPORT")
    canvas.setFont("Portfolio", 8)
    canvas.setFillColor(colors.HexColor("#8aab9a") if doc.page == 1 else colors.HexColor("#4a5f54"))
    canvas.drawString(22 * mm, 15 * mm, "November 2026  |  Local / CI evidence  |  AWS undeployed")
    canvas.drawRightString(188 * mm, 15 * mm, str(doc.page))
    canvas.restoreState()


story = [
    Spacer(1, 37 * mm),
    para("KubeSentinel AI", "CoverTitle"),
    Spacer(1, 8 * mm),
    para("Observe clearly.\nRecover with evidence.", "CoverSubtitle"),
    Spacer(1, 15 * mm),
    para(
        "Technical report\nArchitecture, implementation, experiments and release gates",
        "CoverSubtitle",
    ),
    Spacer(1, 12 * mm),
]
cover_style = ParagraphStyle(
    "CoverBody", parent=styles["BodyPortfolio"], textColor=colors.HexColor("#c1cec6")
)
story += [
    Paragraph(
        "An evidence-backed engineering portfolio. Synthetic evaluations, isolated lab results "
        "and illustrative cost assumptions are labeled throughout. No production deployment "
        "or published v1.0.0 release is claimed.",
        cover_style,
    ),
    PageBreak(),
]
story.append(para("Contents and reading guide", "ChapterPortfolio"))
for index, chapter in enumerate(CONTENT["chapters"], 1):
    story.append(para(f"{index:02d}   {chapter['title']}", "BodyPortfolio"))
story += [
    Spacer(1, 6 * mm),
    para(
        "Appendices: reproducibility commands, evidence inventory, planned "
        "experiments, references and release checklist.",
        "SmallPortfolio",
    ),
    para("Repository: " + CONTENT["repository"], "SmallPortfolio"),
    PageBreak(),
]
for index, chapter in enumerate(CONTENT["chapters"], 1):
    story.append(para(f"{index:02d}  {chapter['title']}", "ChapterPortfolio"))
    for paragraph in chapter["text"]:
        story.append(para(paragraph))
    if chapter.get("figure"):
        image = Image(
            str(ROOT / f"docs/portfolio/figures/{chapter['figure']}.png"),
            width=160 * mm,
            height=70 * mm,
            kind="proportional",
        )
        story.append(
            KeepTogether(
                [
                    Spacer(1, 3 * mm),
                    image,
                    para(
                        "Figure source: "
                        + chapter["refs"][0]
                        + ". Scope and limitations are stated above.",
                        "SmallPortfolio",
                    ),
                ]
            )
        )
    story.append(Spacer(1, 3 * mm))
    story.append(para("Repository references", "SmallPortfolio"))
    for ref in chapter["refs"]:
        story.append(
            Paragraph(
                f'<link href="{CONTENT["repository"]}/blob/codex/phase-11-portfolio/'
                f'{escape(ref)}" color="#166b51">{escape(ref)}</link>',
                styles["SmallPortfolio"],
            )
        )
    story.append(PageBreak())

story.append(para("Supplementary evaluation plots", "ChapterPortfolio"))
story.append(
    para(
        "These plots use the same small synthetic test split and single isolated scale "
        "record described in the experiment chapters. Missed incidents are excluded from "
        "mean detection delay; robust statistics misses one of two incidents. Detection "
        "and recovery intervals are different samples and must not be added together."
    )
)
for name, caption in [
    ("precision-recall", "Synthetic precision-recall curves from the committed per-detector CSVs."),
    (
        "timing",
        "Left: synthetic mean detection delay. Right: one kind scale action, including approval.",
    ),
]:
    plot = Image(
        str(ROOT / f"docs/portfolio/figures/{name}.png"),
        width=160 * mm,
        height=65 * mm,
        kind="proportional",
    )
    story.extend([Spacer(1, 4 * mm), plot, para(caption, "SmallPortfolio")])
story.append(
    para(
        "Sources: docs/reports/phase-05/*-precision-recall.csv; "
        "docs/reports/phase-05/evaluation.json; "
        "docs/reports/phase-06/approved-scale.json.",
        "SmallPortfolio",
    )
)
story.append(PageBreak())
story.append(para("Appendix A  Reproduction and validation", "ChapterPortfolio"))
commands = [
    ("Locked application install", "npm ci; uv sync --frozen --extra ml --extra ops"),
    ("Frontend", "npm run lint; npm run typecheck; npm test; npm run build"),
    (
        "Backend",
        "uv run ruff check .; uv run ruff format --check .; uv run mypy; uv run "
        "pytest -m 'not postgres'",
    ),
    (
        "Documentation",
        "npm run lint:docs; npm run diagrams; uv run python scripts/validate_repository.py",
    ),
    (
        "Local Compose",
        "docker compose up --build --wait --wait-timeout 180; python scripts/setup/smoke.py",
    ),
    ("Portfolio figures", "uv run python docs/portfolio/build_figures.py"),
]
for title, command in commands:
    story.append(para(title, "BodyPortfolio"))
    story.append(para(command, "SmallPortfolio"))
story += [
    para(
        "PowerShell and Linux/macOS setup details live in "
        "docs/development-guide.md. Operations authentication and demo seeding use "
        "docs/runbooks/operations-dashboard.md. Documentation runtimes and "
        "PowerPoint/PDF export commands are pinned in docs/portfolio/README.md.",
        "BodyPortfolio",
    ),
    para(
        "A successful command on one source commit is historical evidence, not a "
        "guarantee for every later commit. See the dated Phase 11 validation matrix "
        "and CI snapshot for exact outcomes and unavailable dependencies.",
        "BodyPortfolio",
    ),
    PageBreak(),
]

story.append(para("Appendix B  Evidence inventory", "ChapterPortfolio"))
for source in MANIFEST["sources"]:
    story.append(para(source["path"], "BodyPortfolio"))
    story.append(para("SHA-256: " + source["sha256"], "SmallPortfolio"))
story.append(para("Scope: " + MANIFEST["scope"], "BodyPortfolio"))
story.append(
    para(
        "The manifest hashes UTF-8 input text with Git LF line endings for portable provenance. "
        "Presentation charts "
        "contain editable literal data and embedded workbook snapshots. Editing a "
        "chart changes the presentation; regenerate from source to restore "
        "repository evidence.",
        "BodyPortfolio",
    )
)
story.append(PageBreak())
story.append(para("Appendix C  Planned experiments", "ChapterPortfolio"))
rows = [
    [
        para("Measurement", "SmallPortfolio"),
        para("Required evidence before a result claim", "SmallPortfolio"),
    ]
]
for left, right in [
    (
        "CPU / memory overhead",
        "Timestamped pod/node samples, requests/limits, scrape interval, baseline "
        "and repeated workload.",
    ),
    (
        "Scaling behavior",
        "Replica transitions, sustained arrival rate, HPA inputs, queue age and "
        "node capacity over time.",
    ),
    (
        "Recovery comparison",
        "Paired native/KubeSentinel trials, identical faults, fault onset and "
        "verification timestamps, failures retained.",
    ),
    (
        "Production ML accuracy",
        "Consented real labeled data, temporal/incident split, tuning isolation, "
        "false positives and missed incidents.",
    ),
    (
        "Full-stack load",
        "Authenticated ingestion/scoring/decision traffic, SQL/Redis latency, "
        "throughput and error distributions.",
    ),
]:
    rows.append([para(left, "BodyPortfolio"), para(right, "BodyPortfolio")])
table = Table(rows, colWidths=[49 * mm, 117 * mm], hAlign="LEFT")
table.setStyle(
    TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5eee7")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd9d0")),
        ]
    )
)
story += [
    table,
    Spacer(1, 8 * mm),
    para(
        "These are planned experiments, not illustrative benchmark values. No CPU, "
        "memory, scaling or recovery-improvement curves are fabricated to fill the "
        "evidence gaps.",
        "BodyPortfolio",
    ),
    PageBreak(),
]
story.append(para("Appendix D  References and release", "ChapterPortfolio"))
for label, target in [
    ("Project source and original Apache 2.0 license", CONTENT["repository"]),
    ("Kubernetes controller model", "https://kubernetes.io/docs/concepts/architecture/controller/"),
    ("OpenTelemetry concepts", "https://opentelemetry.io/docs/concepts/"),
    (
        "Prometheus instrumentation practices",
        "https://prometheus.io/docs/practices/instrumentation/",
    ),
    ("Terraform state", "https://developer.hashicorp.com/terraform/language/state"),
    ("AWS EKS pricing review", "https://aws.amazon.com/eks/pricing/"),
    ("AWS pricing calculator", "https://calculator.aws/"),
]:
    story.append(
        Paragraph(
            f'<b>{escape(label)}</b><br/><link href="{target}" color="#166b51">{target}</link>',
            styles["BodyPortfolio"],
        )
    )
story.append(
    para(
        "The architecture choices in this report are project decisions. External "
        "references provide technology background; measured results come only from "
        "the repository records identified in each chapter and Appendix B.",
        "BodyPortfolio",
    )
)
story.append(para("Release checklist", "ChapterPortfolio"))
story.append(
    para(
        "Resolve blocking vulnerabilities; repeat the complete quality/security "
        "matrix; review artifacts and links; rehearse staging promotion; obtain "
        "maintainer authorization before merge or publication. No release tag, "
        "GitHub release or AWS deployment is created by this document build.",
        "BodyPortfolio",
    )
)
story.append(
    para(
        "Acknowledgements: the Kubernetes, CNCF, Python, Go, React/Next.js and "
        "open-source tool communities. Original repository history and LICENSE are "
        "preserved. Third-party components retain their own licenses.",
        "SmallPortfolio",
    )
)
output = ROOT / "KubeSentinel-AI-Technical-Report.pdf"
doc = SimpleDocTemplate(
    str(output),
    pagesize=A4,
    leftMargin=22 * mm,
    rightMargin=22 * mm,
    topMargin=27 * mm,
    bottomMargin=25 * mm,
    title="KubeSentinel AI - Technical Report",
    author="KubeSentinel AI contributors",
)
doc.build(story, onFirstPage=page, onLaterPages=page)
print(output)
