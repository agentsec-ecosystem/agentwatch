# FT-OTEL-1 — Canonical OTel agent spans in ≥2 backends

**Layer:** recorder · **LLM:** no · **Requires:** docker,jaeger · **PRD / claim:** OTEL-1 · **Suite:** s2-interop · **Class:** P/F

## Goal
Canonical OTel agent spans in ≥2 backends. See `docs/field-test/v0.2.0/field-test-plan.md` for the rationale.

## Steps
Run by `cases/steps/FT-OTEL-1.sh` (generated from `gen_cases.py`); every command is
captured to `commands.log`.

## Assertions
The case-specific assertions in `cases/steps/FT-OTEL-1.sh` (each recorded in
`assertions.ndjson`). **Pass = all assertions true. There is no skip.**

## Artifacts
`field-test/v0.2.0/results/<run-id>/cases/FT-OTEL-1/artifacts/`.

## Cleanup
Shared stack: reset in place between cases; `recycle` cases get a fresh `down -v`
+ boot. The stack is torn down once, at the end of the run.
