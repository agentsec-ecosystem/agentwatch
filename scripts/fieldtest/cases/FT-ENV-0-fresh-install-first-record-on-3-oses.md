# FT-ENV-0 — Fresh install → first record on 3 OSes

**Layer:** recorder · **LLM:** no · **Requires:** python · **PRD / claim:** EXT-10,13 NFR-4,25 NAM-1 · **Suite:** s1-install · **Class:** P/F

## Goal
Fresh install → first record on 3 OSes. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-ENV-0.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-ENV-0.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-ENV-0/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
