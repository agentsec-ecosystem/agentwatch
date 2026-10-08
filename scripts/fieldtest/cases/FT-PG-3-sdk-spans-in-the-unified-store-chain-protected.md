# FT-PG-3 — SDK spans in the unified store, chain-protected

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** PG-3 · **Suite:** s2-interop · **Class:** P/F|D

## Goal
SDK spans in the unified store, chain-protected. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-PG-3.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-PG-3.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-PG-3/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
