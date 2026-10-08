# FT-AAT-1 — AAT export → third-party consumer round-trip

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** AAT-1/2/4 · **Suite:** s2-interop · **Class:** P/F

## Goal
AAT export → third-party consumer round-trip. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-AAT-1.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-AAT-1.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-AAT-1/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
