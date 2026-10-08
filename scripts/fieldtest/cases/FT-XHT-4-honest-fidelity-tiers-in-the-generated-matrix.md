# FT-XHT-4 — Honest fidelity tiers in the generated matrix

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** XHT-4 · **Suite:** s3-harness · **Class:** P/F

## Goal
Honest fidelity tiers in the generated matrix. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-XHT-4.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-XHT-4.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-XHT-4/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
