# 226 Scenarios, 43 Detectors, 1 Clean Run: Building a Detector Validation Harness That Doesn't Lie

> You have 43 anomaly detectors. Some are rule-based. Some call an LLM. Some need a
> database. How do you test all of them with the same harness, ensure none silently skip,
> and prove zero false positives on a clean trace?

## The Hook

Here's the problem: you've built 43 anomaly detectors for an agent observability platform.
35 are rule-based (check a threshold, fire or don't). 3 are Claude Code hook detectors
(check tool patterns in trace spans). 5 are LLM-backed (ask an LLM to judge whether the
agent's behavior is anomalous). 1 uses embeddings (compare output vectors to a baseline).

Each detector has positive cases (should fire) and negative cases (should NOT fire). Some
have severity escalation (warning at n, critical at 2n). Some need a database (baseline
cohorts, run counts, anomaly history). Some need an LLM server (OMLX running on the host).
And all of them run on every trace in production — so a false positive on a clean trace
becomes noise in the operator's anomaly inbox.

How do you test all 43 detectors with one harness? How do you ensure none of them silently
skip (return `None` because the API failed, not because there's no anomaly)? How do you
prove that a known-normal trace fires zero detectors? And how do you do it fast enough to
run in CI?

We built a harness that does all of this in 226 scenarios, runs in 4 milliseconds for the
rule-based cases, makes 12 real LLM calls for the LLM cases, uses a scripted database pool
for the baseline cases, and asserts that a clean trace fires nothing. Here's how.

## The Architecture

### Scenario Model

Every test case is a `Scenario` — a dataclass that knows how to build a trace and what to
expect:

```python
@dataclass
class Scenario:
    id: str                          # "L1", "HAL1", "P-loop-5", etc.
    detector: type                   # LoopDetector, HallucinationDetector, etc.
    expect_fire: bool                # True = positive, False = negative
    build: Callable                   # returns (RunSummary, list[SpanNode])
    severity: str | None             # "warning", "critical", "info", or None
    pool: dict[str, Any] | None      # scripted DB values for baseline detectors
    detector_kwargs: dict[str, Any]  # constructor args (e.g., allowlist)
    phase: str                       # "matrix", "precision", "llm", or "clean"
```

The `build` function returns a `RunSummary` (aggregated metrics: cost, retries, duration,
status) and a list of `SpanNode` (the trace tree: tool calls, planning steps, outputs).
These are hand-constructed — not random, not from a corpus. Each trace has known properties
that should trigger or not trigger a specific detector.

Example — a LoopDetector positive case:

```python
add("L1", LoopDetector, True,
    lambda: (summ(total_tool_calls=6), [tool("search_kb") for _ in range(6)]),
    severity="warning")
```

6 consecutive `search_kb` calls. Threshold is 5. Should fire with `warning` severity.
Simple, deterministic, no ambiguity.

### ScriptedPool: Replacing the Database

Six detectors need a database (baseline cohorts, run counts, anomaly history). In
production, they query Postgres via an asyncpg pool. In the test harness, we use a
`ScriptedPool` — a fake pool whose `fetchrow` and `fetch` return preset values:

```python
class ScriptedPool:
    """A minimal asyncpg-like pool whose queries return preset values."""

    def __init__(self, values: dict[str, Any] | None = None):
        self.conn = _Conn(values or {})

    def acquire(self):
        return _Acq(self.conn)

class _Conn:
    async def fetchrow(self, sql, *args):
        s = sql.lower()
        if "avg(estimated_cost)" in s:
            return {"avg_cost": self.v.get("avg_cost")}
        if "avg(duration_ms)" in s:
            return {"avg_dur": self.v.get("avg_dur")}
        if "count(*)" in s and "run_summaries" in s:
            return {"cnt": self.v.get("cnt", 0),
                    "first_run": self.v.get("first_run")}
        if "from anomalies" in s:
            return [{"anomaly_type": t} for t in self.v.get("anomaly_types", [])]
        return None
```

The key insight: `_has_valid_pool()` in the detector base class checks
`hasattr(pool, "acquire") and not hasattr(pool, "return_value")`. The `ScriptedPool` has
`acquire` but no `return_value` (that's a Mock detection heuristic). So the detectors accept
it as a real pool and run their async queries against it.

Example — a CostVsBaselineDetector positive case:

```python
add("CV1", CostVsBaselineDetector, True,
    lambda: (summ(agent_version="v1", estimated_cost=6.0), []),
    severity="warning",
    pool={"avg_cost": 2.5})  # baseline is $2.50, run costs $6.00 → 2.4x → fires
```

The scripted pool returns `{"avg_cost": 2.5}` when the detector queries
`SELECT AVG(estimated_cost) FROM run_summaries WHERE agent_name = $1 AND agent_version = $2`.
No real database. No asyncpg. No Docker. Just a dict.

### LLM Scenarios: Real Calls, Not Mocks

The 12 LLM detector scenarios make real OMLX calls. This is critical — mocks hide the
silent-None problem (see idea1). A mock LLM client always returns a valid response. A real
LLM client might return `None` if the server is down, the model is wrong, or the response
isn't valid JSON. Only real calls expose these failures.

The LLM client is constructed from environment variables at runtime (inside the Docker
container):

```python
def _llm_client():
    from analytics.llm_client import LLMClient
    return LLMClient()  # reads ANALYTICS_LLM_* env vars
```

Each scenario snapshots `client._stats` before and after to measure LLM calls for that
specific scenario:

```python
stats_before = dict(client._stats)
anomaly = await det.detect_async(summary, spans, pool=None)
stats_after = dict(client._stats)
llm_calls = stats_after["chat_calls"] - stats_before["chat_calls"]
embed_calls = stats_after["embed_calls"] - stats_before["embed_calls"]
```

This per-scenario call counting is what makes the `llm_called_ok` deep check possible.

## The Deep Checks (The Part Most Harnesses Miss)

Most detector test suites check one thing: did the detector fire? That's necessary but not
sufficient. Our harness checks six things:

| Check | What it verifies | Why it matters |
|---|---|---|
| `fire_ok` | `fired == expect_fire` | The detector fired (or didn't) as expected |
| `severity_ok` | `actual_severity == expected_severity` | The severity is correct (warning vs critical) |
| `type_ok` | `anomaly.anomaly_type == detector.anomaly_type` | The anomaly is from the right detector |
| `explanation_ok` | `anomaly.explanation` is non-empty | The anomaly has a human-readable explanation |
| `evidence_ok` | `anomaly.evidence` is a dict | The anomaly has structured evidence |
| `llm_called_ok` | `llm_calls + embed_calls > 0` | The LLM was actually called (not a silent skip) |

The `llm_called_ok` check is the one that caught the `EmbeddingDriftDetector` silent failure
(see idea1). Without it, the test would have passed — the detector returned `None` (correct
for a negative case), but the LLM was never called (the embed endpoint returned 404). The
deep check turned a hidden skip into a visible failure.

There's also `verdict_ok` — for LLM scenarios, parse the LLM's JSON response and verify the
verdict matches the expected outcome. For a positive case, the LLM should say
`{"hallucination": true}`. For a negative case, `{"hallucination": false}`. This catches
cases where the detector fires for the wrong reason (e.g., the LLM said "no anomaly" but the
detector fired anyway due to a logic bug).

## The Precision Boundary Cases

For every numeric threshold, we test at n−1 (must NOT fire) and at n (must fire). This
catches off-by-one errors and floating-point boundary issues.

Example — LoopDetector (threshold=5):

```python
prec("P-loop-4", LoopDetector, False, _tools(["search_kb"] * 4))  # 4 < 5 → no fire
prec("P-loop-5", LoopDetector, True, _tools(["search_kb"] * 5), severity="warning")  # 5 ≥ 5 → fire
```

Example — CostSpikeDetector (absolute threshold=$5.00, strict `>`):

```python
prec("P-cost-500", CostSpikeDetector, False, lambda: (summ(estimated_cost=5.0), []))  # 5.0 > 5.0 → False
prec("P-cost-501", CostSpikeDetector, True, lambda: (summ(estimated_cost=5.01), []), severity="warning")  # 5.01 > 5.0 → True
```

The `PerToolCostSpikeDetector` floating-point bug (6/9 ÷ 3/9 = 1.9999... < 2.0, see idea4)
was caught by this approach. The precision cases force you to test at the exact boundary,
where floating-point and off-by-one bugs live.

48 precision boundary cases across 24 numeric thresholds. All pass.

## The Clean-Run False-Positive Check

This is the most important test in the harness, and it's the one most teams don't run.

Run all 43 detectors against a single known-normal trace. Assert zero fires. If any
detector fires, it's a false positive.

```python
def _clean_trace():
    return (
        summ(status="success", estimated_cost=0.12, duration_ms=4500,
             total_tool_calls=3, total_retries=0, total_interventions=0),
        [
            span("plan", status="ok", start=0),
            tool("search_kb", status="ok", dur=120, result="kb result", start=1),
            tool("lookup_account", status="ok", dur=80, result="account ok", start=2),
            tool("resolve", status="ok", dur=60, result="done", start=3),
            output("Your password reset request has been completed successfully. "
                   "Here is a detailed summary of the steps taken and the final outcome "
                   "for your records and reference."),
        ],
    )

async def run_clean():
    summary, spans = _clean_trace()
    fired = []
    for det in create_all_detectors():
        res = await det.detect_async(summary, spans, pool=None)
        if res is not None:
            fired.append({"detector": det.anomaly_type, "severity": res.severity})
    return {"detectors": len(create_all_detectors()), "fired": fired, "ok": not fired}
```

The clean trace is unambiguously normal: 3 tool calls with 1-second gaps (well below the
30-second inactivity threshold), success status, $0.12 cost (well below the $5 cost spike
threshold), 0 retries, 0 interventions, a 200-character output (well above the 50-character
low-output threshold). No loops, no errors, no timeouts, no file writes, no network tools.

Result: `fired=[]`. Zero false positives across all 43 detectors. The system doesn't fire
on clean data.

## The Results

```
detector-scenarios [full-enumeration]: 226/226 ok; 0 failed

  matrix:     166 cases (154 ported + 12 Claude Code)  — 0 failed
  precision:   48 cases (n−1 vs n for 24 thresholds)   — 0 failed
  llm:         12 cases (6 LLM detectors, real OMLX)   — 0 failed
  clean:        1 case  (43 detectors, 0 false positives) — 0 failed

Per-detector TPR: 100.0%  FPR: 0.0%  (all 43 detectors)
```

The rule-based cases run in 4 milliseconds. The LLM cases take ~1 second each (12 seconds
total for OMLX calls). The clean run takes <1 millisecond. Total harness runtime: ~12
seconds, dominated by LLM latency.

All LLM request/response I/O is captured in `llm-scenario-io.jsonl` — 13 records with
prompts, system messages, raw responses, model names, and timing. This is the audit trail:
you can go back and read exactly what the LLM said for each scenario.

## Key Takeaways

1. **Six check layers, not one.** Fire, severity, type, explanation, evidence, LLM-called.
   Most harnesses check only the first. The sixth (`llm_called_ok`) is the one that catches
   silent failures.
2. **Mocks hide silent failures.** Use real LLM calls for LLM detector tests. A mock client
   always returns a valid response. A real client might fail, and that failure is the bug
   you need to catch.
3. **A scripted pool replaces a test database.** No asyncpg, no Docker, no Postgres. Just a
   dict that returns preset values. 1000x faster, same coverage.
4. **Precision boundary cases catch off-by-one and floating-point bugs.** Test at n−1 and
   at n for every numeric threshold. This is where the bugs live.
5. **The clean-run false-positive check is the most important test you're not running.**
   All detectors against one known-normal trace, assert zero fires. 15 lines of code.
   Catches the most impactful class of bugs.
6. **226 scenarios in 4 ms.** The harness is fast because the scenarios are in-process —
   no Docker, no database, no network for the rule-based cases. The only slow part is the
   12 LLM scenarios (1 s each for OMLX calls).

## Questions for You

- Does your detector test suite check that the LLM was actually called? Or does it just
  check the output?
- Do you test at n−1 as well as at n for numeric thresholds? Have you been bitten by
  floating-point at the exact boundary?
- Do you run a clean-trace false-positive check? All detectors against one known-normal
  input, assert zero fires?
- Are you using mocks for your LLM detector tests? What would happen if the LLM endpoint
  went down? Would your tests catch it?
- How long does your detector test suite take to run? Could it run in CI without slowing
  down the pipeline?
- Could any of your detectors be silently returning `None` right now? How would you know?

---

*This article is grounded in evidence from the agentwatch v0.1.0 field test. The harness
code, results, and LLM I/O are in
`services/analytics/src/analytics/scenario_validation.py` and
`field-test/v0.1.0/results/ft15/cases/FT-15/artifacts/detector-results.json`.*
