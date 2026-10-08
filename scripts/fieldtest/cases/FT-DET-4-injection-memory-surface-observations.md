# FT-DET-4 — Injection + memory-surface observations

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** DET-6/7 · **Suite:** s4-detectors · **Class:** P/F

## Goal
Injection + memory-surface observations. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-DET-4.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-DET-4.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-DET-4/artifacts/`.

## Cleanup
Shared stack: reset in place between cases; `recycle` cases get a fresh `down -v`
+ boot. The stack is torn down once, at the end of the run.
