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

## Generated per-detector metrics (M26 DET-3)

<!-- BEGIN GENERATED: detector-metrics -->
_Generated from the 147-scenario field-test rule matrix (corpus `detector-corpus v1`, offline, scripted pool). Rule detectors non-silent: 40/40 (100%)._

| Detector | TP | FP | FN | TN | TPR | FPR |
|---|---|---|---|---|---|---|
| `anomaly_cluster` | 1 | 0 | 0 | 1 | 100.0% | 0.0% |
| `approval_latency` | 3 | 0 | 0 | 2 | 100.0% | 0.0% |
| `argument_loop` | 2 | 0 | 0 | 2 | 100.0% | 0.0% |
| `cascading_retry` | 1 | 0 | 0 | 1 | 100.0% | 0.0% |
| `cost_efficiency` | 2 | 0 | 0 | 2 | 100.0% | 0.0% |
| `cost_spike` | 3 | 0 | 0 | 2 | 100.0% | 0.0% |
| `cost_vs_baseline` | 3 | 0 | 0 | 2 | 100.0% | 0.0% |
| `credential-hygiene` | 1 | 0 | 0 | 1 | 100.0% | 0.0% |
| `denied-cluster` | 2 | 0 | 0 | 1 | 100.0% | 0.0% |
| `empty_response` | 1 | 0 | 0 | 1 | 100.0% | 0.0% |
| `escalation_rate` | 3 | 0 | 0 | 2 | 100.0% | 0.0% |
| `first_run_heuristic` | 1 | 0 | 0 | 1 | 100.0% | 0.0% |
| `inactivity` | 3 | 0 | 0 | 2 | 100.0% | 0.0% |
| `indeterminate_status` | 1 | 0 | 0 | 1 | 100.0% | 0.0% |
| `injection-shape` | 1 | 0 | 0 | 1 | 100.0% | 0.0% |
| `intervention_frequency` | 2 | 0 | 0 | 2 | 100.0% | 0.0% |
| `intervention_rejection` | 2 | 0 | 0 | 2 | 100.0% | 0.0% |
| `loop` | 3 | 0 | 0 | 2 | 100.0% | 0.0% |
| `low_output` | 1 | 0 | 0 | 1 | 100.0% | 0.0% |
| `max_step_hit` | 1 | 0 | 0 | 1 | 100.0% | 0.0% |
| `network-tool` | 1 | 0 | 0 | 1 | 100.0% | 0.0% |
| `output_drift` | 3 | 0 | 0 | 2 | 100.0% | 0.0% |
| `pattern_loop` | 2 | 0 | 0 | 1 | 100.0% | 0.0% |
| `per_tool_cost_spike` | 3 | 0 | 0 | 2 | 100.0% | 0.0% |
| `premature_completion` | 1 | 0 | 0 | 1 | 100.0% | 0.0% |
| `recovery_path` | 3 | 0 | 0 | 2 | 100.0% | 0.0% |
| `redundant_tool_call` | 2 | 0 | 0 | 2 | 100.0% | 0.0% |
| `retry_storm` | 3 | 0 | 0 | 2 | 100.0% | 0.0% |
| `run_duration` | 3 | 0 | 0 | 2 | 100.0% | 0.0% |
| `run_frequency_anomaly` | 3 | 0 | 0 | 2 | 100.0% | 0.0% |
| `specific_tool_error` | 2 | 0 | 0 | 2 | 100.0% | 0.0% |
| `step_efficiency` | 3 | 0 | 0 | 2 | 100.0% | 0.0% |
| `systemic_retry` | 1 | 0 | 0 | 1 | 100.0% | 0.0% |
| `token_explosion` | 3 | 0 | 0 | 2 | 100.0% | 0.0% |
| `tool_error_rate` | 2 | 0 | 0 | 2 | 100.0% | 0.0% |
| `tool_latency` | 3 | 0 | 0 | 2 | 100.0% | 0.0% |
| `tool_timeout` | 3 | 0 | 0 | 2 | 100.0% | 0.0% |
| `transient_retry` | 1 | 0 | 0 | 1 | 100.0% | 0.0% |
| `wasted_tool_calls` | 2 | 0 | 0 | 2 | 100.0% | 0.0% |
| `write-storm` | 2 | 0 | 0 | 1 | 100.0% | 0.0% |
<!-- END GENERATED: detector-metrics -->

