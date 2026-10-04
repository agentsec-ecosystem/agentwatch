# FT-06b — In-repo corpus soak + validate

**Layer:** analyst · **LLM:** no · **Requires:** docker · **PRD / claim:** 13 NFR-1,30

## Goal
In-repo corpus soak + validate. See `docs/field-test/v0.1.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-06b.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-06b.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.1.0/results/<UTC-ts>/cases/FT-06b/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
