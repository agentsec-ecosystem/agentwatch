# Article Ideas — agentwatch v0.1.0 Field Test

> 7 developer-focused article ideas grounded in evidence from the field test.
> Each is ~2000 words. Target audience: developers building agent observability,
> LLM-backed detection, hash-chained recording, or crash-recovery systems.
> Every article includes real code, real data, and engagement questions.

## Index

- [Idea 1: "Silent None: How a Broken LLM Endpoint Hid for 98 Calls"](idea1.md)
  — A detector that silently returned `None` on every call because the embedding endpoint
  was 404. 98 calls, 98 errors, 0 detections. Nobody noticed for weeks.

- [Idea 2: "The Lock That Starved 1000 Hooks: O(n) Verification Under a Contended Lock"](idea2.md)
  — A background thread's hash chain re-verification held a lock for 242 ms, starving the
  accept loop. 1000 of 10000 hook sends silently disappeared. Raising the backlog was the
  wrong fix.

- [Idea 3: "590 MB for 100 Rows: When File Count Isn't File Size"](idea3.md)
  — A validator OOM'd on 100 rows because one parquet file was 590 MB. `--max-files 5`
  bounded file count, not file size. A single giant file defeated the bound.

- [Idea 4: "The LLM Was Right and the Test Was Wrong"](idea4.md)
  — Three times the test failed and the first instinct was "the detector is broken." Three
  times the LLM was right and the test was wrong. The LLM is a test oracle, not just a
  detector.

- [Idea 5: "226 Scenarios, 43 Detectors, 1 Clean Run: Building a Detector Validation Harness That Doesn't Lie"](idea5.md)
  — How to build a detector test harness with six check layers (fire, severity, type,
  explanation, evidence, LLM-called), precision boundary cases, a scripted DB pool, and a
  clean-trace false-positive check.

- [Idea 6: "The pid File Is the Crash Signal: Why One Missing File Silently Disabled Gap Detection"](idea6.md)
  — A test harness deleted the pid file during cleanup, silently disabling crash-gap
  detection. The daemon didn't error — it just skipped. The gap was invisible.

- [Idea 7: "Zero False Positives on a Clean Trace: The Test You're Not Running"](idea7.md)
  — The most important detector test is the one nobody runs: all detectors against one
  known-normal trace, assert zero fires. 15 lines of code. Catches the #1 killer of
  operator trust.
