# Field-test Docker harness

Harness for the **Field Test Plan**: [`docs/field-test/v0.1.0/field-test-plan.md`](../../docs/field-test/v0.1.0/field-test-plan.md).
Final results are published to [`docs/field-test/v0.1.0/FIELD_TEST_REPORT.md`](../../docs/field-test/v0.1.0/FIELD_TEST_REPORT.md).

This **extends** the existing docker/test setup (it does not replace it):

- lifecycle primitive: [`../stack_lib.sh`](../stack_lib.sh) (`stack_up`, `stack_verify`, `stack_teardown_on_exit`)
- analyst stack: [`../../docker-compose.yml`](../../docker-compose.yml), `make e2e`, `make stack-smoke`
- seed/migrate: [`../seed-e2e-data.py`](../seed-e2e-data.py), [`../migrate-db.py`](../migrate-db.py)
- offline proof: [`../offline_e2e.py`](../offline_e2e.py)

## Layout

```
scripts/fieldtest/
  docker-compose.fieldtest.yml   overlay: recorder + verifier services
  recorder.Dockerfile            agentwatch SDK + CLI image (system under test)
  lib.sh                         ft_* helpers on top of stack_lib.sh
  .env.example                   copy to .env
  gen_cases.py                   source of truth: registry -> specs + steps
  run-case.sh                    run one case
  run-all.sh                     run the suite
  collect-results.py             aggregate verdicts -> summary.json/md
  emit-hook.py                   real hook frames through the socket
  seed-fixtures.py               seed a store (main/sdk/mcp sessions)
  run-soak.py                    long-session / latency generator
  drive-agent.py                 OMLX agent loop with scripted fallback
  otel-probe.py                  SDK OTLP export probe (FT-03/FT-19)
  corpus.sh                      synthetic corpus + detector validation (FT-06b/15b)
  llm-validation.sh              3-way LLM detector validation (FT-11b)
  cases/<ID>-*.md                per-case spec (generated; FT-15 hand-written)
  cases/steps/<ID>.sh            per-case runner (generated)
  cases/registry.json            the case list
```

Results land in **`field-test/v0.1.0/results/<run-id>/`** (stable step name; no timestamps) (gitignored except `.gitkeep`).

Screenshot case: [`../../apps/web/tests/e2e/screenshots.spec.ts`](../../apps/web/tests/e2e/screenshots.spec.ts)
writes full-page PNGs to `results/<run-id>/cases/FT-36/artifacts/screenshots/`.

## Prerequisites

- Docker daemon + Compose v2 (`docker compose`). FT-27 (`requires: python`) runs host-native and
  does not need Docker.
- Free ports: 5433, 8100, 5173, 16686, 4317, 4318 (3200/4319 for the `tempo` profile). Host port
  **8000 is reserved for OMLX** (the API publishes 8100 → container 8000, so there is no collision).
- Analyst cases (`FT-09/15/32/36`) install Node deps + chromium themselves.
- LLM cases (`FT-11`): OMLX reachable at `OMLX_BASE_URL`; primary model `Qwen3-4B-Instruct-2507-4bit`
  (see `.env.example`). If OMLX is unreachable the agent falls back to a scripted list and the case
  still runs to pass/fail on recorder assertions — that is a fallback, not a skip.
- Corpus cases (`FT-06b`/`FT-11b`/`FT-15b`): use the in-repo processed corpus at
  `data/traces/processed/` (gitignored, ~7.5 GB). Regenerate without any external repo via
  `python examples/demo-agent/generate_bulk_traces.py --num-traces 100000 --output-dir data/traces/processed`
  or `python -m analytics.main download-traces`.

## Run

```bash
cp scripts/fieldtest/.env.example scripts/fieldtest/.env
make fieldtest-gen                     # regenerate specs/steps from the registry
make fieldtest                         # all cases
make fieldtest-case ID=FT-04           # one case
make fieldtest-case ID=FT-36           # Playwright screenshots
make fieldtest-clean
```

**No skips.** Every case runs and is `pass`/`fail`; a case that cannot run (e.g. Docker absent for a
Docker case) is recorded as a failure and the suite exits non-zero. There is no `blocked`/`skipped`
status.
