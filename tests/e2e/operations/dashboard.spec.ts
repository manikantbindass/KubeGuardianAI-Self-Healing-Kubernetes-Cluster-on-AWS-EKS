import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFileSync, mkdirSync } from "node:fs";
const env = Object.fromEntries(
  readFileSync(".env", "utf8")
    .split(/\r?\n/)
    .filter((l) => l && !l.startsWith("#") && l.includes("="))
    .map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1)]),
);
const token = process.env.OPS_DEV_TOKEN ?? env.OPS_DEV_TOKEN;
const viewerToken =
  process.env.OPS_DEV_VIEWER_TOKEN ?? env.OPS_DEV_VIEWER_TOKEN;
async function login(page: Page, value = token) {
  await page.goto("/");
  await page.getByLabel("Local development token").fill(value);
  await page.getByRole("button", { name: "Enter workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
}
async function demo(page: Page) {
  await page.getByLabel("Data mode", { exact: true }).selectOption("demo");
  await expect(
    page.getByText("Synthetic demonstration", { exact: false }),
  ).toBeVisible();
}
async function accessible(page: Page) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    result.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => n.target),
    })),
  ).toEqual([]);
}
test("real mode, authentication boundary, and explicit demo gallery", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Connect to your/ }),
  ).toBeVisible();
  expect((await page.request.get("/api/backend/ops/view")).status()).toBe(401);
  await login(page);
  await expect(page.getByLabel("Data mode")).toHaveValue("real");
  await expect(page.getByText("Your canvas is waiting.")).toBeVisible();
  await accessible(page);
  await demo(page);
  await expect(
    page.getByText("checkout-api", { exact: true }).first(),
  ).toBeVisible();
  await accessible(page);
  await page
    .locator(".workload-gallery")
    .getByRole("button", { name: /checkout-api/ })
    .click();
  await expect(
    page.getByRole("dialog", { name: "checkout-api" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
test("all twelve views, source failures, search and keyboard dialog", async ({
  page,
}) => {
  await login(page);
  await demo(page);
  for (const [path, heading] of [
    ["explorer", "Cluster Explorer"],
    ["workloads", "Nodes and Workloads"],
    ["metrics", "Live Metrics"],
    ["anomalies", "AI Anomaly Detection"],
    ["incidents", "Incident Center"],
    ["actions", "Self-Healing Actions"],
    ["policies", "Recovery Policies"],
    ["insights", "AI Insights"],
    ["audit", "Audit Logs"],
    ["infrastructure", "Infrastructure and Costs"],
    ["settings", "Settings"],
  ]) {
    await page.goto(`/${path}?mode=demo`);
    await expect(
      page.getByRole("heading", { name: heading, exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("Unable to load this view", { exact: true }),
    ).toHaveCount(0);
    await accessible(page);
  }
  await page.keyboard.press("Control+k");
  await expect(
    page.getByRole("dialog", { name: "Search workspace" }),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "Search all resources" })
    .fill("checkout-api");
  await expect(
    page
      .getByRole("dialog")
      .getByRole("button", { name: /checkout-api/ })
      .first(),
  ).toBeVisible();
  await page.keyboard.press("Escape");
});
test("preferences persist, cost scenario computes, demo decision creates audit", async ({
  page,
}) => {
  await login(page);
  await page.goto("/settings");
  await page.getByLabel("Polling interval").selectOption("30");
  await page.getByRole("button", { name: "Save preferences" }).click();
  await expect(page.getByText("Preferences saved.")).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Polling interval")).toHaveValue("30");
  await page.goto("/infrastructure");
  await page.getByRole("button", { name: /Calculate/ }).click();
  await expect(page.getByText(/YOUR SCENARIO.*730 HOURS/)).toBeVisible();
  await page.goto("/actions?mode=demo");
  await page
    .getByRole("row")
    .filter({ hasText: "Awaiting Approval" })
    .getByRole("button")
    .first()
    .click();
  await page
    .getByLabel("Decision reason")
    .fill("E2E synthetic rejection with audit");
  await page.getByLabel(/reviewed the target/).check();
  await page.getByRole("button", { name: "Reject plan" }).click();
  await expect(
    page.getByText("Synthetic decision recorded", { exact: true }),
  ).toBeVisible();
});
test("viewer cannot mutate recovery resources even through direct API", async ({
  page,
}) => {
  await login(page, viewerToken);
  await demo(page);
  const view = await (
    await page.request.get("/api/backend/ops/view?mode=demo")
  ).json();
  const row = view.resources.find(
    (r: { kind: string }) => r.kind === "RemediationPolicy",
  );
  const result = await page.request.post(
    `/api/backend/ops/policies/${row.id}?mode=demo`,
    {
      headers: { Origin: new URL(page.url()).origin },
      data: {
        expected_uid: row.uid,
        expected_version: row.resource_version,
        dry_run: false,
        cooldown_seconds: 60,
        maximum_actions: 2,
        maximum_replicas: 4,
        reason: "Must fail server authorization",
        idempotency_key: "e2e-viewer-denied-0001",
      },
    },
  );
  expect(result.status()).toBe(403);
  const csrf = await page.request.post("/api/backend/ops/preferences", {
    headers: { Origin: "https://attacker.invalid" },
    data: { refresh_seconds: 15, compact_tables: false, timezone: "UTC" },
  });
  expect(csrf.status()).toBe(403);
});
test("offline state stays real, refresh restores actual data", async ({
  page,
}) => {
  await login(page);
  await page.route("**/api/backend/ops/view**", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Controlled API outage" }),
    }),
  );
  await page.getByRole("button", { name: "Refresh workspace" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Controlled API outage" }),
  ).toContainText("Controlled API outage");
  await expect(page.getByLabel("Data mode")).toHaveValue("real");
  await page.unroute("**/api/backend/ops/view**");
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByText("Your canvas is waiting.")).toBeVisible();
});
test("responsive screenshots, reduced motion and layout budget", async ({
  page,
}) => {
  await login(page);
  await demo(page);
  mkdirSync("docs/screenshots/phase-07", { recursive: true });
  for (const [name, width, height] of [
    ["desktop", 1440, 1000],
    ["tablet", 834, 1112],
    ["mobile", 390, 844],
  ] as const) {
    await page.setViewportSize({ width, height });
    await expect(
      page.getByRole("heading", { name: /Complex systems/ }),
    ).toBeVisible();
    await expect
      .poll(() =>
        page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      )
      .toBe(true);
    await accessible(page);
    await page.screenshot({
      path: `docs/screenshots/phase-07/${name}.png`,
      fullPage: true,
    });
    if (name === "mobile") {
      await page.getByRole("button", { name: "Open navigation" }).click();
      await expect(
        page.getByRole("dialog", { name: "Workspace navigation" }),
      ).toBeVisible();
      await page.keyboard.press("Escape");
    }
  }
  expect(
    await page
      .locator(".canvas-orbits")
      .evaluate((el) => getComputedStyle(el).animationName),
  ).toBe("none");
  const payload = await page.evaluate(() =>
    performance
      .getEntriesByType("resource")
      .reduce((n, r) => n + (r as PerformanceResourceTiming).transferSize, 0),
  );
  expect(payload).toBeLessThan(12_000_000); // documented development-mode ceiling; not a Lighthouse score
});
