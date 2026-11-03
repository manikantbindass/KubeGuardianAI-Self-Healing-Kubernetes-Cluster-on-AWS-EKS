// Editable PowerPoint source. See README.md here for runtime setup and validation.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const modulePath = process.env.ARTIFACT_TOOL_PATH;
const skill = process.env.PRESENTATIONS_SKILL_DIR;
if (!modulePath || !skill || !process.env.DOCS_PYTHON) {
  throw new Error('Set ARTIFACT_TOOL_PATH, PRESENTATIONS_SKILL_DIR and DOCS_PYTHON; see docs/portfolio/README.md');
}
const { Presentation, PresentationFile } = await import(pathToFileURL(modulePath).href);
const { finalizePresentation, applyPresentationChartFont } = await import(
  pathToFileURL(path.join(skill, 'container_tools/artifact_tool_utils.mjs')).href);
const data = JSON.parse(await fs.readFile(path.join(ROOT, 'docs/portfolio/content.json'), 'utf8'));
const evidence = JSON.parse(await fs.readFile(path.join(ROOT, 'docs/portfolio/evidence-manifest.json'), 'utf8'));
const ml = JSON.parse(await fs.readFile(path.join(ROOT, 'docs/reports/phase-05/evaluation.json'), 'utf8'));
const load = JSON.parse(await fs.readFile(path.join(ROOT, 'docs/benchmarks/phase-09/loopback/summary.json'), 'utf8'));
const stage = path.join(ROOT, '.cache/portfolio');
const revision = process.env.DOCS_REVISION || 'v1';
const finalPath = path.join(stage, 'output', `KubeSentinel-AI-${revision}.pptx`);
await fs.mkdir(path.join(stage, 'output'), { recursive: true });
const p = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const C = { bg: '#101214', fg: '#f3f1ea', muted: '#afb7b4', green: '#a3edcb', purple: '#b3a7f3', line: '#36423e' };
function shape(s, x, y, w, h, fill, geometry = 'rect') {
  return s.shapes.add({ geometry, position: { left: x, top: y, width: w, height: h }, fill,
    line: { fill: 'none', width: 0, style: 'solid' } });
}
function text(s, value, x, y, w, h, size = 25, color = C.fg, bold = false) {
  const t = shape(s, x, y, w, h, 'none', 'textbox');
  t.text = value;
  t.text.style = { typeface: 'Arial', fontSize: size, color, bold };
  return t;
}
function base(d, i) {
  const s = p.slides.add(); s.background.fill = C.bg;
  shape(s, 64, 56, 44, 5, C.green);
  text(s, d.title, 64, 90, 1150, 65, 43, C.fg, true);
  text(s, d.subtitle, 66, 166, 1140, 50, 22, C.muted);
  shape(s, 64, 650, 1152, 1, C.line);
  text(s, `KUBESENTINEL AI     /     ${String(i + 1).padStart(2, '0')}`, 64, 667, 450, 25, 13, C.muted);
  text(s, 'Engineering evidence · November 2026', 853, 667, 365, 25, 13, C.muted);
  s.speakerNotes.text = `${d.notes}\n\nRepository source: ${d.source}\nRepository: ${data.repository}\nEvidence scope: local/CI; no AWS deployment; release unpublished.`;
  return s;
}
function paragraphs(s, points, x = 66, y = 252, width = 1100, step = 77, size = 27) {
  points.forEach((v, n) => {
    text(s, String(n + 1).padStart(2, '0'), x, y + n * step, 46, 45, 17, C.green, true);
    text(s, v, x + 67, y + n * step - 3, width - 67, step - 8, size);
  });
}
function chart(s, title, categories, series, x, y, w, h, ymax) {
  const ch = s.charts.add('bar', {
    position: { left: x, top: y, width: w, height: h }, title,
    titleTextStyle: { fontSize: 17, fill: '#1e3029' }, categories,
    // Display rounding avoids overstating precision and preserves Excel portability.
    series: series.map(v => ({ ...v, values: v.values.map(n => Number(n.toFixed(4))) })),
    hasLegend: series.length > 1, legend: { position: 'bottom', textStyle: { fontSize: 14 } },
    chartFill: '#f3f5f0', plotAreaFill: '#f3f5f0',
    barOptions: { direction: 'column', grouping: 'clustered' },
    xAxis: { textStyle: { fontSize: 14, fill: '#223a30' } },
    yAxis: { min: 0, ...(ymax ? { max: ymax } : {}), textStyle: { fontSize: 14, fill: '#223a30' },
      majorGridlines: { fill: '#d4ddd6', width: 1, style: 'solid' } },
    dataLabels: { showValue: false, textStyle: { fontSize: 13 } },
  });
  applyPresentationChartFont(ch, { fontFamily: 'Arial' });
  return ch;
}
for (const [i, d] of data.slides.entries()) {
  const s = base(d, i);
  if (d.kind === 'cover' || d.kind === 'close') {
    // Large editable typography and geometric signal motif.
    shape(s, 64, 240, 4, 300, C.green);
    text(s, d.kind === 'cover' ? 'Evidence.\nPolicy.\nVerified recovery.' : 'Explore.\nReproduce.\nReview.', 90, 248, 680, 265, 62, C.fg, true);
    if (d.kind === 'close') {
      text(s, d.points.slice(0, 3).join('\n\n'), 800, 260, 390, 250, 23, C.muted);
      const label = 'github.com/manikantbindass/\nKubeSentinel-AI';
      const repo = text(s, label, 800, 528, 390, 70, 21, C.green);
      repo.text.get(label).link = { uri: data.repository, isExternal: true };
    } else {
      text(s, d.points.join('\n\n'), 800, 260, 390, 300, 23, C.muted);
    }
    for (let n = 0; n < 10; n++) shape(s, 90 + n * 62, 565 - n * 4, 44, 13 + n * 4, n % 2 ? C.purple : C.green);
  } else if (i === 5) {
    const nodes = [
      ['Operator / approver', 64, 335, 230, 95],
      ['OIDC identity provider', 455, 242, 360, 70],
      ['KubeSentinel platform', 455, 350, 360, 95],
      ['Kubernetes API', 966, 335, 250, 95],
      ['GitHub / optional AWS', 455, 505, 360, 70],
    ];
    nodes.forEach(([label, x, y, w, h], j) => {
      shape(s, x, y, w, h, j === 2 ? '#28614b' : '#292d32');
      text(s, label, x + 18, y + 20, w - 36, h - 24, 23, C.fg, true);
    });
    shape(s, 294, 384, 161, 2, C.green); text(s, 'scoped HTTPS', 306, 347, 145, 30, 16, C.muted);
    shape(s, 815, 384, 151, 2, C.green); text(s, 'scoped RBAC', 826, 347, 145, 30, 16, C.muted);
    shape(s, 633, 312, 2, 38, C.green);
    shape(s, 633, 445, 2, 60, C.green);
    text(s, 'User identity, execution and delivery are separate trust boundaries.', 66, 601, 1125, 40, 22, C.muted);
  } else if (d.kind === 'components') {
    text(s, 'Container view', 66, 241, 400, 32, 20, C.green, true);
    ['Next.js web', 'FastAPI', 'SQL / Redis', 'Go operator'].forEach((v, j) => {
      const x = 64 + j * 296;
      shape(s, x, 290, 265, 85, j === 3 ? '#292735' : '#20332c');
      text(s, v, x + 18, 312, 231, 50, 26, C.fg, true);
      if (j < 2) shape(s, x + 266, 331, 29, 2, C.green);
    });
    text(s, 'API component view', 66, 421, 500, 32, 20, C.green, true);
    ['Identity + scope', 'Queries + incidents', 'Policy + audit', 'Approval bridge'].forEach((v, j) => {
      const x = 64 + j * 296;
      shape(s, x, 472, 265, 85, '#292d32');
      text(s, v, x + 18, 492, 231, 52, 23, C.fg, true);
    });
    text(s, 'Execution is independently authorized; stores are not instruction channels.', 66, 603, 1125, 36, 20, C.muted);
  } else if (i === 8) {
    ['Prometheus + KSM', 'OTel to Loki', 'Kubernetes events'].forEach((v, j) => {
      shape(s, 64, 247 + j * 115, 290, 80, j === 1 ? '#292735' : '#20332c');
      text(s, v, 82, 270 + j * 115, 256, 48, 24, C.fg, true);
      shape(s, 354, 287 + j * 115, 90, 2, C.green);
    });
    shape(s, 443, 287, 2, 230, C.green); shape(s, 443, 402, 75, 2, C.green);
    shape(s, 518, 351, 285, 105, '#20332c');
    text(s, 'Scoped evidence APIs', 536, 375, 249, 70, 26, C.fg, true);
    shape(s, 804, 402, 110, 2, C.green);
    shape(s, 914, 351, 302, 105, '#292735');
    text(s, 'Grafana + incident views', 932, 375, 266, 70, 26, C.fg, true);
    text(s, 'Bounded queries, retention and cardinality; explicit behavior during outages.', 66, 594, 1125, 40, 22, C.muted);
  } else if (d.kind === 'flow') {
    d.points.forEach((v, j) => {
      const x = 64 + j * 234;
      shape(s, x, 304, 208, 166, j % 2 ? '#292735' : '#20332c');
      text(s, `0${j + 1}`, x + 18, 323, 160, 30, 17, C.green, true);
      text(s, v, x + 18, 360, 172, 96, 23, C.fg, true);
      if (j < 4) { shape(s, x + 209, 372, 23, 2, C.green); }
    });
    text(s, d.notes.split('. ')[0] + '.', 66, 508, 1125, 90, 24, C.muted);
  } else if (d.kind === 'ml') {
    chart(s, 'Precision and recall (synthetic)', ['Rules', 'Robust', 'Forest'], [
      { name: 'Precision', values: Object.values(ml.detectors).map(v => v.precision), fill: '#168778' },
      { name: 'Recall', values: Object.values(ml.detectors).map(v => v.recall), fill: '#7770b6' },
    ], 64, 241, 690, 344, 1);
    const m = ml.detectors.isolation_forest.confusion_matrix;
    text(s, 'Isolation Forest', 798, 245, 380, 35, 24, C.green, true);
    text(s, 'Actual ↓  /  Predicted →', 798, 288, 380, 32, 18, C.muted);
    ['Normal', 'Anomaly'].forEach((v, j) => text(s, v, 853 + j * 153, 327, 150, 30, 17, C.muted));
    m.forEach((row, r) => row.forEach((value, c) => {
      shape(s, 825 + c * 170, 365 + r * 91, 155, 76, value > 75 ? '#28614b' : '#292d32');
      text(s, String(value), 855 + c * 170, 382 + r * 91, 105, 45, 34, C.fg, true);
    }));
    text(s, 'Rows: normal, anomaly. Small synthetic sample; no production accuracy claim.', 66, 607, 1120, 31, 18, C.muted);
  } else if (d.kind === 'screenshot') {
    s.images.add({ blob: new Uint8Array(await fs.readFile(path.join(ROOT, 'docs/portfolio/figures/dashboard-crop.png'))), contentType: 'image/png', alt: 'Actual dashboard browser capture with synthetic mode label', fit: 'contain', position: { left: 64, top: 235, width: 765, height: 379 } });
    paragraphs(s, d.points, 859, 247, 345, 86, 21);
  } else if (d.kind === 'recovery') {
    chart(s, 'Terminal action state (record count)', Object.keys(evidence.action_outcomes), [
      { name: 'Actions', values: Object.values(evidence.action_outcomes), fill: '#168778' },
    ], 64, 244, 640, 344);
    text(s, '10 s', 770, 255, 400, 80, 60, C.green, true);
    text(s, 'Observation → apply\nIncludes human approval', 770, 340, 400, 75, 23, C.muted);
    text(s, '36 s', 770, 438, 400, 80, 60, C.purple, true);
    text(s, 'Verification interval\nOne approved scale example', 770, 520, 420, 70, 23, C.muted);
    text(s, 'One isolated run; no repeated baseline or recovery SLA.', 66, 608, 1100, 31, 18, C.muted);
  } else if (d.kind === 'load') {
    const cats = load.summaries.map(t => `${t.concurrency}/${t.repetition + 1}`);
    chart(s, 'Throughput: requests/s', cats, [{ name: 'RPS', values: load.summaries.map(t => t.requests_per_second), fill: '#168778' }], 64, 244, 555, 330);
    chart(s, 'Latency: ms per trial', cats, ['p50_ms', 'p95_ms', 'p99_ms'].map((k, j) => ({ name: k.slice(0, 3), values: load.summaries.map(t => t[k]), fill: ['#168778', '#7770b6', '#be883e'][j] })), 650, 244, 566, 330);
    text(s, 'Labels = concurrency / repetition. Health only; no DB, cluster, CPU/memory or HPA measurement.', 66, 599, 1130, 45, 19, C.muted);
  } else if (d.kind === 'cost') {
    chart(s, 'Illustrative monthly USD', ['Dev', 'Demo'], [{ name: 'Assumed subtotal', values: [211.5, 324], fill: '#168778' }], 64, 244, 550, 340);
    paragraphs(s, d.points, 652, 245, 560, 85, 22);
    text(s, 'Budget inputs are assumptions, not current prices. Complete application costs are higher.', 66, 607, 1100, 33, 19, C.muted);
  } else {
    paragraphs(s, d.points, 66, 243, 1125, d.points.length > 4 ? 73 : 89, d.kind === 'stack' ? 26 : 27);
  }
}
const candidate = path.join(stage, `candidate-${revision}.pptx`);
await (await PresentationFile.exportPptx(p)).save(candidate);
const result = await finalizePresentation({ workspaceDir: ROOT, candidatePath: candidate, finalPath,
  pythonExecutable: process.env.DOCS_PYTHON,
  integrityValidatorPath: path.join(skill, 'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath: path.join(skill, 'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs: ['--expected-slide-size-emu', '12192000,6858000', '--validate-bullet-geometry', '--validate-heading-fit'],
  explicitTotalSlideCount: 25, requiredNativeChartOwnerSlides: [11, 20, 21, 22],
  materializeLiteralChartWorkbooks: true, fontPolicy: { basis: 'design', families: ['Arial'] },
  verifyArtifactToolImport: true, receiptPath: path.join(stage, `validation-${revision}.json`),
});
console.log(JSON.stringify(result));
await fs.copyFile(finalPath, path.join(ROOT, 'KubeSentinel-AI-Presentation.pptx'));
