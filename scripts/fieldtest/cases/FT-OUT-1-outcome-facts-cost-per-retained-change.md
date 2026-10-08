# FT-OUT-1 — Outcome facts + cost per retained change

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** OUT-1 · **Suite:** s14-outcomes · **Class:** P/F|D

## Goal
Outcome facts + cost per retained change. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-OUT-1.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-OUT-1.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-OUT-1/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
