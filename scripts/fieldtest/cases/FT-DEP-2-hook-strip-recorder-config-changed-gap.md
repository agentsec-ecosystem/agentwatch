# FT-DEP-2 — Hook-strip → recorder-config-changed + gap

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** DEP-2 · **Suite:** s1-install · **Class:** P/F

## Goal
Hook-strip → recorder-config-changed + gap. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-DEP-2.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-DEP-2.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-DEP-2/artifacts/`.

## Cleanup
Shared stack: reset in place between cases; `recycle` cases get a fresh `down -v`
+ boot. The stack is torn down once, at the end of the run.
