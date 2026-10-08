# FT-LUI-1 — Clean-machine console ≤60 s, no Docker

**Layer:** analyst · **LLM:** no · **Requires:** python,node · **PRD / claim:** LUI-1 · **Suite:** s11-console · **Class:** P/F

## Goal
Clean-machine console ≤60 s, no Docker. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-LUI-1.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-LUI-1.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-LUI-1/artifacts/`.

## Cleanup
Shared stack: reset in place between cases; `recycle` cases get a fresh `down -v`
+ boot. The stack is torn down once, at the end of the run.
