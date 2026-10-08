# FT-CMP-2 — Retention profiles + signed default posture

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** CMP-3/4 · **Suite:** s5-identity · **Class:** P/F

## Goal
Retention profiles + signed default posture. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-CMP-2.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-CMP-2.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-CMP-2/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
