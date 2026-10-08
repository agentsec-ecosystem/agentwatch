# FT-APV-1 — Classifier/bypass/user fidelity

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** APV-1 · **Suite:** s8-apv · **Class:** P/F

## Goal
Classifier/bypass/user fidelity. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-APV-1.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-APV-1.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-APV-1/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
