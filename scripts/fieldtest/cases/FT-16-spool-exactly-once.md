# FT-16 — Spool + exactly-once

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** 17 F2,21 B1

## Goal
Spool + exactly-once. See `docs/field-test/v0.1.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-16.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-16.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.1.0/results/<UTC-ts>/cases/FT-16/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
