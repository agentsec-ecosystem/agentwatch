# FT-CUR-2 — Cursor blocking events + IDE/CLI/remote

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** CUR-2 · **Suite:** s3-harness · **Class:** P/F

## Goal
Cursor blocking events + IDE/CLI/remote. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-CUR-2.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-CUR-2.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-CUR-2/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
