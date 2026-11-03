# Phase 11 validation and release status

Date: 2026-11-03. Base source: `afa9867` (Phase 10); Phase 11 changes on `codex/phase-11-portfolio`. This is release preparation, not production certification. No AWS resources, merge, tag or GitHub release were created.

## Local quality matrix

| Command / check | Result | Scope / limitation |
| --- | --- | --- |
| `npm run lint` | Pass | ESLint, zero warnings |
| `npm run typecheck` | Pass | Frontend TypeScript |
| `npm test` | Pass: 16 tests, five files | Component/unit tests |
| `npm run build` | Pass | Next.js production build; sandbox initially denied output directory creation, rerun with filesystem access succeeded |
| `.venv/Scripts/python -m ruff check .` | Pass | Backend and repository Python, including portfolio source |
| `.venv/Scripts/python -m ruff format --check .` | Pass | Formatting |
| `.venv/Scripts/python -m mypy` | Pass: 76 source files | Application/scripts/tests strict typing |
| `.venv/Scripts/python -m pytest -m 'not postgres'` | Pass: 76, one deselected | Rerun with loopback socket permission; PostgreSQL migration test excluded locally |
| PowerPoint finalizer | Pass on reviewed generation | 25 slides, 25 notes, five editable charts/workbooks, Arial, 16:9 geometry, zero layout findings; see [receipt](phase-11/presentation-validation.json) |
| PowerPoint export | Pass | Installed PowerPoint rendered slides to PNG and PDF; visual review is separate from package checks |
| ReportLab export | Pass | A4 technical report, selectable text, referenced evidence and charts |
| `actionlint -color` | Pass locally | Linux ShellCheck recheck requires CI; local Windows actionlint does not include ShellCheck |
| Gitleaks on portfolio source | Pass | Redacted local scan; complete final tracked-source scan recorded with final checks |
| `go test ./...` and `go vet ./...` in `operator/` | Pass | Existing controller tests; no live faults injected |
| `helm lint` and `helm template` for local/dev/prod | Pass | Chart source only; no new local cluster startup |
| `terraform fmt -check -recursive infrastructure/terraform` | Pass | No source formatting drift |
| `terraform validate` for bootstrap/dev/demo | Pass | Backend-disabled local module initialization needed for demo; no plan/apply/destroy |
| Checkov 3.4.3 and repository policy gate | 139 checks pass; seven findings covered by existing reviewed, dated exceptions | No new exceptions; policy gate reports zero blocked findings |
| Gitleaks full history and candidate source | Pass, zero leaks | 36 commits and non-ignored tracked/new source; outputs redacted |
| Trivy local dependency scan | Blocked | No cached DB; registry download exceeded timeout. No clean scan claim; CI image failures still block release |

## Inherited CI snapshot

[Machine-readable snapshot](phase-11/inherited-ci.json) is the final Phase 10 PR #13 check state fetched during this phase. It is **historical**, not Phase 11 final-commit approval. Sixteen jobs succeeded; seven failed.

Passed jobs include Windows/Linux backend and Go checks, Windows/Linux ML reproducibility, frontend build/tests, Compose containers, migrations, detector container, browser flows, real operations cluster bridge, isolated recovery, telemetry and loopback resilience. Each snapshot entry links to its job.

Failures: five image-security jobs (blocking vulnerability findings), static security (ShellCheck SC2086 in Terraform scan argument quoting), and kind artifact upload (tests did not emit the expected `.cache/*.json`). Phase 11 fixes the quoting and captures actual non-secret kind status/warning logs plus rendered YAML. These fixes require fresh Linux CI; they do not waive image vulnerabilities or turn a historical failure green.

## Artifact and documentation checks

The [source manifest](../portfolio/evidence-manifest.json) binds each chart to recorded input bytes. [Artifact hashes](../portfolio/artifact-manifest.json) cover delivered binaries and editable sources. The [artifact validator](../portfolio/validate_artifacts.py) checks hashes, local references, slide/note/chart/workbook counts, embedded PNG data and PDF text/page structure. CI runs it with the isolated documentation lock.

All slide/page renders must be visually reviewed. The actual dashboard capture retains its synthetic-data label. CPU/memory and HPA curves remain planned because no machine-readable measurements exist. Recovery outcome counts describe action records; repeated native-baseline improvements are not claimed. Cost charts are assumptions, not measured bills.

## Deployment and release blockers

- Windows local Docker Engine is unavailable; do not claim a new local Compose/kind startup. Linux CI provides historical container/cluster evidence.
- No disposable local PostgreSQL instance was available for a new migration run; inherited Linux migration CI passed.
- HIGH/CRITICAL image findings remain blocking. No release version bump or v1.0.0 tag is appropriate until all security gates pass.
- No live OIDC tenant certification, ECR publishing, Argo staging promotion or AWS deployment is claimed.
- Full-stack load, CPU/memory overhead, HPA scaling, repeated recovery comparisons, backup restore and broad isolated chaos remain open evidence gaps.
- Stacked upstream PRs require review; Phase 11 does not authorize merging them or publishing a release.

## Final checks

Markdown lint passes for 71 files; all 13 Mermaid files and the README's inline diagram parse. Local file links, required files, original LICENSE hash, actionlint, npm lock declarations and `git diff --check` pass. Artifact validation checks 25 slides/notes, five editable chart/workbook pairs, embedded screenshot PNG, a 22-page report and 25-page slide PDF. Every slide and report page was rendered and visually reviewed; screenshot embedding, text encoding and diagram wrapping defects found during review were corrected before final export.

Text provenance uses Git LF normalization so validation works on Windows and Linux. A new CI portfolio job verifies committed binary/source hashes and artifact structure from the locked documentation environment; deck regeneration itself requires the documented Codex authoring runtime.

See the [release checklist](../releases/v1.0.0-candidate.md) for publication requirements and the [portfolio build guide](../portfolio/README.md) for exact regeneration commands and runtime limitations.
