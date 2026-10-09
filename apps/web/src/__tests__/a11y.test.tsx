/**
 * Automated accessibility (a11y) checks for the operator UI (WBS 7.8, #63).
 *
 * Renders each operator view with mocked API data and runs axe-core against
 * the result, failing on any violation. This makes the promise in
 * `docs/design/ui-accessibility.md` real: the a11y baseline is verified by the
 * UI test suite, not just manual review.
 *
 * jsdom has no layout engine, so the `color-contrast` rule is disabled here;
 * contrast remains a manual/Playwright check (see the design doc). The seeded
 * violation test at the bottom proves this harness actually fails on a real
 * violation rather than silently passing.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactElement } from "react";
import axe from "axe-core";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "../pages/Dashboard";
import FleetHealthPage from "../pages/FleetHealth";
import RunTimelinePage from "../pages/RunTimeline";
import VersionComparePage from "../pages/VersionCompare";
import AnomalyInboxPage from "../pages/AnomalyInbox";
import DetectorTelemetryPage from "../pages/DetectorTelemetry";
import {
  anomaliesResponse,
  attributionResponse,
  compareResponse,
  detectorTelemetryResponse,
  fleetResponse,
  siemHealthResponse,
  timelineResponse,
} from "./fixtures";

// Mock the network boundary (the API client) so pages render their data state.
vi.mock("../api/client", () => ({
  api: {
    getFleet: vi.fn(),
    getRunTimeline: vi.fn(),
    getCompare: vi.fn(),
    getAnomalies: vi.fn(),
    getHealth: vi.fn(),
    getDetectorTelemetry: vi.fn(),
    getAttribution: vi.fn(),
    getSiemHealth: vi.fn(),
  },
}));

import { api } from "../api/client";

/** axe options: jsdom cannot compute colors, so contrast is checked elsewhere. */
const AXE_OPTIONS = { rules: { "color-contrast": { enabled: false } } };

/**
 * Runs axe against the rendered container and fails with a readable list of
 * any violations (rule id, impact, and the offending HTML).
 */
async function expectNoA11yViolations(container: HTMLElement) {
  const results = await axe.run(container, AXE_OPTIONS);
  const summary = results.violations.map((v) => ({
    id: v.id,
    impact: v.impact,
    nodes: v.nodes.map((n) => n.html),
  }));
  expect(summary).toEqual([]);
}

/** Renders a page inside a router; `path` controls the active route. */
function renderPage(ui: ReactElement, path = "/") {
  return render(
    <MemoryRouter
      initialEntries={[path]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <Routes>
        <Route path="/runs/:runId" element={ui} />
        <Route path="*" element={ui} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.mocked(api.getFleet).mockResolvedValue(fleetResponse);
  vi.mocked(api.getRunTimeline).mockResolvedValue(timelineResponse);
  vi.mocked(api.getCompare).mockResolvedValue(compareResponse);
  vi.mocked(api.getAnomalies).mockResolvedValue(anomaliesResponse);
  vi.mocked(api.getDetectorTelemetry).mockResolvedValue(detectorTelemetryResponse);
  vi.mocked(api.getAttribution).mockResolvedValue(attributionResponse);
  vi.mocked(api.getSiemHealth).mockResolvedValue(siemHealthResponse);
});

describe("operator UI accessibility", () => {
  it("Dashboard has no a11y violations", async () => {
    const { container } = renderPage(<DashboardPage />);
    await screen.findByText("Total Runs");
    await expectNoA11yViolations(container);
  });

  it("Fleet Health has no a11y violations", async () => {
    const { container } = renderPage(<FleetHealthPage />);
    await screen.findByRole("table");
    await expectNoA11yViolations(container);
  });

  it("Run Timeline has no a11y violations", async () => {
    const { container } = renderPage(<RunTimelinePage />, "/runs/run_demo");
    await screen.findByText("Research Crew");
    await expectNoA11yViolations(container);
  });

  it("Agent Detail panel has no a11y violations", async () => {
    const { container } = renderPage(<RunTimelinePage />, "/runs/run_demo");
    await screen.findByText("Research Crew");
    // Selecting a span reveals the Agent Detail (span detail) panel.
    fireEvent.click(screen.getByRole("button", { name: /web_search/ }));
    await screen.findByText("Span ID");
    await expectNoA11yViolations(container);
  });

  it("Version Compare has no a11y violations", async () => {
    const { container } = renderPage(<VersionComparePage />);
    fireEvent.change(screen.getByPlaceholderText("v1.0"), { target: { value: "v1.2.0" } });
    fireEvent.change(screen.getByPlaceholderText("v2.0"), { target: { value: "v1.3.0" } });
    await screen.findByText("Tool Usage Comparison");
    await expectNoA11yViolations(container);
  });

  it("Anomaly Inbox has no a11y violations", async () => {
    const { container } = renderPage(<AnomalyInboxPage />);
    await screen.findByText("Repeated tool call detected.");
    await expectNoA11yViolations(container);
  });

  it("Operator Console has no a11y violations", async () => {
    const { container } = renderPage(<DetectorTelemetryPage />, "/operator");
    await screen.findByText("Operator Console");
    await screen.findByText("research_crew");
    await expectNoA11yViolations(container);
  });

  it("Operator Console renders outcomes as text, not colour alone", async () => {
    renderPage(<DetectorTelemetryPage />, "/operator");
    await screen.findByText("loop");
    expect(screen.getByText("fired")).toBeInTheDocument();
    expect(screen.getByText("suppressed")).toBeInTheDocument();
  });

  it("Version Compare inputs expose accessible names", async () => {
    renderPage(<VersionComparePage />);
    expect(screen.getByRole("textbox", { name: "Agent" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Version A" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Version B" })).toBeInTheDocument();
  });

  it("detects a seeded violation (harness self-check)", async () => {
    const { container } = render(
      <div>
        <input type="text" />
      </div>
    );
    const results = await axe.run(container, AXE_OPTIONS);
    expect(results.violations.map((v) => v.id)).toContain("label");
  });
});
