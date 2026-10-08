# FT-IDN-3 — Ambient / shared credential hygiene observation

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** IDN-3,DD-07 · **Suite:** s5-identity · **Class:** P/F

## Goal
Ambient / shared credential hygiene observation. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-IDN-3.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-IDN-3.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-IDN-3/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
