# Zero False Positives on a Clean Trace: The Test You're Not Running

> You have 43 anomaly detectors. You test each one: positives fire, negatives don't,
> severity is correct. 226 scenarios, all green. But have you run all 43 detectors against
> a single known-normal trace and checked that none of them fire?

## The Hook

You've been thorough. You wrote positive cases for every detector — known anomalies that
should fire. You wrote negative cases — known-normal inputs that should NOT fire. You
wrote precision boundary cases — n−1 vs n for every numeric threshold. You even verified
severity escalation (warning at n, critical at 2n). 226 scenarios, all green. TPR 100%,
FPR 0%. You're done, right?

Wrong. You're missing the most important test.

In production, all 43 detectors run on the same trace. Not one at a time in isolation —
all of them, together, on every trace the agent produces. A trace that's clean (no loops,
no retries, no cost spike, normal output) should fire zero detectors. If any detector
fires on a clean trace, it's a false positive — and in production, that false positive
becomes noise in the operator's anomaly inbox, an alert that wastes time, a distraction
from real issues.

False positive noise is the #1 reason operators stop trusting anomaly detection systems.
The predecessor's v2 report showed 56,869 anomalies on 100k traces, reduced to 11,294
after noise fixes — an 80% reduction. 45,575 of those original anomalies were false
positives. The operator saw 56,869 alerts, investigated them, found that 80% were noise,
and stopped trusting the system. The fix wasn't better detectors — it was removing the
detectors that fired too eagerly.

The clean-trace test catches false positives before they reach production. It's 15 lines of
code. And almost nobody runs it.

## The Problem with Per-Detector Tests

Per-detector tests check each detector in isolation. Detector X fires on its positive case,
stays silent on its negative case. Good. But in production, all 43 detectors run on the
same trace. A clean trace might accidentally satisfy a detector's trigger conditions:

- `tool_error_rate`: The clean trace has 0 errors out of 3 calls — 0% error rate, below
  the 30% threshold. Good. But what if the clean trace has 1 error out of 3 calls? That's
  33% — above the threshold. The trace is "clean" (the error is a transient network blip,
  not a systemic issue), but the detector fires. Is that a false positive? It depends on
  your definition of "clean."

- `inactivity`: The clean trace has 1-second gaps between spans — well below the 30-second
  threshold. Good. But what if the clean trace has a 35-second gap between spans 2 and 3
  (the agent was waiting for a slow API response)? The trace is "clean" (the agent was
  legitimately waiting), but `inactivity` fires. False positive.

- `loop`: The clean trace has 3 different tools — no repetition. Good. But what if the
  clean trace calls `search_kb` twice in a row (searching for two different things)? That's
  2 consecutive same-tool calls — below the threshold of 5. Good. But what if the threshold
  is 2 instead of 5? Now it fires. The trace is "clean" but the detector fires.

Per-detector tests don't catch these because each detector is tested in isolation. The
clean-trace test catches them because all detectors run on the same trace, just like
production.

## The Clean Trace

Design a trace that is unambiguously normal — no edge cases, no borderline values, nothing
that could accidentally trigger a detector:

```python
def _clean_trace():
    return (
        RunSummary(
            run_id="clean-run",
            agent_name="triage",
            status="success",
            estimated_cost=0.12,       # well below $5 cost_spike threshold
            duration_ms=4500,          # well below 5x baseline for run_duration
            total_tool_calls=3,        # well below 20 for step_efficiency
            total_retries=0,           # well below 5 for retry_storm
            total_interventions=0,     # well below 3 for intervention_frequency
        ),
        [
            span("plan", status="ok", start=0),
            tool("search_kb", status="ok", dur=120, result="kb result", start=1),
            tool("lookup_account", status="ok", dur=80, result="account ok", start=2),
            tool("resolve", status="ok", dur=60, result="done", start=3),
            output(
                "Your password reset request has been completed successfully. "
                "Here is a detailed summary of the steps taken and the final outcome "
                "for your records and reference."
            ),  # 200 chars — well above 50 for low_output
        ],
    )
```

Every value is chosen to be far from every threshold:
- Cost: $0.12 (threshold: $5.00 — 42x margin)
- Tool calls: 3 (threshold: 20 for step_efficiency — 7x margin)
- Retries: 0 (threshold: 5 for retry_storm — infinite margin)
- Interventions: 0 (threshold: 3 — infinite margin)
- Output length: 200 chars (threshold: 50 for low_output — 4x margin)
- Gaps: 1 second (threshold: 30 seconds for inactivity — 30x margin)
- Status: "success" (not "error", not "unknown", not "max_steps_hit")
- Tool names: all different (no repetition for loop detectors)
- Tool results: all different (no redundancy for wasted_tool_calls)
- No file-write tools (no write-storm)
- No network tools (no network-tool)
- No denied/error statuses (no denied-cluster)

This trace is so normal it's boring. That's the point. If any detector fires on this
trace, it's a false positive — the detector is firing on data that is unambiguously normal.

## The Check

Run all 43 detectors against the clean trace. Assert zero fires. 15 lines of code:

