# FT-IDN-1 — Attribution end-to-end in one command

**Layer:** recorder · **LLM:** no · **Requires:** docker,fleet · **PRD / claim:** IDN-1..4 · **Suite:** s5-identity · **Class:** P/F

## Goal
Attribution end-to-end in one command. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-IDN-1.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-IDN-1.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-IDN-1/artifacts/`.

## Cleanup
Shared stack: reset in place between cases; `recycle` cases get a fresh `down -v`
+ boot. The stack is torn down once, at the end of the run.
