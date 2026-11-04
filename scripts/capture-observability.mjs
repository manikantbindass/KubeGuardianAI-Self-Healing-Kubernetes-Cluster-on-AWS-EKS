import { chromium } from "@playwright/test";
import { mkdir, readFile } from "node:fs/promises";
const directory = ".cache/observability/screenshots";
await mkdir(directory, { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, colorScheme: "dark" });
  for (const uid of ["cluster-overview", "namespace-workload", "application-performance", "incident-timeline", "recovery-history", "slo-error-budget"]) {
    const response = await page.goto(`http://127.0.0.1:3300/d/sentinel-${uid}?orgId=1&from=now-15m&to=now&theme=dark&kiosk`, { waitUntil: "networkidle", timeout: 60000 });
    if (!response?.ok()) throw new Error(`Grafana dashboard failed: ${uid}`);
    const definition = JSON.parse(await readFile(`infrastructure/helm/observability/dashboards/${uid}.json`, "utf8"));
    await page.getByText(definition.panels[0].title, { exact: true }).first().waitFor();
    await page.waitForTimeout(6000);
    await page.screenshot({ path: `${directory}/${uid}.png`, fullPage: true });
  }
  await page.goto("http://127.0.0.1:3200/status", { waitUntil: "networkidle" });
  await page.getByText("Telemetry incidents", { exact: true }).waitFor();
  await page.screenshot({ path: `${directory}/incident-app.png`, fullPage: true });
} finally { await browser.close(); }
