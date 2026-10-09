# FT-WIN-1 — Windows support (named-pipe daemon + service)

**Layer:** recorder · **LLM:** no · **Requires:** shell · **PRD / claim:** WIN-1 · **Suite:** s1-install · **Class:** P/F|D

## Goal
Windows support (named-pipe daemon + service). See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-WIN-1.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-WIN-1.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-WIN-1/artifacts/`.

## Cleanup
Shared stack: reset in place between cases; `recycle` cases get a fresh `down -v`
+ boot. The stack is torn down once, at the end of the run.
