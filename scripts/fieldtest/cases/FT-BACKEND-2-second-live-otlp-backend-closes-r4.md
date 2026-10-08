# FT-BACKEND-2 — Second live OTLP backend (closes R4)

**Layer:** recorder · **LLM:** no · **Requires:** docker,jaeger · **PRD / claim:** EXT-10,OTEL-1 · **Suite:** s15-hostile · **Class:** P/F

## Goal
Second live OTLP backend (closes R4). See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-BACKEND-2.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-BACKEND-2.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-BACKEND-2/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
