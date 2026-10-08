# FT-DET-6 — New-class scenario depth

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** DET-6 · **Suite:** s4-detectors · **Class:** P/F

## Goal
New-class scenario depth. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-DET-6.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-DET-6.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-DET-6/artifacts/`.

## Cleanup
Shared stack: reset in place between cases; `recycle` cases get a fresh `down -v`
+ boot. The stack is torn down once, at the end of the run.
