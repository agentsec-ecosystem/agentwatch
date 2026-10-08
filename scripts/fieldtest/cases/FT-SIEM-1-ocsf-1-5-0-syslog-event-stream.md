# FT-SIEM-1 — OCSF 1.5.0 + Syslog event stream

**Layer:** recorder · **LLM:** no · **Requires:** docker · **PRD / claim:** SIEM-1/2 · **Suite:** s5-identity · **Class:** P/F

## Goal
OCSF 1.5.0 + Syslog event stream. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-SIEM-1.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-SIEM-1.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-SIEM-1/artifacts/`.

## Cleanup
`down -v` via the runner teardown trap (`STACK_KEEP=1` keeps the stack).
