# FT-API-1 — OpenAPI publication + typed client drift

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** API-1 · **Suite:** s7-platform · **Class:** P/F

## Goal
OpenAPI publication + typed client drift. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-API-1.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-API-1.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-API-1/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
