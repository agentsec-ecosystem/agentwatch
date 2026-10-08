# FT-CCO-1 — Claude Code native-OTel ingest + tool_use_id join

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** CCO-1 · **Suite:** s7-platform · **Class:** P/F

## Goal
Claude Code native-OTel ingest + tool_use_id join. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-CCO-1.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-CCO-1.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-CCO-1/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
