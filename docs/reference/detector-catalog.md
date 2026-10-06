# Reference — Detector Catalog

**BLUF:** The detectors restored from the shipped project: 35 rule-based across 7 categories, plus 5
LLM-augmented (feature-flagged, default off). Thresholds and false-positive risks are per-workload and
configurable.

## Rule-based (35)

| Category | Count | Detectors |
|---|---|---|
| Tool Execution | 8 | argument_loop, tool_loop, tool_error_rate, tool_latency_spike, redundant_tool_call, wasted_tool_calls, tool_count_exhaustion, tool_mix_anomaly |
| Cost & Resource | 6 | cost_spike, token_explosion, per_tool_cost, wasted_cost, cost_vs_baseline, step_efficiency |
| Runtime & Completion | 5 | duration_anomaly, premature_completion, step_exhaustion, inactivity, early_stop |
| Retry & Recovery | 5 | retry_storm, cascading_retry, recovery_complexity, retry_success_rate, escalation_rate |
| Interaction & Control | 4 | intervention_frequency, approval_latency, human_loop_count, control_surface_anomaly |
| Output Quality | 4 | empty_response, low_output, indeterminate_status, output_drift |
| Cross-Run Patterns | 3 | anomaly_cluster, run_frequency_anomaly, first_run_heuristic |

## LLM-augmented (5, optional)

SemanticLoop · Hallucination · GoalDrift · QualityDegradation · ConfusionPattern.

> Research-grade in the shipped project (10-trace sample); treat as signals, not enforcement.

## Output

Structured anomaly records: `severity`, `explanation`, `evidence`. Thresholds are configurable per detector
per workload. Method: trailing baselines over fixed thresholds (AgentWatch lesson).

## Status

Thresholds + false-positive-risk table to be backfilled from the shipped project during v0.2.0.

## Coverage & classification (M26 DET-2)

The field-test scenario matrix (`analytics.scenario_validation`, 143 boundary + precision scenarios)
runs every **rule** detector offline and deterministically; the DET-2 gate
(`scripts/detector_eval.py --scenarios`, tested in
`services/analytics/tests/test_detector_non_silent.py`) requires **≥ 80 % of rule detectors non-silent** and
currently reports **38/38 (100 %)**. Classification:

- **Offline rule detectors (38):** evaluated from synthetic spans/summaries; all fire on at least one positive
  scenario (none retired, none silent).
- **Baseline/cohort detectors:** the DB-backed family (`cost_vs_baseline`, `run_duration`, `escalation_rate`,
  `output_drift`, `anomaly_cluster`, `run_frequency_anomaly`, `first_run_heuristic`) is evaluated with a
  **scripted pool** (preset `fetchrow`/`fetch` values) — no live Postgres; reclassified as *baseline-required
  offline-drivable*, not silent.
- **LLM-augmented (5):** excluded from the rule gate; they need a live local model and stay feature-flagged
  (default off).

The detectors were not rewritten to fit the corpus; instead the corpus was reconciled to the field-test scenarios
so the count claim ("35+ rule detectors") is backed by measured firing. Real captured traces (Claude Code
transcripts, Cursor session-tracer traces, Codex rollouts) are replayed through the detectors in
`services/analytics/tests/test_detector_real_traces.py` — every detector accepts runs derived from the real
corpus without error.


## Claude Code hook detectors (M6 addition L1)

Purpose-built for Claude Code hook records (observability only, never enforcement — PRD 14):

| Type | Fires when | Evidence |
|---|---|---|
| `write-storm` | ≥ 8 file-modifying tool calls (`Write`/`Edit`/`MultiEdit`/`NotebookEdit`) in one run | count, threshold, tools |
| `denied-cluster` | ≥ 3 denied/errored tool calls in one run | count, threshold |
| `network-tool` | network-capable tools used (`curl`/`wget`/`http`/`fetch`/`webfetch`) | count, tools |

Implemented in `services/analytics/src/analytics/detectors/claude_code.py`; registered by
`create_all_detectors()` (38 rule+LLM detectors total).
