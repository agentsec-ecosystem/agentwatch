# FT-SYS-1 — System-effects ingest join (Linux, opt-in)

**Layer:** recorder · **LLM:** no · **Requires:** docker,linux · **PRD / claim:** SYS-1 · **Suite:** s6-surfaces · **Class:** P/F|D

## Goal
System-effects ingest join (Linux, opt-in). See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-SYS-1.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-SYS-1.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-SYS-1/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
