# The LLM Was Right and the Test Was Wrong

> You write a test: "the agent searched the KB instead of resetting the password — that's
> goal drift, fire the detector." The LLM says `{"diverged": false}`. Your test fails. You
> file a bug. But the LLM was right — searching the KB IS a step toward resetting a password.
> The test was wrong.

## The Hook

Here's a situation every developer dreads: your test fails, and you can't tell if the bug is
in the code or in the test. Usually, the code is wrong. That's the default assumption. Test
fails → debug the code → fix the code → test passes. That's the loop.

But what happens when the code is an LLM-backed detector, and the test is a hand-constructed
scenario, and the LLM has broader world knowledge than you do? What happens when the LLM
correctly judges that your "anomalous" scenario isn't actually anomalous?

This happened to us three times in the agentwatch field test. Three tests failed. Three
times the first instinct was "the detector is broken." Three times the real problem was that
the test was wrong — and the LLM was right.

## Case 1: Goal Drift That Wasn't

The scenario: `GoalDriftDetector` should fire when the agent pursues a different objective
than intended. We constructed a trace:

- **Plan:** "Reset the user's password and send a confirmation email."
- **Action:** `search_kb` (search the knowledge base)
- **Expected:** `diverged=true` (the agent drifted from the goal)

The LLM responded:

```json
{
  "diverged": false,
  "similarity": 0.95,
  "note": "Searching the knowledge base is a necessary step to retrieve the user's current
  credentials before resetting the password."
}
```

`diverged=false`. The test failed. The first reaction: "the detector isn't working. The LLM
isn't understanding the scenario. Maybe the prompt is bad."

But read the LLM's note. It's... correct. Searching the knowledge base IS a necessary step
toward resetting a password. You'd look up the password reset procedure before resetting
the password. The agent is following the plan, not drifting from it.

The test author's mental model was: "search_kb has nothing to do with password reset."
The LLM's mental model was: "search_kb is a prerequisite for password reset." The LLM was
right. The test author was wrong.

**The fix:** Switch the drifted action to `delete_database` — unambiguously unrelated to
password reset. The LLM correctly responded:

```json
{
  "diverged": true,
  "similarity": 0.0,
  "note": "The action deletes the database instead of resetting the password and sending an
  email, completely failing the original objective."
}
```

Test passes. The LLM was right both times — first when it correctly said "not drifted," and
again when it correctly said "drifted" after we fixed the scenario.

## Case 2: The Floating-Point Boundary

The scenario: `PerToolCostSpikeDetector` should fire when one tool dominates cost. The
threshold is a dominance ratio of 2.0. We constructed a precision boundary case:

- 6 calls to tool "a" + 3 calls to tool "b" = 9 total
- share = 6/9 = 0.667 > 0.5 ✓
- count = 6 ≥ 3 ✓
- dominance = 0.667 / 0.333 = 2.0 ≥ 2.0 ✓ (should fire)

The detector didn't fire. The test failed. First reaction: "the threshold comparison is
broken. `>=` should fire at exactly 2.0."

But look closer:

```python
share = 6 / 9        # = 0.6666666666666666
other = 1.0 - share   # = 0.33333333333333337
dominance = share / max(other, 0.0001)
# = 0.6666666666666666 / 0.33333333333333337
# = 1.9999999999999998
# 1.9999999999999998 >= 2.0 → False
```

**Floating-point.** `6/9 ÷ 3/9` is not `2.0` in IEEE 754. It's `1.9999999999999998`. The
detector correctly did not fire because `1.9999... < 2.0`. The test was wrong — it assumed
exact arithmetic where there was floating-point arithmetic.

**The fix:** Use 7+2 spans instead of 6+3. `7/9 = 0.7778`, `2/9 = 0.2222`,
`0.7778/0.2222 = 3.5 ≥ 2.0` — comfortably above the threshold, no floating-point ambiguity.

This is a gotcha that every developer hits eventually. You write a test at the exact
boundary (`n == threshold`), and floating-point says `n = threshold - epsilon`. The code is
correct. The test is wrong. Always test at `n+1`, not at `n`, for numeric thresholds.

## Case 3: The Documented Blind Spot

The scenario: `RetryStormDetector` should NOT fire when 6 retries happen but 5 succeed
(transient errors that eventually resolve). The test expected "must NOT fire."

