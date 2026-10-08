# FT-DET-3 — LLM detectors in the same harness

**Layer:** recorder · **LLM:** yes · **Requires:** docker,omlx · **PRD / claim:** DET-4 · **Suite:** s4-detectors · **Class:** P/F

## Goal
LLM detectors in the same harness. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-DET-3.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-DET-3.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-DET-3/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
