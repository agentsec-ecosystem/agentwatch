# FT-PRV-2 — Agent Trace export + content-free ranges

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** PRV-2/3 · **Suite:** s10-provenance · **Class:** P/F

## Goal
Agent Trace export + content-free ranges. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-PRV-2.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-PRV-2.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-PRV-2/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
