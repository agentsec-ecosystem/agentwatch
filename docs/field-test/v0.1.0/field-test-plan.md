# agentwatch v0.1.0 — Field Test Plan

**BLUF:** Prove the recording path on a real machine with real Claude Code usage, and prove the security
baseline.

Status: **draft**.

## Scenarios (proposed)

1. Fresh-machine install → first recorded tool call ≤15 min, zero agent-side code changes.
2. Full session replay reconstructs the action timeline.
3. Export loads into ≥2 standard OTel backends unmodified.
4. Attack pack: zero secrets in stored records.
5. Tamper: edit hook config → detected, fail-closed.
6. Long session: recording stays on, no gaps, bounded storage growth.

## Report

Results go to `field-test/v0.1.0/FIELD_TEST_REPORT.md` at gate time.
