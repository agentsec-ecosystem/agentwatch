# FT-DET-5 — Detector telemetry (SIEM-feedable, content-free)

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** DET-5 · **Suite:** s4-detectors · **Class:** P/F

## Goal
Detector telemetry (SIEM-feedable, content-free). See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-DET-5.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-DET-5.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-DET-5/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
