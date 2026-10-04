# CUJ-10 — Cost answer

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** CUJ-10

## Goal
Cost answer. See `docs/field-test/v0.1.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/CUJ-10.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/CUJ-10.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.1.0/results/<UTC-ts>/cases/CUJ-10/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
