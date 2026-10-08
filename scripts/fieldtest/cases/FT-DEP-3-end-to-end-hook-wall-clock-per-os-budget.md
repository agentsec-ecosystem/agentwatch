# FT-DEP-3 — End-to-end hook wall-clock per OS + budget

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** DEP-3 · **Suite:** s1-install · **Class:** P/F|D

## Goal
End-to-end hook wall-clock per OS + budget. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-DEP-3.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-DEP-3.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-DEP-3/artifacts/`.

## Cleanup
Shared stack: reset in place between cases; `recycle` cases get a fresh `down -v`
+ boot. The stack is torn down once, at the end of the run.
