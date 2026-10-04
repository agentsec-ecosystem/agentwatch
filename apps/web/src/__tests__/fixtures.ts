/**
 * Shared API fixtures for component/accessibility tests.
 *
 * These mirror the **normalized** shapes in `src/types/api.ts` (i.e. what the
 * API client returns to pages), so pages render their real data state without
 * a network call. Keep every field present — partial fixtures silently drift
 * from the real contract.
 */

import type {
  AnomalyListResponse,
  CompareResponse,
  FleetResponse,
  RunTimelineResponse,
} from "../types/api";

/** Fleet rollup with two agent/version/workload groups. */
export const fleetResponse: FleetResponse = {
  groups: [
    {
      agent_name: "research_crew",
      agent_version: "v1.2.0",
      workload_type: "analysis",
      total_runs: 12,
      success_count: 10,
      error_count: 2,
      loop_count: 1,
      anomaly_count: 3,
      avg_duration_ms: 4200,
      avg_cost: 0.0123,
    },
    {
      agent_name: "support_bot",
      agent_version: "v2.0.1",
      workload_type: "triage",
      total_runs: 8,
      success_count: 8,
      error_count: 0,
      loop_count: 0,
      anomaly_count: 0,
      avg_duration_ms: 1500,
      avg_cost: 0.0045,
    },
  ],
};

/** Run timeline with a root span, a child span, and one anomaly. */
export const timelineResponse: RunTimelineResponse = {
  run_id: "run_demo",
  agent_name: "research_crew",
  agent_version: "v1.2.0",
  status: "success",
  duration_ms: 4200,
  estimated_cost: 0.0123,
  loop_count: 1,
  loop_detected: true,
  started_at: "2026-01-01T00:00:00Z",
  completed_at: "2026-01-01T00:00:04Z",
  spans: [
    {
      span_id: "span_root",
      parent_span_id: null,
      operation: "invoke_agent",
      name: "Research Crew",
      start_time: "2026-01-01T00:00:00Z",
      end_time: "2026-01-01T00:00:04Z",
      status: "success",
      attributes: { model: "claude-sonnet" },
    },
    {
      span_id: "span_child",
      parent_span_id: "span_root",
      operation: "execute_tool",
      name: "web_search",
      start_time: "2026-01-01T00:00:01Z",
      end_time: "2026-01-01T00:00:02Z",
      status: "success",
      attributes: {},
    },
  ],
  anomalies: [
    {
      id: "anom_1",
      anomaly_type: "loop",
      severity: "warning",
      explanation: "Repeated tool call detected.",
      detected_at: "2026-01-01T00:00:03Z",
    },
  ],
};

/** Version comparison with positive deltas and one tool delta. */
export const compareResponse: CompareResponse = {
  left: { version: "v1.2.0", run_count: 12 },
  right: { version: "v1.3.0", run_count: 15 },
  deltas: { avg_cost_usd: 0.0021, retry_rate: 0.03, success_rate: -0.02 },
  tool_deltas: [
    { tool_name: "web_search", left_count: 20, right_count: 25, delta: 5 },
  ],
};

/** Paginated anomaly list with one item. */
export const anomaliesResponse: AnomalyListResponse = {
  items: [
    {
      id: "anom_1",
      run_id: "run_demo",
      agent_name: "research_crew",
      anomaly_type: "loop",
      severity: "warning",
      explanation: "Repeated tool call detected.",
      detected_at: "2026-01-01T00:00:03Z",
    },
  ],
  total: 1,
  limit: 1000,
  offset: 0,
};
