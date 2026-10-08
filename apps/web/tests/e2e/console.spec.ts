/**
 * Local console screenshots + a11y (M30 LUI-1/LUI-2; PRD 54; CUJ-24).
 *
 * The v0.2.0 local console (`agentwatch ui`) is a Python-served loopback UI, not
 * the analyst web app. This spec runs against a *live* console (started by
 * `scripts/fieldtest/console_playwright.py`) and recaptures its screenshots and
 * runs axe in a real browser. It skips only when `FT_CONSOLE_URL` is unset, so a
 * console run that is claimed but not exercised fails the case rather than
 * passing by default.
 */
import { test, expect, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const axePath = require.resolve("axe-core/axe.min.js");

const consoleUrl = process.env.FT_CONSOLE_URL || "";
const outDir = process.env.FT_SCREENSHOT_DIR || "docs/assets/screenshots";
mkdirSync(outDir, { recursive: true });

interface AxeViolation {
  id: string;
  impact: string | null;
  nodes: { target: string[] }[];
}
interface AxeResults {
  violations: AxeViolation[];
}

test.skip(!consoleUrl, "local console not running (set FT_CONSOLE_URL)");

async function shot(page: Page, name: string) {
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.screenshot({ path: `${outDir}/${name}.png`, fullPage: true });
}

test.describe("Local console (agentwatch ui)", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(consoleUrl);
  });

  test("console-overview renders and is captured", async ({ page }) => {
    await expect(page.getByRole("heading", { name: /agentwatch console/i })).toBeVisible({
      timeout: 10_000,
    });
    await page.waitForSelector("#sessions", { timeout: 10_000 });
    await shot(page, "console-overview");
  });

  test("console-signatures captured", async ({ page }) => {
    await page.waitForSelector("#signatures", { timeout: 10_000 });
    await shot(page, "console-signatures");
  });

  test("console has no axe violations (incl. contrast)", async ({ page }) => {
    await page.waitForSelector("#sessions", { timeout: 10_000 });
    await page.addScriptTag({ path: axePath });
    const results: AxeResults = await page.evaluate(async () => {
      const w = window as unknown as {
        axe: { run: (ctx: Document, opts: object) => Promise<AxeResults> };
      };
      return await w.axe.run(document, { resultTypes: ["violations"] });
    });
    const violations = results.violations.map((v) => ({
      id: v.id,
      impact: v.impact,
      target: v.nodes.flatMap((n) => n.target),
    }));
    expect(violations, JSON.stringify(violations, null, 2)).toEqual([]);
  });
});
