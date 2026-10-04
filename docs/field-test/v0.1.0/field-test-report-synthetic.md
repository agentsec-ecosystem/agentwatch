# Synthetic Corpus Report (Rule-Based) — M13.1 / v0.1.0

> Rule-based (no-LLM) validation of agentwatch detectors against the 1M-trace
> synthetic corpus. This is the baseline that the
> [synthetic-LLM validation plan](synthetic-llm-validation-plan.md) complements and
> compares against.

**Status:** published (M24 release evidence) · **Data generated:** 2026-08-04 ·
**Report published:** 2026-10-04

**BLUF:** the 20 rule-based detectors fired on **5,132,535 anomalies** across
**1,000,343 synthetic traces** (96.7% of traces had ≥1 anomaly), with no LLM in the
path. The corpus is **detector-dense by construction** — it exists to prove detectors
fire and to exercise boundary/correlation behaviour, **not** to estimate precision on
real agent traffic (see [FIELD_TEST_REPORT.md](FIELD_TEST_REPORT.md) §"Synthetic vs
real traces").

---

## 1. Corpus

Span-level OpenTelemetry traces generated for detector coverage.

| Metric | Value | Source |
|---|---|---|
| Parquet files | 290 | `data/traces2/synthetic/*.parquet` (footer metadata) |
| Span rows | 72,457,789 | parquet footer metadata |
| Traces processed | 1,000,343 | `without-llm/summary.json` |
| Agents | 10 (e.g. `BlipZorp`, `SnarfBlat`) | corpus design |
| Tools | 14 shared across agents | corpus design |
| On-disk size | ~4.2 GB | `du -sh data/traces2/synthetic` |

The corpus is **gitignored** (`data/`); only this report and the summary figures are
committed. Regeneration lives with the field-test harness (`scripts/fieldtest/`,
`m13-agents/`).

## 2. Method

For each trace, agentwatch's rule-based detectors run over the recorded span tree with
**no LLM calls** (`data/traces2/validations/synthetic/without-llm/`). Every anomaly
record is classified by detector type and severity; cross-detector co-firing is
computed pairwise.

## 3. Results

| Metric | Value |
|---|---|
| Traces processed | 1,000,343 |
| Traces with ≥1 anomaly | 967,386 (**96.7%**) |
| Total anomaly records | 5,132,535 (**≈5.13 per trace**) |
| Severity — critical | 2,586,131 |
| Severity — warning | 2,750,032 |

### 3.1 Detector fire rate

Share of processed traces on which each detector fired (as reported by the harness):

| Detector | Fire rate | Anomalies |
|---|---|---|
| `inactivity` | 93.4% | 934,408 |
| `tool_timeout` | 77.2% | 772,191 |
| `wasted_tool_calls` | 68.0% | 680,627 |
| `recovery_path` | 65.2% | 651,765 |
| `specific_tool_error` | 36.9% | 368,922 |
| `tool_latency` | 36.9% | 369,473 |
| `retry_storm` | 31.6% | 316,003 |
| `low_output` | 31.1% | 311,034 |
| `max_step_hit` | 25.0% | 250,356 |
| `loop` | 24.0% | 240,030 |
| `intervention_frequency` | 12.8% | 127,887 |
| `cost_efficiency` | 5.5% | 54,953 |
| `tool_error_rate` | 2.1% | 20,813 |
| `argument_loop` | 1.1% | 11,378 |
| `per_tool_cost_spike` | 0.9% | 8,984 |
| `token_explosion` | 0.6% | 6,368 |
| `redundant_tool_call` | 0.4% | 3,657 |
| `pattern_loop` | 0.3% | 2,928 |
| `cost_spike` | 0.1% | 758 |
| `step_efficiency` | 0.0% | 0 |

### 3.2 Cross-detector correlation (top co-fires)

The highest-signal pairs co-fire on the same heavily-degraded traces:

| Pair | Co-fires | % of pair's left detector |
|---|---|---|
| `tool_timeout` → `inactivity` | 769,398 | 99.6% |
| `inactivity` → `tool_timeout` | 769,398 | 82.3% |
| `wasted_tool_calls` → `inactivity` | 674,824 | 99.1% |
| `recovery_path` → `inactivity` | 645,730 | 99.1% |
| `tool_latency` → `tool_timeout` | 369,473 | 100.0% |
| `tool_latency` → `inactivity` | 369,412 | 39.5% |

## 4. Interpretation & caveats

- **Purpose is coverage, not precision.** The corpus is intentionally dense with
  failure shapes; a 93.4% `inactivity` fire rate is a property of the generator, not
  a real-world false-positive rate. Real-traffic precision is measured separately in
  [FIELD_TEST_REPORT.md](FIELD_TEST_REPORT.md) (FT-11b/FT-11d LLM pilots) and the
  real-agent reports (`docs/real-agent-integration/`).
- **`step_efficiency` never fired** on this corpus — a generator gap, not necessarily
  a detector defect; noted rather than hidden.
- Rule-based results are deterministic and require no network or model, so this
  baseline is reproducible from the raw corpus alone.

## 5. Raw data

| Artifact | Location (gitignored) |
|---|---|
| Span parquet | `data/traces2/synthetic/*.parquet` |
| Rule-based summary | `data/traces2/validations/synthetic/without-llm/summary.json` |
| Rule-based correlation | `data/traces2/validations/synthetic/without-llm/correlation.json` |
| Progress checkpoints | `data/traces2/validations/synthetic/without-llm/progress*.json` |
