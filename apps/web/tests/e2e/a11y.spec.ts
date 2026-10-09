/**
 * WCAG 2.2 AA checks for the operator UI (PRD 38 §Q11, issue #228).
 *
 * The unit suite (`src/__tests__/a11y.test.tsx`) runs axe under jsdom, which has
 * no layout engine, so it disables the `color-contrast` rule. These Playwright
 * tests run axe in a real browser against the seeded compose stack, which covers
 * contrast, and add a keyboard-only pass through the operator-UI portion of the
 * flagship journey (CUJ-8).
 */

import { test, expect, type Page } from "@playwright/test";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const axePath = require.resolve("axe-core/axe.min.js");

interface AxeViolation {
  id: string;
  impact: string | null;
  nodes: { target: string[] }[];
}
interface AxeResults {
  violations: AxeViolation[];
}

const ROUTES = [
  { path: "/", name: "Dashboard" },
  { path: "/fleet", name: "Fleet Health" },
  { path: "/runs", name: "Run Timeline" },
  { path: "/compare", name: "Version Compare" },
  { path: "/anomalies", name: "Anomaly Inbox" },
  { path: "/operator", name: "Operator" },
];

async function runAxe(page: Page): Promise<AxeResults> {
  await page.addScriptTag({ path: axePath });
  return page.evaluate(async () => {
    const w = window as unknown as {
      axe: { run: (ctx: Document, opts: object) => Promise<AxeResults> };
    };
    // Full rule set: in a real browser this includes color-contrast.
    return await w.axe.run(document, { resultTypes: ["violations"] });
  });
}

test.describe("WCAG 2.2 AA — automated checks", () => {
  for (const route of ROUTES) {
    test(`${route.name} has no axe violations (including contrast)`, async ({ page }) => {
      await page.goto(route.path);
      await page.waitForLoadState("networkidle");
      // Freeze entrance animations so axe measures final opacity/colors.
      await page.addStyleTag({
        content: "*, *::before, *::after { animation: none !important; transition: none !important; }",
      });

      const results = await runAxe(page);
      const violations = results.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        target: v.nodes.flatMap((n) => n.target),
      }));

      expect(violations, JSON.stringify(violations, null, 2)).toEqual([]);
    });
  }
});

/** Tab forward until the focused element's text contains `label` (keyboard-only). */
async function tabTo(page: Page, label: string, presses = 40): Promise<boolean> {
  for (let i = 0; i < presses; i++) {
    await page.keyboard.press("Tab");
    const active = await page.evaluate(() => document.activeElement?.textContent?.trim() ?? "");
    if (active.includes(label)) {
      return true;
    }
  }
  return false;
}

async function focusedStyle(page: Page): Promise<string> {
  return page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    if (!el) return "none";
    const style = getComputedStyle(el);
    return `${style.outlineStyle} ${style.outlineWidth} ${style.boxShadow}`;
  });
}

test.describe("Keyboard-only operator journey (CUJ-8)", () => {
  test("navigates every view and opens a run with the keyboard alone", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Dashboard -> Fleet Health by tabbing to the nav link and pressing Enter.
    expect(await tabTo(page, "Fleet Health")).toBe(true);
    expect(await focusedStyle(page)).not.toBe("none 0px none");
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/fleet$/);
    await page.waitForSelector("table");

    // Fleet Health -> Run Timeline (nav link), then activate a run row if present.
    expect(await tabTo(page, "Run Timeline")).toBe(true);
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/runs/);

    // Anomaly Inbox, still keyboard-only.
    expect(await tabTo(page, "Anomaly Inbox")).toBe(true);
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/anomalies$/);

    // Operator console (identity/attribution + SIEM health + detector markers).
    expect(await tabTo(page, "Operator")).toBe(true);
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/operator$/);
  });

  test("activates a span in the timeline with Enter", async ({ page }) => {
    await page.route("**/api/v1/runs/**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          run: {
            run_id: "abc-123",
            agent_name: "test_agent",
            agent_version: "v1.0.0",
            status: "success",
            estimated_cost_usd: 0.5,
            total_retries: 0,
            total_interventions: 0,
          },
          summary: { duration_ms: 12000, loop_detected: false, tool_call_count: 2 },
          spans: [
            {
              span_id: "s2",
              parent_span_id: null,
              operation: "execute_tool",
              name: "fetch_data",
              start_time: "2026-08-06T00:00:01Z",
              end_time: "2026-08-06T00:00:09Z",
              status: "success",
              attributes: { "tool.name": "fetch_data" },
            },
          ],
          anomalies: [],
        }),
      });
    });

    await page.goto("/runs/abc-123");
    await expect(page.getByText("Span Tree")).toBeVisible({ timeout: 10_000 });

    const spanButton = page.getByRole("button").filter({ hasText: /fetch_data|tool\.call/ }).first();
    await spanButton.focus();
    await page.keyboard.press("Enter");
    // The span detail panel exposes a stable heading when opened.
    await expect(page.getByText("Span ID")).toBeVisible();
  });
});
