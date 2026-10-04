# Silent None: How a Broken LLM Endpoint Hid for 98 Calls

> Your LLM detector returns `None`. You mark the test as pass. But the LLM was never called.

## The Hook

You wrote a detector that calls an LLM embedding API. It returns `None` — no anomaly detected.
Your test suite marks it as pass. Green checkmark. Move on.

But the LLM was never called. The endpoint returned 404 on every single call. Your detector
silently swallowed the error, returned `None`, and your test suite said everything was fine.

98 calls. 98 errors. 0 detections. And nobody noticed for weeks.

This is not a hypothetical. This happened in agentwatch's field test. And it's probably
happening in your codebase right now.

## The Discovery

We were running FT-11d — a 100-trace synthetic corpus pilot through our LLM-augmented
detectors. The summary looked great:

```
traces_processed: 100
chat_calls: 363
embed_calls: 98
errors: 98
total_tokens: 52,578
json_parse_success: 363
json_parse_fail: 0
```

363 chat calls, 100% JSON parse success, 52,578 tokens. The LLM was working. The detectors
were firing. `hallucination: 98`, `confusion_pattern: 2`, `quality_degradation: 1`. All
looked correct.

But look at the embed line: **98 calls, 98 errors**. Every single embedding call failed.
100% failure rate. And nobody noticed because the corpus run counts fires, not non-fires.
A detector that never fires simply doesn't appear in the anomaly counts. `output_drift` was
not "0" — it was **absent**. And absent is not zero. Absent means "this detector never ran."

The error was sitting in the logs the entire time:

```
LLM embed call failed: Error code: 404 - {'error': {'message': "Model 'all-MiniLM-L6-v2'
not found. Available models: Llama-3.2-3B-Instruct-4bit, Qwen3-4B-Instruct-2507-4bit,
Qwen3-8B-4bit, Qwen3.5-4B-4bit, Qwen3.5-9B-MLX-4bit, mlx-community--Qwen3.5-4B-4bit",
'type': 'not_found_error'}}}
```

Logged 98 times. Nobody read those logs. Why would they? The test passed.

## The Mechanism

Here's the code path that made this invisible:

```python
# llm_client.py
async def embed(self, text: str) -> list[float] | None:
    client = self._client_instance()
    if client is None:
        return None
    try:
        resp = await client.embeddings.create(
            model=self.embed_model,
            input=text,
        )
        vector = list(resp.data[0].embedding)
        return vector
    except Exception as exc:
        self._record_error(start)
        logger.warning("LLM embed call failed: %s", exc)
        return None  # ← silent failure
```

The `embed()` method catches every exception, logs a warning, and returns `None`. This is
intentional — the client is designed to be resilient. A failed embedding shouldn't crash
the detector pipeline.

Now the detector:

```python
# llm.py — EmbeddingDriftDetector
async def detect_drift(self, output_text, baseline_key):
    current_vector = await self._client.embed(output_text)
    if current_vector is None:
        return None  # ← "no vector available, no anomaly"
    # ... compare to baseline ...
```

When `embed()` returns `None`, the detector treats it as "no vector available" and returns
`None` (no anomaly). This is also intentional — if you can't get a vector, you can't compare
vectors, so you can't detect drift.

And the test:

```python
# scenario_validation.py
anomaly = await det.detect_async(summary, spans, pool=None)
fired = anomaly is not None  # ← None means "didn't fire"
fire_ok = fired == sc.expect_fire  # ← False == False → pass
```

The test sees `fired=False`, the expected outcome for a negative case is `False`, so
`fire_ok=True`. Pass. Green checkmark.

Here's the equivalence that makes this invisible:

```
None from "I checked and found no anomaly"
    == None from "I couldn't check because the API failed"
    == None from "I never called the API at all"
```

All three produce `fired=False`. All three look like a pass. Without call telemetry, they
are indistinguishable.

## The Fix

Two layers.

**Layer 1: Make the detector actually work.** When `embed()` returns `None`, fall back to
asking the LLM to rate similarity via chat:

```python
async def detect_drift(self, output_text, baseline_key):
    current_vector = await self._client.embed(output_text)
    baseline = self._baselines.get(baseline_key)

    if current_vector is not None and baseline is not None:
        sim = cosine_similarity(current_vector, baseline)
    elif current_vector is not None and baseline is None:
        self._baselines[baseline_key] = current_vector
        return None  # first call sets baseline
    else:
        # Embedding unavailable — fall back to chat-based similarity
        baseline_text = self._baseline_texts.get(baseline_key)
        if baseline_text is None:
            self._baseline_texts[baseline_key] = output_text
            return None  # first call sets baseline text
        sim = await self._chat_similarity(baseline_text, output_text)
        if sim is None:
            return None

    distance = 1.0 - sim
    if distance >= self._threshold:
        return Anomaly(
            anomaly_type=self.anomaly_type,
            severity="warning" if distance < 0.5 else "critical",
            explanation=f"Output drift detected: cosine distance {distance:.2f}...",
            evidence={"cosine_distance": distance, "method": "chat-fallback"},
        )
    return None
```

