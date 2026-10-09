# FT-TRACE-2 — Cross-host clock skew ordering

**Layer:** recorder · **LLM:** no · **Requires:** docker,fleet · **PRD / claim:** TRACE-2,F9 · **Suite:** s2-interop · **Class:** P/F

## Goal
Cross-host clock skew ordering. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-TRACE-2.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-TRACE-2.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-TRACE-2/artifacts/`.

## Cleanup
Shared stack: reset in place between cases; `recycle` cases get a fresh `down -v`
+ boot. The stack is torn down once, at the end of the run.
