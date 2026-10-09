# FT-XHT-2 — Live soak on OpenCode (real agent)

**Layer:** recorder · **LLM:** yes · **Requires:** docker,omlx · **PRD / claim:** XHT-2 · **Suite:** s3-harness · **Class:** P/F|D

## Goal
Live soak on OpenCode (real agent). See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-XHT-2.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-XHT-2.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-XHT-2/artifacts/`.

## Cleanup
Shared stack: reset in place between cases; `recycle` cases get a fresh `down -v`
+ boot. The stack is torn down once, at the end of the run.
