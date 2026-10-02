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
