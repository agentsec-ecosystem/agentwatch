# agentwatch v0.1.0 — Field Test Plan

**BLUF:** Prove the recording path on a real machine with real Claude Code usage, and prove the security
baseline. Each scenario has reproducible steps and a pass/fail.

Status: **draft**.

## Scenarios

1. **Fresh-machine install** — clean OS → `agentwatch init` → first recorded tool call ≤15 min, zero agent-side
   code changes. **Pass:** first record appears within 15 min.
2. **Session replay** — run a session; `agentwatch replay <id>`. **Pass:** timeline matches the raw
   transcript (automated diff).
3. **OTLP export** — enable export to Phoenix and Jaeger. **Pass:** traces load unmodified in both.
4. **Redaction attack pack** — feed secret-bearing arguments. **Pass:** 0 secrets in the store; `secret-detected`
   events emitted.
5. **Tamper** — edit hook config / a store record. **Pass:** fail-closed; gap surfaced; chain break reported.
6. **Long session** — 1k+ tool calls. **Pass:** no gaps; bounded growth (<cap); p99 step latency ≤5 ms.

## Harness

A single **Playwright** harness (delivered in M14 14.1, #141) drives the Docker Compose stack
(`make stack-up` → `make seed-e2e` → the E2E specs) and executes the automatable scenarios. It absorbs
the M8 8.5 harness, which was deferred to M14 because it needs a real environment.

## Report

Results → [`FIELD_TEST_REPORT.md`](FIELD_TEST_REPORT.md) at gate time.
