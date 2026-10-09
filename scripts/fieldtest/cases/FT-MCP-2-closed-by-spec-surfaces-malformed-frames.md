# FT-MCP-2 — Closed-by-spec surfaces + malformed frames

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** MCP-5,B4 · **Suite:** s3-harness · **Class:** P/F

## Goal
Closed-by-spec surfaces + malformed frames. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-MCP-2.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-MCP-2.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-MCP-2/artifacts/`.

## Cleanup
Shared stack: reset in place between cases; `recycle` cases get a fresh `down -v`
+ boot. The stack is torn down once, at the end of the run.
