# Reproducible portfolio source

The root [PowerPoint](../../KubeSentinel-AI-Presentation.pptx), [technical report](../../KubeSentinel-AI-Technical-Report.pdf) and [slide PDF](../presentations/KubeSentinel-AI-Presentation.pdf) are generated deliverables. They do not replace the source, runbooks or raw experiment records.

## Source inventory

| File | Purpose |
| --- | --- |
| [content.json](content.json) | Shared slide copy, speaker notes, report chapters and repository references |
| [build_figures.py](build_figures.py) | Matplotlib charts derived from recorded JSON; cost scenarios use stated assumptions |
| [build_presentation.mjs](build_presentation.mjs) | Editable 1280×720 / 16:9 deck; native shapes, text, charts and workbook snapshots |
| [build_report.py](build_report.py) | ReportLab A4 typesetting, references, figures and appendices |
| [export_slides.ps1](export_slides.ps1) | Installed Microsoft PowerPoint PDF/PNG export on Windows |
| [evidence-manifest.json](evidence-manifest.json) | SHA-256 of raw chart inputs and missing measurements |
| [artifact-manifest.json](artifact-manifest.json) | Delivered binary hashes, generation inputs and tool versions |
| [pyproject.toml](pyproject.toml) / [uv.lock](uv.lock) | Isolated documentation Python dependencies |

## Runtimes and portability

Python 3.12 and uv 0.13.6 build the figures/report using the isolated lock. The deck uses **@oai/artifact-tool 2.8.106**, Node **24.22.1** and its presentation finalizer from Codex primary runtime **26.1026.10807**. These are authoring dependencies, separate from the application toolchain. This package/finalizer is supplied by the Codex runtime; it is not installed by root `npm ci` and ordinary GitHub runners do not include it. Deck regeneration therefore requires that runtime or a separately reviewed adapter. Sources and all editable PPTX objects are included so this dependency is explicit rather than hidden.

The chosen typeface is Arial. Windows supplies `arial.ttf` and `arialbd.ttf` under `C:/Windows/Fonts`. On Linux/macOS, set `DOCS_FONT_DIR` to a directory containing licensed copies of those files, or deliberately update both the source font choice and validation policy. Do not download fonts without appropriate licensing. Report and chart generation are portable; the supplied slide export script requires PowerPoint on Windows. Linux/macOS operators can export the final deck with LibreOffice and must recheck chart/text fidelity; that path has not been verified here.

## Regenerate figures and report

From the repository root, on PowerShell, bash or zsh:

```sh
uv sync --project docs/portfolio --frozen
uv run --project docs/portfolio python docs/portfolio/build_figures.py
uv run --project docs/portfolio python docs/portfolio/build_report.py
```

The dashboard image is a crop of [the original browser capture](../screenshots/phase-07/desktop.png), retaining the synthetic-data banner. To recreate the crop:

```sh
uv run --project docs/portfolio python -c "from PIL import Image; Image.open('docs/screenshots/phase-07/desktop.png').crop((0,0,1440,770)).save('docs/portfolio/figures/dashboard-crop.png')"
```

## Regenerate the deck

Set absolute runtime paths returned by the Codex workspace dependency tool. PowerShell example, adapting the installation root to your machine:

```powershell
$runtimeRoot = "$env:USERPROFILE/.cache/codex-runtimes/codex-primary-runtime"
$env:RUNTIME_NODE_MODULES = "$runtimeRoot/dependencies/node/node_modules"
$env:ARTIFACT_TOOL_PATH = "$env:RUNTIME_NODE_MODULES/@oai/artifact-tool/dist/artifact_tool.mjs"
$env:DOCS_PYTHON = "$runtimeRoot/dependencies/python/python.exe"
$env:PRESENTATIONS_SKILL_DIR = 'ABSOLUTE_PATH_TO_PRESENTATIONS_SKILL'
$env:DOCS_REVISION = 'review-01'
& "$runtimeRoot/dependencies/node/bin/node.exe" docs/portfolio/build_presentation.mjs
./docs/portfolio/export_slides.ps1
```

On Linux/macOS, use `export NAME=/absolute/path` for the same variables and invoke the bundled `node` binary. Use a new `DOCS_REVISION` for each finalization; the validator intentionally refuses to overwrite a validated output. Private drafts and review renders live under `.cache/portfolio/`. The validated PPTX is copied unchanged to the root. Speaker notes contain source references and evidence qualifications.

## Validation and evidence policy

Run `uv run --project docs/portfolio python docs/portfolio/validate_artifacts.py`, plus root Markdown/link/Mermaid checks. The validator verifies required binaries, 25 slides/notes, five editable charts/workbooks, embedded image bytes, PDF page counts, input hashes and output hashes. It cannot prove visual quality. Render every slide/page and inspect them, especially charts, screenshots and dense tables. The generation finalizer additionally checks package integrity, font policy, geometry, chart portability and Artifact Tool import. The committed [validation receipt](../reports/phase-11/presentation-validation.json) records those checks.

Figures use recorded synthetic ML results, isolated recovery records and Windows health-only trials. The source manifest documents missing CPU/memory, HPA, repeated recovery-comparison and full-stack-load evidence. Cost charts are illustrative assumptions, not observed bills or current quotes. No missing measurement is replaced with plausible-looking values.

Text hashes normalize CRLF to LF, matching the repository's `.gitattributes`; binaries are hashed as exact bytes. This prevents Windows/Linux checkouts from changing provenance. Manifest byte counts describe the authoring checkout and are informational. Raw telemetry/model dataset hashes retain their original documented semantics.

After an intentional regeneration, update the artifact manifest with the new hashes and source commit, rerun validation, and review binary changes. Rendering/build timestamps can change binary hashes; reproducibility here means reviewable pinned inputs and generation steps, not a claim of byte-identical Office exports.
