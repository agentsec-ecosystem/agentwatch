import { test } from "@playwright/test";
import { mkdirSync } from "node:fs";

// Field-test screenshot capture (M23, FT-36).
//
// Writes the exact image set that docs/guides/user-guide.md links to
// (relative paths `../assets/screenshots/<name>.png`). The harness points
// FT_SCREENSHOT_DIR at docs/assets/screenshots so the user-guide images stay
// fresh, then copies them into the case artifacts.
const outDir = process.env.FT_SCREENSHOT_DIR || "docs/assets/screenshots";
mkdirSync(outDir, { recursive: true });

async function shot(page: import("@playwright/test").Page, name: string) {
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.screenshot({ path: `${outDir}/${name}.png`, fullPage: true });
}

test.describe("Field-test screenshots (user guide)", () => {
  test("dashboard-overview", async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector("body", { timeout: 10_000 });
    await shot(page, "dashboard-overview");
  });

  test("dashboard-to-fleet", async ({ page }) => {
    await page.goto("/");
    const card = page.locator("a[href*='fleet'], [data-testid='agent-card'], .agent-card").first();
    if (await card.count()) {
      await card.click().catch(() => {});
      await page.waitForTimeout(800);
    } else {
      await page.goto("/fleet");
    }
    await shot(page, "dashboard-to-fleet");
  });

  test("fleet-default", async ({ page }) => {
    await page.goto("/fleet");
    await page.waitForSelector("table", { timeout: 10_000 }).catch(() => {});
    await shot(page, "fleet-default");
  });

  test("anomalies-default", async ({ page }) => {
    await page.goto("/anomalies");
    await page.waitForSelector(".space-y-2\\.5 > button, article, body", { timeout: 10_000 }).catch(() => {});
    await shot(page, "anomalies-default");
  });

  test("anomalies-critical", async ({ page }) => {
    await page.goto("/anomalies");
    const select = page.locator("select[aria-label='Filter by severity']");
    if (await select.count()) {
      await select.selectOption({ value: "critical" }).catch(() => {});
      await page.waitForTimeout(600);
    }
    await shot(page, "anomalies-critical");
  });

  test("timeline-normal", async ({ page }) => {
    // Reach the timeline via the anomaly inbox click-through.
    await page.goto("/anomalies");
    const item = page.locator(".space-y-2\\.5 > button").first();
    if (await item.count()) {
      await item.click().catch(() => {});
      await page.waitForTimeout(1000);
    } else {
      await page.goto("/timeline");
    }
    await shot(page, "timeline-normal");
  });

  test("timeline-spans", async ({ page }) => {
    await page.goto("/anomalies");
    const item = page.locator(".space-y-2\\.5 > button").first();
    if (await item.count()) {
      await item.click().catch(() => {});
      await page.waitForTimeout(1000);
    }
    // Expand the first span/row if present.
    const toggle = page.locator("[aria-expanded], button:has-text('▸'), summary").first();
    if (await toggle.count()) {
      await toggle.click().catch(() => {});
      await page.waitForTimeout(500);
    }
    await shot(page, "timeline-spans");
  });

  test("compare-deltas", async ({ page }) => {
    await page.goto("/compare");
    const agent = page.locator("input").first();
    await agent.fill("research_crew").catch(() => {});
    await page.locator("input[placeholder='v1.0']").fill("v1.2.0").catch(() => {});
    await page.locator("input[placeholder='v2.0']").fill("v1.3.0").catch(() => {});
    await page.waitForTimeout(1200);
    await shot(page, "compare-deltas");
  });
});
