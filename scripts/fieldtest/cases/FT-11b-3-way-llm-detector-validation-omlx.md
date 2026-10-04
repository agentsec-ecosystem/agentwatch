# FT-11b — 3-way LLM detector validation (OMLX)

**Layer:** analyst · **LLM:** yes · **Requires:** docker,omlx · **PRD / claim:** 29,30

## Goal
3-way LLM detector validation (OMLX). See `docs/field-test/v0.1.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-11b.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-11b.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.1.0/results/<UTC-ts>/cases/FT-11b/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