```python
async def run_clean():
    from analytics.detectors import create_all_detectors

    summary, spans = _clean_trace()
    fired = []
    for det in create_all_detectors():
        res = await det.detect_async(summary, spans, pool=None)
        if res is not None:
            fired.append({
                "detector": det.anomaly_type,
                "severity": res.severity,
                "explanation": res.explanation,
            })
    return {
        "detectors": len(create_all_detectors()),
        "fired": fired,
        "ok": not fired,  # ← zero false positives
    }
```

Result: `fired=[]`. `ok=True`. Zero false positives across all 43 detectors.

If any detector had fired, the `fired` list would tell us which detector, what severity,
and what explanation — enough to diagnose the false positive and fix it.

## What It Catches

The clean-trace check catches five classes of bugs that per-detector tests miss:

1. **Thresholds set too low.** A detector that fires on 3 tool calls when the threshold
   should be 20. Per-detector tests check the threshold in isolation, but the clean trace
   catches misconfigured thresholds that fire on normal data.

2. **Buggy logic.** A detector that fires when `status == "success"` because of a logic
   inversion (`if status != "error"` instead of `if status == "error"`). Per-detector
   tests might not test the "success" case for that detector.

3. **Misparse attributes.** A detector that treats a normal attribute as an anomaly signal.
   For example, a detector that reads `gen_ai.tool.name` and fires when it's "resolve"
   because "resolve" matches a denylist pattern. Per-detector tests use specific tool names
   that might not trigger the denylist.

4. **Cross-detector interactions.** Detector X's output triggers detector Y. For example,
   `anomaly_cluster` checks how many distinct anomaly types fired on a trace. If 3
   detectors fire falsely, `anomaly_cluster` fires too — a false positive cascade. Per-
   detector tests can't catch this because they run one detector at a time.

5. **State leakage.** A previous scenario's state (e.g., `EmbeddingDriftDetector`'s
   baseline texts) contaminates the clean trace. The detector fires because it compares
   the clean trace to a baseline from a previous scenario, not because the clean trace is
   anomalous. Per-detector tests don't catch this because they don't run all detectors
   together after all scenarios.

## The Predecessor's Experience

The `agent-exec-trace` v2 report is a case study in false positive noise:

| Detector | Before fixes | After fixes | Reduction |
|---|---|---|---|
| `premature_completion` | 35,930 | 0 | Removed (fired on any error status) |
| `argument_loop` | 5,768 | 0 | Removed (missing args collapsed to empty) |
| `redundant_tool_call` | 509 | 0 | Removed (same args collapse) |
| `pattern_loop` | 2,012 | 67 | Deduped from loop |
| `step_efficiency` | 1,797 | 184 | Deduped from loop |
| `wasted_tool_calls` | 1,451 | 2 | Multi-tool gate added |
| **Total** | **56,869** | **11,294** | **-80%** |

45,575 false positives. 80% of all anomalies were noise. The operator saw 56,869 alerts and
stopped trusting the system. The fixes were not new detectors — they were removing or
tightening existing detectors that fired too eagerly.

A clean-trace test would have caught `premature_completion` (fired on any error status,
including normal errors) and `argument_loop` (fired when args were missing, which is normal
for some tool types) before they reached production. 15 lines of code vs. 45,575 false
positives.

## Key Takeaways

1. **The clean-trace false-positive check is the most important detector test you're not
   running.** It's 15 lines of code and catches the most impactful class of bugs — false
   positives that destroy operator trust.
2. **Per-detector tests check logic. The clean-trace test checks integration.** Both are
   necessary. Neither is sufficient alone.
3. **False positive noise is the #1 killer of operator trust.** 80% of anomalies were noise
   in the predecessor. The operator stopped trusting the system. The fix was removing
   detectors, not adding them.
4. **The clean trace must be unambiguously normal.** No edge cases, no borderline values.
   Every value should be far from every threshold. If a detector fires, there's no
   ambiguity — it's a false positive.
5. **Run all detectors, not just the one you're testing.** In production, they all run
   together. Cross-detector interactions and state leakage only appear when all detectors
   run on the same trace.
6. **The `fired` list tells you exactly what to fix.** Detector name, severity, explanation
   — enough to diagnose and fix the false positive without further investigation.

## Questions for You

- Do you run all your detectors against a single known-normal trace? If not, why not?
- How many false positives does your system produce per 1,000 clean traces? Have you
  measured it?
- What would a "clean trace" look like in your domain? What values are unambiguously
  normal for every detector?
- Could any of your detectors fire on normal data by accident? How would you know?
- Have you ever had an operator stop trusting your anomaly system because of noise? How
  did you fix it?
- If you could only run one detector test, which would it be: a positive case, a negative
  case, a precision boundary, or a clean-trace false-positive check? (Hint: the last one.)

---

*This article is grounded in evidence from the agentwatch v0.1.0 field test. The clean-trace
check, detector results, and the predecessor's noise data are in
`services/analytics/src/analytics/scenario_validation.py` and
`field-test/v0.1.0/results/ft15/cases/FT-15/artifacts/detector-results.json`. The
predecessor's noise data is from `agent-exec-trace/docs/field-test/field-test-report-v2.md`.*
