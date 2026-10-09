# FT-ACC-1 — Role × data-class matrix + access log

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** ACC-1 · **Suite:** s12-governance · **Class:** P/F

## Goal
Role × data-class matrix + access log. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-ACC-1.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-ACC-1.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-ACC-1/artifacts/`.

## Cleanup
Shared stack: reset in place between cases; `recycle` cases get a fresh `down -v`
+ boot. The stack is torn down once, at the end of the run.
