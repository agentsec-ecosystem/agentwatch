# FT-15 — Detector validation (analyst layer)

**Maps to:** M23 field tests · PRD 30 (analytics signals), PRD 12 A2 (40-detector parity)
**Sources (ported):** [`../../../docs/field-test/v0.1.0/detector-validation-plan.md`](../../../docs/field-test/v0.1.0/detector-validation-plan.md)
(full 35-detector matrix) and [`../../../docs/field-test/v0.1.0/anomaly-validation-matrix.md`](../../../docs/field-test/v0.1.0/anomaly-validation-matrix.md)
(compact acceptance table).
**Fixtures (already present):** `examples/demo-agent/fixtures/{normal,loop,high_cost}.json`,
`examples/demo-agent/scenario-matrix.md`.

## Goal

Prove, on the real compose stack, that every seeded detector scenario behaves as the matrix says:
each positive fires, each negative does not, severity is correct, and per-detector
TPR ≥ 95% / FPR ≤ 5% (zero FPs on known-normal runs).

## Requires

- Docker daemon + Compose v2.
- Analyst services: `postgres`, `jaeger`, `otel-collector`, `api`, `analytics`, `web`.
- `make setup`; `scripts/seed-e2e-data.py`; `scripts/migrate-db.py` (or the worker's `ensure_schema`).
- LLM cases only: OMLX (`OMLX_BASE_URL`, `OMLX_MODEL`).

## Preconditions

- Clean stack (`down -v`), read-model tables created, seed data loaded.
- Detector matrix parsed from `detector-validation-plan.md` (positive/negative per detector).

## Steps

1. `bash scripts/fieldtest/run-case.sh FT-15` boots the analyst stack and verifies endpoints
   (reuses `stack_lib.sh`).
2. Seed the read model (`scripts/seed-e2e-data.py`) and materialize cohorts.
3. For each detector scenario in the ported matrix:
   a. generate/load the fixture trace (`examples/demo-agent/fixtures/*`, or the recipe appendix for
      cohort/timed detectors),
   b. run the analytics worker / detector pass,
   c. record whether the expected anomaly fired and its severity.
4. Repeat for the **negative** cases and assert zero FPs on `normal`.
5. (LLM detectors) run the synthetic-LLM pass per `synthetic-llm-validation-plan.md` via OMLX.
6. Capture the anomaly inbox screenshots + per-detector results.

## Assertions (machine-checkable)

- Every positive scenario fires its detector.
- No anomaly on the `normal` fixture.
- Severity matches the matrix (warning vs critical).
- Per-detector TPR ≥ 95%, FPR ≤ 5%.
- Detector names present in `services/analytics` and matched in the matrix.
- `/anomalies` returns the expected rows; web view renders them.

## Artifacts → `field-test/v0.1.0/results/<UTC-ts>/cases/FT-15/artifacts/`

- `detector-results.json` (per-detector fired/severity/TP/FP/FN)
- `anomalies.json` (API dump)
- screenshots of Fleet/Timeline/Anomaly Inbox
- analytics worker logs

## Pass

All assertions above; zero seeded false negatives; no FP on known-normal runs.

## Cleanup

`down -v` via the runner's teardown trap (`STACK_KEEP=1` to keep for debugging).

## Fallback / no skips

There is no skip. If the analyst stack cannot be booted or OMLX is unavailable, the case is
recorded as a **failure** (never a pass). Rule-based detectors run without OMLX; only the semantic
(LLM) detectors need it, and a missing model fails the case rather than hiding it.
