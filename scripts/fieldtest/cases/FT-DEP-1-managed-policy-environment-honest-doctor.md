# FT-DEP-1 — Managed-policy environment, honest doctor

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** DEP-1 · **Suite:** s1-install · **Class:** P/F|D

## Goal
Managed-policy environment, honest doctor. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-DEP-1.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-DEP-1.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-DEP-1/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
