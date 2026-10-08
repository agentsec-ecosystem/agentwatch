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

## v0.2.0 (M31 31.1–31.4)

The v0.2.0 field tests extend the same harness; they do **not** fork it. Results land under
**`field-test/v0.2.0/results/<suite>/`** (version-scoped), and the plan/report live under
`docs/field-test/v0.2.0/`.

| Piece | What |
|---|---|
| `run-suite.sh SUITE` | run one suite (`s1-install … s15-hostile`) → `field-test/v0.2.0/results/<suite>/` |
| `stack-v020.sh up\|down\|ps\|verify\|reset` | the v0.2.0 compose environment (profile services) |
| `seed-v020.sh [SERVICE]` | seed the fixture store in a service |
| `gen_cases.py` (+ `cases/registry.json`) | source of truth: 50 v0.1.0 + 94 v0.2.0 cases |
| `_ftutil.py` + `*.py` drivers | the M31 31.2 drivers the v0.2.0 steps call (at `/ft/scripts/`) |
| `fixtures/` | version-tagged, secret-scanned fixtures for the drivers |
| `docker-compose.fieldtest.yml` | adds `otel-grpc`, `fleet-h1..3`, `a2a-proxy`, `litellm`, `runner`, `managed-hooks` |

```bash
# v0.2.0 environment (profiles v020/managed/tempo)
scripts/fieldtest/stack-v020.sh up
scripts/fieldtest/seed-v020.sh

# one suite, or all (results under field-test/v0.2.0/results/)
FT_VERSION=v0.2.0 bash scripts/fieldtest/run-suite.sh s1-install
make fieldtest-v020          # runs every case (v0.1.0 regression + v0.2.0)
make fieldtest-suite SUITE=s7-platform
```

**Declare class.** The 19 `P/F|D` cases may resolve to `declared` via `ft_declare "<limitation>" "<gate>"`
only where the release gate says "or declared"; a `declared` case is recorded distinctly in the
verdict, `summary.json`, and the report — never as a pass. A hard-gate case can never declare.

**Versioning.** `FT_VERSION` selects the results root (`field-test/<FT_VERSION>/results`); `FT_RESULTS_ROOT`
overrides it outright. `run-suite.sh` sets `FT_VERSION=v0.2.0` by default.
