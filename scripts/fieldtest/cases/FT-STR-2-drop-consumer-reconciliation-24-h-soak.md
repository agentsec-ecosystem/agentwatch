# FT-STR-2 — Drop-consumer reconciliation + 24 h soak

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** STR-2/3 · **Suite:** s3-harness · **Class:** P/F

## Goal
Drop-consumer reconciliation + 24 h soak. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-STR-2.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-STR-2.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-STR-2/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
