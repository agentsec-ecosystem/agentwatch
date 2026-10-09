# FT-HOSTILE-1 — Weaponized ingest containment

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** R5,ADR-0024,RSK-1 · **Suite:** s15-hostile · **Class:** P/F

## Goal
Weaponized ingest containment. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-HOSTILE-1.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-HOSTILE-1.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-HOSTILE-1/artifacts/`.

## Cleanup
Shared stack: reset in place between cases; `recycle` cases get a fresh `down -v`
+ boot. The stack is torn down once, at the end of the run.
