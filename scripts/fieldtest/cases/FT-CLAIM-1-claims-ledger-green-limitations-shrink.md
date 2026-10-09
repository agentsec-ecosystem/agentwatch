# FT-CLAIM-1 — Claims ledger green + limitations shrink

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** PRD-48 §5 · **Suite:** s15-hostile · **Class:** P/F

## Goal
Claims ledger green + limitations shrink. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-CLAIM-1.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-CLAIM-1.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-CLAIM-1/artifacts/`.

## Cleanup
Shared stack: reset in place between cases; `recycle` cases get a fresh `down -v`
+ boot. The stack is torn down once, at the end of the run.