The chat fallback asks: "Compare two texts and rate their semantic similarity on a scale of
0.0 to 1.0. RETURN ONLY JSON: `{"similarity": <float>}`". The LLM responds, and we use
`1.0 - similarity` as the distance. Less precise than vector cosine, but correct fire/no-fire
verdicts.

**Layer 2: Make the test verify the LLM was called.** This is the deep check that most test
suites miss:

```python
# Snapshot stats before the scenario
stats_before = dict(client._stats)
responses_before = len(client._responses)

# Run the detector
anomaly = await det.detect_async(summary, spans, pool=None)

# Measure LLM calls for THIS scenario
stats_after = dict(client._stats)
llm_calls = stats_after["chat_calls"] - stats_before["chat_calls"]
embed_calls = stats_after["embed_calls"] - stats_before["embed_calls"]

# Deep check: the LLM must have been called
total_llm = llm_calls + embed_calls
llm_called_ok = total_llm > 0

# A negative case where the LLM was never called is NOT a pass
ok = fire_ok and sev_ok and type_ok and expl_ok and evid_ok and llm_called_ok
```

If `llm_called_ok` is `False`, the scenario fails — even if the detector returned the
"correct" answer. A silent `None` with zero LLM calls is a hidden skip, not a pass.

## The Evidence

After the fix, the EmbeddingDriftDetector scenarios pass with real LLM calls:

```
✅ ED1  output_drift  fire=True  sev=critical  llm_calls=1  llm_errors=2  verdict_ok=True
✅ ED2  output_drift  fire=False sev=None       llm_calls=1  llm_errors=2  verdict_ok=True
```

Both scenarios have `llm_calls=1` (the chat fallback) and `llm_errors=2` (the two failed
embed calls). The detector works. The test proves it was called. The LLM's actual responses:

ED1 (positive — completely different texts):
```json
{"similarity": 0.1}
```
Distance = 0.9 ≥ 0.3 threshold → fires with `critical` severity (0.9 ≥ 0.5).

ED2 (negative — nearly identical texts):
```json
{"similarity": 0.95}
```
Distance = 0.05 < 0.3 threshold → stays silent. Correct.

## The Broader Pattern

This is not just about embedding endpoints. Any external dependency that returns a sentinel
value on failure is vulnerable:

| Dependency | Sentinel value | Looks like |
|---|---|---|
| LLM `embed()` | `None` | "no anomaly" |
| LLM `chat()` | `None` | "no anomaly" |
| Database `fetchrow()` | `None` | "no baseline" |
| HTTP `GET` | `""` (empty body) | "no data" |
| Cache `get()` | `None` | "not in cache" |
| File `read()` | `""` (empty) | "file is empty" |

In every case, the failure looks like a legitimate "no data" result. The test passes. The
system is broken. Nobody knows.

The fix is always the same: **verify the dependency was exercised, not just check the
output.** Count the calls. Check the response status. Assert the network was reached. A
`None` return is only trustworthy if you can prove the call happened.

## Key Takeaways

1. **Assert the dependency was called, not just the output.** `llm_calls > 0` on every
   negative case. A silent `None` with zero calls is a hidden skip.
2. **A missing anomaly type in your counts is not "zero anomalies" — it's "this detector
   never ran."** Absent ≠ zero. Check for presence, not just count.
3. **Log-level warnings are not alerts.** The embed errors were logged 98 times. Nobody saw
   them because nobody reads logs until something breaks. If it's important, make it an
   assertion, not a log line.
4. **Sentinel values are ambiguous.** `None` means "I checked and found nothing" OR "I
   couldn't check." Without call telemetry, they're indistinguishable. Always instrument
   the call, not just the result.
5. **Chat-based fallback works.** When the primary API (embeddings) is unavailable, a
   chat-based fallback (ask the LLM to rate similarity) produces correct verdicts with the
   same model. The tradeoff is precision, not correctness.

## Questions for You

- Do your LLM-backed tests verify the LLM was actually called? Or do they just check the
  output?
- What other external dependencies in your codebase return sentinel values (`None`, `""`,
  `[]`, `0`) on failure? Could any of them be silently failing right now?
- How would you know if your embedding endpoint went down tomorrow? Would your test suite
  catch it, or would it silently mark everything as pass?
- When was the last time you read your warning logs? Are there errors sitting in there right
  now that nobody has noticed?
- Have you ever shipped a feature that was "working" but actually silently failing? How did
  you find out?

---

*This article is grounded in evidence from the agentwatch v0.1.0 field test. The actual
error logs, LLM responses, and test results are in
`field-test/v0.1.0/results/ft15/cases/FT-15/artifacts/llm-scenario-io.jsonl` and
`field-test/v0.1.0/results/all/cases/FT-11d/artifacts/llm/with-llm/summary.json`.*