The detector fired. The test failed. First reaction: "the detector is over-firing. It
should suppress transient retries."

But the predecessor's `anomaly-validation-matrix.md` explicitly documents this as a known
blind spot:

> **Known blind spots for v0.1.0:**
> - **Transient error vs systemic:** No distinction between retries that succeed vs those
>   that keep failing. A run with 5 retries that all succeed still fires.

The detector fires on `total_retries >= 5` — that's the entire logic. It doesn't check
success rate. It doesn't suppress transients. This is by design, not a bug. The test
contradicted the documented behavior.

**The fix:** Change the test expectation from "must NOT fire" to "must fire (known blind
spot)." The detector is behaving as designed. The test was wrong to expect suppression
that was never implemented.

## The Pattern

All three cases share a pattern: **the test author's expectation didn't match reality.**

In Case 1, the test author's mental model of "goal drift" was narrower than the LLM's. The
LLM correctly identified that `search_kb` is a valid step toward `reset_password`. The test
author didn't think of that.

In Case 2, the test author assumed exact arithmetic where there was floating-point. The
code was correct; the math was wrong.

In Case 3, the test author expected behavior that was explicitly documented as not
implemented. The code was working as designed; the test didn't read the docs.

In all three cases, the first instinct was "the code is wrong." In all three cases, the code
was right. The test was wrong.

## Why This Matters for LLM-Backed Tests

When you test a deterministic function, the test is the oracle. `add(2, 3) == 5` — the test
knows the answer. The code is the suspect.

When you test an LLM-backed detector, the roles can reverse. The LLM has world knowledge
that the test author doesn't. The LLM can judge whether `search_kb` is related to
`reset_password` — and its judgment may be better than the test author's. The LLM is the
oracle. The test is the suspect.

This doesn't mean LLMs are always right. They hallucinate, they misjudge, they parse prompts
wrong. But when an LLM-backed test fails, the debugging process should be:

1. **Read the LLM's response.** What did it actually say? What was its reasoning?
2. **Check if the LLM's judgment is correct.** Is `search_kb` actually a valid step toward
   `reset_password`? (Yes, it is.)
3. **If the LLM is correct, fix the test.** The scenario wasn't what you thought it was.
4. **If the LLM is wrong, fix the prompt or the detector.** The LLM misunderstood the
   scenario.
5. **Check the docs.** Is the behavior you're expecting actually implemented? Or is it a
   documented blind spot?

Most developers skip steps 1–3. They see a test failure, assume the code is wrong, and start
debugging the detector. But with LLM-backed tests, the test itself might be the bug.

## Key Takeaways

1. **When an LLM-backed test fails, read the LLM's response first.** The LLM may be right
   and the test may be wrong. The LLM has world knowledge you don't.
2. **Test at n+1 for numeric thresholds, not at n.** Floating-point arithmetic means
   `6/9 ÷ 3/9 = 1.9999...`, not `2.0`. Test at 7+2, not 6+3.
3. **Read the documented blind spots before writing tests.** If the docs say "this detector
   doesn't suppress transient retries," don't write a test that expects suppression.
4. **The LLM is a test oracle, not just a detector.** It can tell you whether your scenario
   is actually what you think it is. Listen to it.
5. **The debugging loop for LLM-backed tests is different.** Test fails → read LLM response
   → check if LLM is correct → fix test or fix detector. Don't skip to "fix detector."

## Questions for You

- Have you ever written a test that was wrong and the code was right? How did you find out?
- When your LLM-backed tests fail, do you read the LLM's response? Or do you immediately
  start debugging the code?
- Do you test numeric thresholds at the exact boundary (`n == threshold`) or at `n+1`?
  Have you been bitten by floating-point?
- Do your tests account for documented blind spots? Or do they expect behavior that was
  never implemented?
- Could your LLM-backed detector be right and your test be wrong right now? How would you
  know?
- When the LLM says "this isn't anomalous," do you trust it? Or do you override it?

---

*This article is grounded in evidence from the agentwatch v0.1.0 field test. The actual LLM
responses, test results, and code are in
`field-test/v0.1.0/results/ft15/cases/FT-15/artifacts/llm-scenario-io.jsonl` and
`services/analytics/src/analytics/scenario_validation.py`.*
