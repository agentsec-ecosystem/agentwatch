# FT-TRACE-1 — One causal chain across 3 hosts × 3 harnesses

**Layer:** recorder · **LLM:** no · **Requires:** docker,fleet · **PRD / claim:** TRACE-1/2 · **Suite:** s2-interop · **Class:** P/F

## Goal
One causal chain across 3 hosts × 3 harnesses. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-TRACE-1.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-TRACE-1.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-TRACE-1/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
