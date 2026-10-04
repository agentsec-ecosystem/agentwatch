# Field Test Plan — agentwatch v0.1.0

**Milestone:** M23 Field Tests (milestone 15) · **Status:** draft for review
**Plan & final report:** `docs/field-test/v0.1.0/` · **Docker harness:** `scripts/fieldtest/` · **Results:** `field-test/v0.1.0/results/`
**Local LLM:** OMLX (OpenAI-compatible, on-box) — primary model **`Qwen3-4B-Instruct-2507-4bit`** on host
port 8000; see §4 for the full model call-out. Deterministic fallback in every LLM case.

This is the single combined plan for field tests **and** Docker tests, and it replaces the earlier
six-scenario draft in this directory. The final results are published to
[`FIELD_TEST_REPORT.md`](FIELD_TEST_REPORT.md) here.

One plan, one lifecycle primitive, two layers under test:

- **Recorder layer** — hook/SDK → store → chain → replay → coverage → export → evidence. What the
  six field scenarios and the CUJs exercise.
- **Analyst layer** — Postgres read-model + API + analytics + web + Jaeger + otel-collector, driven
  by the existing Playwright suite.

`scripts/stack_lib.sh` is already "the reusable stack primitive for the Docker-backed field tests
(M23 23.1)"; both layers reuse it. This plan **extends** the existing setup rather than replacing it.

---

## 0. Readiness checklist & status

Legend: ✅ ready · ☐ todo.

**No skips.** Every case in the registry is implemented and runs; a case that does not pass is a
failure (there is no `skipped`/`blocked` status). A missing prerequisite (Docker, OMLX, Node)
fails the case rather than skipping it, so a green run cannot hide an unexercised path.

| Component | Status | Notes |
|---|---|---|
| Field test plan (this doc) | ✅ | §1–§11, §5a ported, §5b PRD-derived, §4 pinned LLMs |
| Final report scaffold | ✅ | `FIELD_TEST_REPORT.md` (all sections, cells to fill) |
| Detector validation assets | ✅ | `detector-validation-plan.md`, `anomaly-validation-matrix.md` |
| Fixtures | ✅ | `examples/demo-agent/fixtures/{normal,loop,high_cost}.json` |
| Harness skeleton | ✅ | `docker-compose.fieldtest.yml`, `recorder.Dockerfile` (installs `[signing,otlp]`), `.env.example` |
| Lifecycle lib | ✅ | `scripts/fieldtest/lib.sh` (sources `scripts/stack_lib.sh`; loads `.env`; per-case Docker gate) |
| Runners | ✅ | `run-case.sh`, `run-all.sh`, `collect-results.py` (pass/fail only) |
| Helpers | ✅ | `emit-hook.py` (spools like the real hook), `seed-fixtures.py`, `run-soak.py`, `drive-agent.py`, `otel-probe.py`, `corpus.sh`, `llm-validation.sh` |
| Case registry + specs + steps | ✅ | 50 cases, 50 step scripts (`gen_cases.py` regenerates and prunes stale files) |
| Screenshot capture | ✅ | `apps/web/tests/e2e/screenshots.spec.ts` → `results/<run-id>/cases/FT-36/artifacts/screenshots/` |
| Makefile targets | ✅ | `fieldtest`, `fieldtest-case`, `fieldtest-gen`, `fieldtest-clean` |
| Pre-work fix: Docker false-green | ✅ | `STACK_ON_NO_DOCKER=fail`; `ft_require_docker` hard-fails |
| Pre-work fix: `migrate-db` dead step | ✅ | Makefile target simplified |
| Pre-work fix: Playwright browsers | ✅ | `run-e2e.sh` and the analyst cases install chromium |
| Recorder cases | ✅ | FT-01/02/04/05/07/08/10/12/13/14/16/17/18/20/22/23/24/25/26/27/28/29/30/31/33/34/35, CUJs |
| Export / soak / LLM cases | ✅ | FT-03/19 (SDK OTLP → Jaeger), FT-06/25/28 (soak), FT-11 (OMLX `Qwen3-4B-Instruct-2507-4bit`) |
| Analyst cases | ✅ | FT-09/15/32/36 (Node deps + browsers installed by the case) |
| Predecessor LLM/corpus assets | ✅ | `synthetic-llm-validation-plan.md` ported; `m13-agents/` ported (generators retargeted to `agentwatch`); `scripts/m13/run-llm-validation.sh` present |
| New corpus/LLM/cross-framework cases | ✅ | FT-01b, FT-06b, FT-11b, FT-11c, FT-11d, FT-15b, FT-15c, FT-20b |

**Overall status: READY.** All 50 cases are implemented and self-contained; the full run executes
recorder, export, soak, LLM, and analyst layers with no skips.

### Run

```bash
make fieldtest-gen                       # regenerate specs/steps from the registry (optional)
cp scripts/fieldtest/.env.example scripts/fieldtest/.env   # set OMLX_MODEL if not the default
make fieldtest                           # all cases
make fieldtest-case ID=FT-04             # one case
make fieldtest-clean                     # remove run artifacts
```

---

## 1. What already exists (reuse as-is — the setup)

| Asset | Role |
|---|---|
| `docker-compose.yml` + `services/api/Dockerfile`, `services/analytics/Dockerfile`, `apps/web/Dockerfile` | analyst stack |
| `Makefile`: `setup`, `stack-up`, `stack-down`, `migrate-db`, `seed-e2e`, `e2e`, `stack-smoke` | entry points |
| `scripts/stack_lib.sh` | lifecycle primitive: `stack_require_docker`, `stack_up`, `stack_verify`, `stack_teardown_on_exit`, `STACK_SERVICES`/`STACK_ENDPOINTS` |
| `scripts/stack-smoke.sh` | build+boot+verify smoke |
| `scripts/run-e2e.sh` | boot → verify → migrate → seed → Playwright |
| `scripts/seed-e2e-data.py`, `scripts/migrate-db.py`, `scripts/export-e2e-data.py`, `scripts/reload-e2e-data.py`, `scripts/seed-investigations.py` | analyst data setup |
| `apps/web/tests/e2e/*.spec.ts` + `playwright.config.ts` | product views |
| `scripts/offline_e2e.py` | offline record→verify→replay+self-test |
| `scripts/first_run_timing.py`, `scripts/soak.py`, `scripts/perf_gate.py` | timing/soak/perf primitives |
| Workflows `e2e.yml`, `stack-smoke.yml`, `offline-e2e.yml`, `soak.yml`, `perf.yml`, `web.yml` | the Docker test harness already in CI |

**Do not create a parallel harness.** New runners source `stack_lib.sh` and reuse the seed,
timing, soak, and offline primitives.

---

## 2. What the existing setup does not do (gap this plan closes)

- It never produces an **agentwatch record** — the analyst suite seeds Postgres directly, so the
  six scenarios and every CUJ are unproven.
- Nothing enables **OTLP export** into the in-stack Jaeger/Tempo; those endpoints are liveness-probed only.
- There is **no per-scenario recorder runner** and no **combined result report**.

---

## 3. Topology

Base `docker-compose.yml` is unchanged. One overlay adds the recorder stack:
`scripts/fieldtest/docker-compose.fieldtest.yml`

| Service | Role | Notes |
|---|---|---|
| `recorder` | agentwatch SDK+CLI, daemon, store | system under test; store at `/data/agentwatch` |
| `agent` | traffic generator (OMLX ReAct loop, deterministic fallback) | shares the socket volume; added with FT-11 |
| `llm` | OMLX endpoint (or host via `host.docker.internal`) | OpenAI-compatible |
| `verifier` | clean, no-install auditor | `scripts/agentwatch_verify` / `agentwatch-verify` zipapp |
| reuses | `jaeger`, `otel-collector`, `postgres`, `api`, `analytics`, `web`, `tempo` | from base compose |

Boot: append `recorder agent verifier` to `STACK_SERVICES`, then
`docker compose -f docker-compose.yml -f scripts/fieldtest/docker-compose.fieldtest.yml up -d`.

---

## 4. Local LLM (OMLX) — models used

All LLM-backed cases run against a **local OMLX server** (OpenAI-compatible, on-box). No
case calls a hosted model.

| Role | Model | Where used | Notes |
|---|---|---|---|
| **Primary LLM** | `Qwen3-4B-Instruct-2507-4bit` | FT-11 (`drive-agent.py` ReAct loop); FT-11b/FT-11d (analytics semantic detectors); FT-15 LLM path | Selected for the v0.1.0 run for speed (4B, 262k ctx, verified present on the on-box OMLX server). 4B-vs-9B remains available for the ablation |
| Ablation (optional) | `Qwen3.5-4B-4bit` | detector model comparison | Faster alternative also present on OMLX; use if the primary misbehaves |
| Ablation (optional) | `Qwen3.5-9B-MLX-4bit` | 9B comparison (predecessor baseline) | The model the predecessor `agent-exec-trace` used for its field tests; also the analytics code default |
| No-LLM baseline | — (rule-based only) | FT-15 rule detectors; all non-LLM cases | Ground-truth comparison pass |

- **Endpoint:** OMLX on the host at **port 8000**. Recorder containers reach it via
  `host.docker.internal:8000/v1` (`--add-host=host.docker.internal:host-gateway` on Linux).
  The compose `api` service publishes host **8100** → container 8000, so host:8000 is free for
  OMLX — **no port collision**.
- **Env:** `OMLX_BASE_URL` (default `http://host.docker.internal:8000/v1`), `OMLX_MODEL`
  (pinned `Qwen3-4B-Instruct-2507-4bit`), `OMLX_API_KEY` (optional). The resolved base URL and
  model are recorded in `results/<run-id>/env.json` and on every LLM verdict.
- **Available on OMLX (verified):** `Qwen3-4B-Instruct-2507-4bit`, `Qwen3.5-4B-4bit`,
  `Qwen3.5-9B-MLX-4bit`, `Qwen3-8B-4bit`, `Llama-3.2-3B-Instruct-4bit`.
- **Prompting:** `temperature=0` and `chat_template_kwargs={"enable_thinking": false}`
  (JSON/tool calls without reasoning traces), matching the predecessor's validation setup.
- **Fallback:** if OMLX is unreachable, `drive-agent.py` uses a deterministic scripted action
  list; the case still exercises the recorder and reports `llm: fallback` in its artifacts. The
  case's pass/fail is based on recorder assertions, never on the model — a fallback run is not a
  skip.
- **Model pin:** tests must not silently follow a moving OMLX model. `OMLX_MODEL` is pinned here
  and asserted into `env.json`; changing the primary model is a plan amendment.

---

## 5. Combined scenario matrix

`Layer` R=recorder, A=analyst. `Reuse` = already exercised by an existing script/workflow.

| ID | Layer | Scenario (field §) | Driver | Pass | LLM | Reuse |
|---|---|---|---|---|---|---|
| FT-01 | R | Fresh install → first record (S1) | `recorder` | record within threshold; chain intact; timing captured | no | `first_run_timing.py` |
| FT-02 | R | Replay matches transcript (S2) | `agent` | timeline == raw transcript | yes | `replay` tests |
| FT-03 | R | OTLP export → Jaeger + Tempo (S3) | `recorder` | spans queryable in both; OCSF/CloudEvents validate | no | `otel-collector-config.yml` |
| FT-04 | R | Redaction attack, 0 leaks (S4) | `recorder` | 0 secrets; `secret-detected`; `verify-privacy` | no | `selftest` |
| FT-05 | R | Tamper → fail closed (S5) | `recorder` | chain break reported; gap classified; no silent drop | no | fault-injection tests |
| FT-06 | R | Long session / soak (S6) | `run-soak.py` | no gaps; bounded growth; p99 ≤ 5 ms | no | `soak.py`/`soak.yml` |
| FT-07 | R | `agentwatch demo` proof | `recorder` | chain verdict; demo excluded; `--purge` clean | no | demo tests |
| FT-08 | R | Checkpoint notarize + sign (W7/W9) | `recorder` | digest; signed verifies; TSA-down → digest-only | no | mock TSA |
| FT-10 | R | Offline / no egress (R6) | `recorder` | record→verify→replay under `unshare --net`; egress audit clean | no | `offline_e2e.py` |
| FT-11 | R | LLM agent loop | `agent` | every call captured; approvals derived; flow/secret traces correct | yes | — |
| CUJ-08 | R | Incident → evidence (flagship) | CLI + `verifier` | three verdicts unambiguous, offline, no install | yes* | `evidence` tests |
| CUJ-09 | R | Recorder trust report | CLI | `gap:unexplained` = 0 | no | coverage tests |
| CUJ-10 | R | Cost answer | CLI | one command; pricing version stamped | no | cost tests |
| CUJ-11 | R | SDK ↔ harness union | SDK agent | both sources; `source` set; SDK not chain-protected | no | union tests |
| CUJ-12 | R | Erase and prove it | CLI | erasure provable; content not resurrected | no | purge/evidence tests |
| CUJ-13 | R | MCP surface drift | CLI | one `tool-surface-changed` + digests | no | mcp_surface tests |
| CUJ-14 | R | "Did a human approve?" | CLI | value never inferred | no | approval tests |
| FT-09 | A | Product E2E (existing) | `run-e2e.sh` | all Playwright specs green | no | `e2e.yml` + specs |

\* CUJ-08 uses the LLM only to generate a realistic session; falls back to scripted.

---

## 5a. Ported from agent-exec-trace (predecessor)

agentwatch supersedes `agent-exec-trace`; the predecessor's field-test assets are the porting source.
Its local path is `~/Desktop/code/github/agent-exec-trace` (also mirrored at
`agentsec-ecosystem/_predecessors/agent-exec-trace`). Port these, adapting paths/names to agentwatch.

| Source (agent-exec-trace) | What it is | Bring over as |
|---|---|---|
| `docs/test/e2e-testing-plan.md` | Playwright setup, CUJ catalog, per-view test catalog, screenshot strategy, Makefile integration, acceptance criteria, coverage checklist, failure triage | **FT-09** analyst E2E acceptance + failure-triage; **FT-32** (a11y/axe) |
| `docs/test/e2e-seed-data.md` | Deterministic counts, selector expectations, table→scenario map, span-tree strategy, edge cases via route intercepts | deterministic seeds/assertions for **FT-09** |
| `examples/demo-agent/scenario-matrix.md` (+ `fixtures/`) | `normal` / `loop` / `high_cost` (+ planned `retry`) with expected outcomes + detector mapping + version labels for cohorts | **FT-15** fixtures — ✅ already ported and byte-identical (`examples/demo-agent/fixtures/`, `examples/demo-agent/scenario-matrix.md`) |
| `docs/field-test/field-test-plan.md` (1087 lines) | 35-detector matrix, **70+ positive / 70+ negative** scenarios, 5 workloads (Request Triage seeded+param, Research Crew, RAG Q&A, 15-agent OSS fleet), pre-flight hardening table, validation criteria (TPR ≥95%, FPR ≤5%, severity 100%, clarity/actionability ≥4.5), review sheet, deliverables | **FT-15** — ✅ ported to [`detector-validation-plan.md`](detector-validation-plan.md) |
| `docs/field-test/anomaly-validation-matrix.md` | Compact detector cases + documented blind spots | **FT-15** — ✅ ported to [`anomaly-validation-matrix.md`](anomaly-validation-matrix.md); case spec at `scripts/fieldtest/cases/FT-15-detector-validation.md` |
| `docs/field-test/synthetic-llm-validation-plan.md` (516 lines) | Three-way design (rule-based vs LLM vs combined), MLX models (Qwen3.5-9B-MLX-4bit), telemetry, ground truth, success criteria, 4B-vs-9B ablation | **FT-11b** (wired) — ✅ ported to [`synthetic-llm-validation-plan.md`](synthetic-llm-validation-plan.md); runner `scripts/fieldtest/llm-validation.sh` |
| `docs/field-test/m13-100-trace-report.md` (517 lines) | 100-trace LLM-augmented run: three-pass design, telemetry, per-detector fire rates, additivity, limitations | **FT-06b** large-corpus run; **FT-11b** LLM corpus |
| `docs/field-test/field-test-report-{v1,v2,synthetic}.md` | Report structure, TP/FP/FN protocol, detector-confidence framework, root-cause analysis, verdict, next-steps | template for `docs/field-test/v0.1.0/FIELD_TEST_REPORT.md` |
| `examples/demo-agent/run_demo.py`, `generate_bulk_traces.py` | Demo driver + bulk trace generation | **FT-06b** corpus generator (wired via `scripts/fieldtest/corpus.sh`) |
| `m13-agents/` (10 OSS agent harnesses: langchain, crew, react, pydantic, mcp, weather, chatbot, eval-graph, github, raw) | Cross-framework agent harness | ✅ ported to `m13-agents/` (source; generators retargeted to `agentwatch`); **FT-11c** runs the raw agent end-to-end |
| `scripts/export-e2e-data.py`, `reload-e2e-data.py`, `seed-e2e-data.py` | Seed/export/reload helpers | diff against agentwatch's descendants; port missing reload/export |

**Note:** agentwatch already carries the E2E specs (`apps/web/tests/e2e/*`), the seed helpers
(`scripts/seed-e2e-data.py` / `reload-e2e-data.py` / `export-e2e-data.py`), the base stack, and the
`examples/demo-agent` fixtures/scenario-matrix — all byte-identical to the predecessor. **Ported:**
the 35-detector validation plan, the anomaly validation matrix, the FT-15 case spec, the
synthetic-LLM validation plan, `scripts/m13/run-llm-validation.sh`, and the `m13-agents` harness
(generators retargeted to `agentwatch`). **In-repo corpora:** `data/traces/processed/` (100,010 HF traces, 7.5 GB; FT-06b/FT-11b/FT-15b/FT-15c)
and `data/traces2/synthetic/` (1,000,343 synthetic traces, 4.9 GB; FT-11d). Both are gitignored and can
be regenerated without any external repo via `python examples/demo-agent/generate_bulk_traces.py
--num-traces 100000 --output-dir <dir>` or `python -m analytics.main download-traces`.

---

## 5b. Additional field tests mined from the agentwatch PRDs

The six scenarios + CUJs don't cover the product's own failure/compliance/operability guarantees.
These are field tests for claims the PRDs make (each already has unit coverage; the field test
proves it on a real machine/stack).

### Security baseline & fail-closed (PRD 06 threat scenarios, PRD 17 F1–F10)

| ID | Field test | PRD |
|---|---|---|
| FT-12 | Edit hook config to disable recording → detected, fail-closed, surfaced | 06 #1, 17 F7 |
| FT-13 | Tamper a store record (edit/remove) → `verify-store` breaks at the right seq; `--repair` salvages the intact prefix | 06 #2, 17 F4 |
| FT-14 | `SIGKILL` the daemon → restart synthesizes a `recording-gap` record chained between old/new; clean stop → no gap | 17 F1, 21 B3 |
| FT-16 | Daemon down → hook spools the frame; restart → replayed exactly once (idempotent re-delivery) | 17 F2, 21 B1/B2 |
| FT-17 | Malformed frame → quarantined verbatim (0600, excluded from export) + `hook-error`; `reprocess` after adapter fix | 17 F8, 21 B4 |
| FT-18 | Fill the store to the cap → recording **stops and surfaces** (no overwrite); retention clears it | 17 F3, 13 NFR-3 |
| FT-19 | Drop the OTLP endpoint mid-run → records keep accumulating, export resumes from the cursor, no loss | 17 F5 |
| FT-20 | Force the redaction self-test to fail → export blocked, local recording continues | 17 F6, DD-09 |
| FT-22 | Clock skew (move wall clock) → `degraded` + capped/flagged gap | 17 F9, 21 B5 |
| FT-23 | Miss a session boundary → session closed `incomplete`; replay still works | 17 F10 |
| FT-35 | Capture-fidelity matrix: metadata-only / truncated / hashed / full each behave per spec | 25 |

### Self-observability & operator trust (PRD 13 NFR-12, PRD 22, PRD 24)

| ID | Field test | PRD |
|---|---|---|
| FT-24 | `/healthz` states `recording` / `degraded` / `stopped` with the documented fields; **never** reports `recording` while stopped; `agentwatch status` matches | 13 NFR-12, 22 |
| FT-33 | OTel self-metrics emitted when enabled (`records.stored`, `gaps`, `export.errors`, `chain.broken`, `self_test.passing`) | 13 NFR-12, 22 |
| FT-20b | Redaction self-test gate visible in health as `redaction.self_test_passing` | 13 NFR-9 |

### Performance, footprint & operability (PRD 13 NFRs, PRD 28)

| ID | Field test | PRD |
|---|---|---|
| FT-01b | First-run ≤15 min measured end to end (reuse `scripts/first_run_timing.py`) | 13 NFR-4, R2 |
| FT-25 | Hook-path latency benchmark: spawn → socket send → exit, published; and an **async ordering** run under load | 13 NFR-1, 28 P1 |
| FT-26 | Bounded storage + rotation: store cap, `daemon.log` rotation at cap, `0700`/`0600` posture, `doctor` flags a loose mode | 13 NFR-3, 28 F5/F6 |
| FT-27 | Portability: recorder run on **Linux (Docker)** and a **macOS** host; identical records | 13 NFR-6 |
| FT-28 | Scale: 10k+ records/day ingestion; event→stored ≤30 s | 13 NFR-2/NFR-7 |
| FT-06b | Long session (1k–20k calls) with the ported bulk-trace generator | 13 NFR-1, R1 |

### Data integrity & interoperability (PRD 21, PRD 12, PRD 27)

| ID | Field test | PRD |
|---|---|---|
| FT-30 | Store-format versioning: a v1 store reads/migrates; unknown version rejected with the range named | 21, 15 |
| FT-29 | Multi-harness conformance: ≥5 Tier-1 + ≥3 Tier-2 adapters via the ported `m13-agents` harness | 12 R10, 27 |
| FT-31 | Least privilege on a shared box: store/quarantine/spool/log all `0600`, dir `0700` | 28 F5 |
| FT-34 | Usage/cost accounting: `cost --by …` matches the seeded token totals; pricing version stamped | 20, S6 |

### Detector & LLM validation (PRD 30, PRD 12 A2)

| ID | Field test | PRD |
|---|---|---|
| FT-15 | 35-detector validation (ported matrix): every seeded positive fires, zero FPs on known-normal runs, severity/clarity/actionability thresholds met | 30, 12 A2 |
| FT-11 | OMLX three-way LLM validation (rule vs LLM vs combined) with ground truth and model ablation | 29, 30 |
| FT-11b | 100-trace LLM-augmented corpus (ported M13.1 design) | 29, 30 |
| FT-11c | Cross-framework agent runs (ported `m13-agents`) feeding both recorder and detectors | 27, 12 R10 |

### Analyst UI capture (PRD A5, NFR-10)

| ID | Field test | PRD |
|---|---|---|
| FT-09 | Product E2E (Playwright) + failure triage | A5 |
| FT-32 | UI a11y (axe) | 13 NFR-10 |
| FT-36 | **Playwright screenshot capture** — `apps/web/tests/e2e/screenshots.spec.ts` captures full-page PNGs of Dashboard/Fleet/Compare/Anomalies into `results/<run-id>/cases/FT-36/artifacts/screenshots/` | A5 |

**Aggregate:** ~90 positive + ~90 negative detector scenarios (ported) plus ~28 new
recorder/operability field tests — the six original scenarios become a subset.

---

## 6. Case creation & run scripts (extend, don't duplicate)

Harness lives under `scripts/fieldtest/` (next to the existing setup scripts):

- `README.md`, `docker-compose.fieldtest.yml`, `.env.example`, `recorder.Dockerfile`
- `cases/FT-XX-*.md` — one spec each: goal/maps-to, requires, preconditions, numbered steps,
  machine-checkable assertions, artifacts, pass criteria, cleanup, fallback
- `lib.sh` — sources `../stack_lib.sh`; adds `ft_case_begin/end`, `ft_run`, `ft_assert`,
  `ft_capture`, `ft_require_docker` (**hard-fail**), `ft_teardown`
- `run-case.sh <ID> [--keep]`, `run-all.sh [--case ID ...]`
- `emit-hook.py` (real hook/socket path), `drive-agent.py` (OMLX), `run-soak.py` (wraps existing soak),
  `seed-fixtures.py` (runtime-built secrets/transcripts/git repo), `collect-results.py`
- Makefile additions: `fieldtest`, `fieldtest-case ID=…`, `fieldtest-clean` (wrapping existing `stack-*`)

Case lifecycle: `ft_require_docker` → `stack_up` (base + overlay) → `stack_verify` (extended
services/endpoints) → seed → steps → `ft_capture` → `down -v` via `stack_teardown_on_exit`.

---

## 7. Results (all under `field-test/v0.1.0/results/`)

```
field-test/v0.1.0/results/<run-id>/   # stable name, e.g. step2 (no timestamps)
  summary.md / summary.json
  env.json                 # docker/compose versions, image digests, OMLX model
  cases/<ID>/{commands.log,stdout.log,stderr.log,verdict.json,artifacts/…}
```

`summary.json` carries per-case status (`pass|fail`), durations,
assertion booleans, artifact paths. `summary.md` feeds [`FIELD_TEST_REPORT.md`](FIELD_TEST_REPORT.md)
(#143), clearing the ◑ partials for S1/S3/S6. `field-test/v0.1.0/results/` is gitignored except
`.gitkeep`.

---

## 8. Execution (reusing existing targets)

```bash
make setup
(cd apps/web && npm ci && npx playwright install --with-deps chromium)

# full combined run (OMLX on host port 8000; primary model pinned)
OMLX_BASE_URL=http://host.docker.internal:8000/v1 OMLX_MODEL=Qwen3-4B-Instruct-2507-4bit \
  bash scripts/fieldtest/run-all.sh

# one case
bash scripts/fieldtest/run-case.sh FT-04 --keep

# analyst layer (unchanged)
make e2e
```

---

## 9. Pre-work fixes

1. `scripts/stack_lib.sh` `stack_require_docker` exits **0** when Docker is absent → the field
   harness hard-fails the case (`STACK_ON_NO_DOCKER=fail`; per-case Docker gate), never green.
2. `make migrate-db` has a dead container step (`if False else ''` + `|| true`); the analytics worker
   already `ensure_schema()`s. Remove or repair.
3. `scripts/run-e2e.sh` doesn't install Playwright browsers (CI does) — assert/install.
4. Add the recorder overlay + cases (the actual gap).
5. OMLX reachable from containers (`--add-host=host.docker.internal:host-gateway` on Linux);
   host port **8000** reserved for OMLX (API publishes 8100).
6. Free ports 5433/8100/5173/16686/4317/4318 (3200/4319 for tempo).
7. Runtime-generated secret fixtures (push-protection).

---

## 10. Gates & issue mapping

- Case passes only on explicit assertions; anything that is not a pass is a `fail` (there is no
  skip/blocked); overall run is nonzero if any required case fails.
- FT-01…06 → #141/#142; FT-07 → S31; FT-08 → #276/#278; FT-09 → `e2e.yml`; FT-10 → R6/NFR-9;
  FT-11 → P5/S11; CUJ-08…14 → #279–#285; results/report → #143; regressions → #144;
  nightly → #145; docs → #146/#147.
- Ported assets (5a): FT-15 and the detector matrix → **#141/#142** (port) + PRD 30; FT-11/11b →
  PRD 29/30; report template → **#143**; `m13-agents` → **#146/#147**; rollout of the ported set →
  **#144**.
- New PRD-derived tests (5b): FT-12…FT-35 → **#141/#142** with their PRD clauses (06/13/17/21/22/24/
  25/27/28/30) named in each case spec; every row already has a unit test, so the field test is the
  real-machine proof, not new logic.

## 5c. Authoritative test-case inventory (all cases that will run)

This is the complete, authoritative list of every case the field-test suite runs.
Every case is `pass`/`fail` — there is no skip. The registry at
`scripts/fieldtest/cases/registry.json` is the machine source of truth; this section
is the human-readable mirror and must stay in sync with it.

### 5c.1  Field-test cases (50 runnable cases)

| ID | Layer | LLM | Requires | Scenario | PRD / claim |
|---|---|---|---|---|---|
| FT-01 | R | no | docker | Fresh install → first record | 13 NFR-4,R2 |
| FT-01b | R | no | python | First-run timing ≤ 15 min | 13 NFR-4,R2 |
| FT-02 | R | no | docker | Replay matches transcript | R8 |
| FT-03 | R | no | docker,jaeger | OTLP export → Jaeger | R4 |
| FT-04 | R | no | docker | Redaction attack, 0 leaks | R7,06 |
| FT-05 | R | no | docker | Store tamper → fail closed | 17 F4 |
| FT-06 | R | no | docker | Long session / soak | 13 NFR-1 |
| FT-06b | A | no | docker | In-repo corpus soak + validate | 13 NFR-1,30 |
| FT-07 | R | no | docker | agentwatch demo proof | S31 |
| FT-08 | R | no | docker | Checkpoint notarize + sign | W7/W9 |
| FT-09 | A | no | docker,node | Product E2E (Playwright) | A5 |
| FT-10 | R | no | docker | Offline / no egress | R6,NFR-9 |
| FT-11 | R | yes | docker,omlx | LLM agent loop (OMLX) | S11,30 |
| FT-11b | A | yes | docker,omlx | 3-way LLM detector validation (OMLX) | 29,30 |
| FT-11c | R | no | docker,jaeger | Cross-framework agent traces | 27,12 R10 |
| FT-11d | A | yes | docker,omlx | 1M synthetic corpus LLM pilot (M13.1) | 29,30 |
| FT-12 | R | no | docker | Bad config → fail closed | 17 F7,06 #1 |
| FT-13 | R | no | docker | Store tamper + repair | 17 F4 |
| FT-14 | R | no | docker | Daemon SIGKILL → recording-gap | 17 F1,21 B3 |
| FT-15 | A | no | docker,node | Detector validation (ported matrix) | 30,12 A2 |
| FT-15b | A | no | docker | Detector corpus compatibility diagnostic | 30,12 A2 |
| FT-15c | A | no | docker | Full 100k-trace corpus validation | 30,12 A2 |
| FT-16 | R | no | docker | Spool + exactly-once | 17 F2,21 B1 |
| FT-17 | R | no | docker | Quarantine + reprocess | 17 F8,21 B4 |
| FT-18 | R | no | docker | Store full → stop + surface | 17 F3 |
| FT-19 | R | no | docker,jaeger | Export endpoint down → resume | 17 F5 |
| FT-20 | R | no | docker | Self-test fail → export blocked | 17 F6 |
| FT-20b | R | no | docker | Self-test visible in health | 13 NFR-9 |
| FT-22 | R | no | docker | Clock skew → degraded | 17 F9 |
| FT-23 | R | no | docker | Partial session incomplete | 17 F10 |
| FT-24 | R | no | docker | /healthz states never lie | 13 NFR-12 |
| FT-25 | R | no | docker | Hook latency + async ordering | 28 P1 |
| FT-26 | R | no | docker | Bounded store/logs + posture | 28 F5/F6 |
| FT-27 | R | no | python | Portability: host-native run | 13 NFR-6 |
| FT-28 | R | no | docker | Scale 10k/day | 13 NFR-7 |
| FT-29 | R | no | docker | Multi-harness adapters conformance | 27,12 R10 |
| FT-30 | R | no | docker | Store-format migration | 21 |
| FT-31 | R | no | docker | Least-privilege on shared box | 28 F5 |
| FT-32 | A | no | docker,node | UI a11y | 13 NFR-10 |
| FT-33 | R | no | docker | Self-observability contract | 13 NFR-12 |
| FT-34 | R | no | docker | Usage/cost accounting | 20,S6 |
| FT-35 | R | no | docker | Capture-fidelity matrix | 25 |
| FT-36 | A | no | docker,node | Playwright E2E screenshots | A5,NFR-10 |
| CUJ-08 | R | no | docker | Incident → evidence (flagship) | CUJ-8 |
| CUJ-09 | R | no | docker | Recorder trust report | CUJ-9 |
| CUJ-10 | R | no | docker | Cost answer | CUJ-10 |
| CUJ-11 | R | no | docker | SDK ↔ harness union | CUJ-11 |
| CUJ-12 | R | no | docker | Erase and prove it | CUJ-12 |
| CUJ-13 | R | no | docker | MCP surface drift | CUJ-13 |
| CUJ-14 | R | no | docker | "Did a human approve?" | CUJ-14 |

### 5c.2  Ported predecessor detector scenarios (154 cases, 35 detectors)

These are the per-detector positive/negative scenario cases ported verbatim from
`agent-exec-trace/docs/field-test/field-test-plan.md` into
[`detector-validation-plan.md`](detector-validation-plan.md). `Positive` must fire;
`Negative` must not. They are executed **in full** by **FT-15**
(`analytics.scenario_validation --all`): all 154 scenarios across all 35 rule-based
detectors — positives fire, negatives stay silent, escalations are `critical` — plus
**FT-15b/15c** (in-repo corpus diagnostic + full-corpus validation) for breadth. A compact
boundary subset is available as the default run of `analytics.scenario_validation`.

| Case | Detector | Expectation | Scenario |
|---|---|---|---|
| L1 | LoopDetector | must fire | Missing account (`acc_404`) — `lookup_account` fails, agent retries search + lookup |
| L2 | LoopDetector | must fire | Bad KB query that keeps returning non-matches, triggers repeated `search_kb` |
| L3 | LoopDetector | must fire | Researcher finds incomplete data, Analyst rejects, Researcher retries same search 6x |
| L4 | LoopDetector | must fire | Embedding mismatch causes repeated identical retrievals, agent retries query 7x |
| L5 | LoopDetector | must NOT fire | Normal password reset — `search_kb` then `lookup_account` then resolve |
| L6 | LoopDetector | must NOT fire | Tool alternation — `search_kb` → `lookup_account` → `search_kb` → `lookup_account` |
| L7 | LoopDetector | must NOT fire | Polling tool `wait-for-deploy` called 8x from allowlist |
| L8 | LoopDetector | must NOT fire | Researcher runs 4 different searches (different queries) |
| L9 | LoopDetector | must NOT fire | Normal single retrieval then answer |
| R1 | RetryStormDetector | must fire | Loop scenario also produces retries on failed lookups |
| R2 | RetryStormDetector | must fire | All tools fail — account lookup fails 8x, all retries fail |
| R3 | RetryStormDetector | must fire | Analyst rejects Researcher output 6x, all retries return same bad data |
| R4 | RetryStormDetector | must fire | Hallucination check fails 5x, agent retries with different prompts |
| R5 | RetryStormDetector | must NOT fire | Normal run with 2 retries on a transient network error, both succeed |
| R6 | RetryStormDetector | **must fire** (known blind spot) | 6 retries but 5 succeed — `RetryStormDetector` fires on count alone; transient/systemic suppression is not implemented (see `anomaly-validation-matrix.md`) |
| R7 | RetryStormDetector | must NOT fire | 3 retries on a bad search, all succeed |
| R8 | RetryStormDetector | must NOT fire | 4 retries on LLM timeout, all succeed eventually |
| R9 | RetryStormDetector | must NOT fire | Any run with 0 retries |
| C1 | CostSpikeDetector | must fire | High-cost open-ended scenario — deep KB search chain |
| C2 | CostSpikeDetector | must fire | 20-turn KB exhaustive search with large tool costs |
| C3 | CostSpikeDetector | must fire | Deep research chain — Researcher finds 10 sources, Analyst validates all, Writer synthesiz |
| C4 | CostSpikeDetector | must fire | Embedding exhaustive scan across 50 documents |
| C5 | CostSpikeDetector | must NOT fire | Normal reset password — 2 tool calls |
| C6 | CostSpikeDetector | must NOT fire | Medium workload but still under absolute threshold |
| C7 | CostSpikeDetector | must NOT fire | Baseline too sparse (<5 runs) → relative check skipped, cost under absolute |
| C8 | CostSpikeDetector | must NOT fire | Normal single-doc retrieval + short answer |
| PL1 | PatternLoopDetector | must fire | search_kb → lookup → search_kb → lookup repeats 6x in a window |
| PL2 | PatternLoopDetector | must fire | retrieve → rank → retrieve → rank → retrieve → rank across 12 spans |
| PL3 | PatternLoopDetector | must NOT fire | Normal workflow: search → lookup → resolve → close |
| PL4 | PatternLoopDetector | must NOT fire | retrieve → retrieve → retrieve (short window, 3 cycles only) |
| AL1 | ArgumentLoopDetector | must fire | search_kb("password reset") called 4x with identical args |
| AL2 | ArgumentLoopDetector | must fire | Researcher calls search("market trends 2025") 5x |
| AL3 | ArgumentLoopDetector | must NOT fire | search_kb("password") then search_kb("account") then search_kb("billing") |
| AL4 | ArgumentLoopDetector | must NOT fire | retrieve("weather") called 2x then stop |
| TE1 | ToolErrorRateDetector | must fire | 4 of 10 tool calls fail (40% error rate) |
| TE2 | ToolErrorRateDetector | must fire | 6 of 12 tool calls fail (50% error rate) |
| TE3 | ToolErrorRateDetector | must NOT fire | 1 of 10 tool calls fails (10% error rate) |
| TE4 | ToolErrorRateDetector | must NOT fire | 0 errors in 8 tool calls |
| SE1 | SpecificToolErrorDetector | must fire | search_kb called 5x, 2 fail (40%); lookup called 3x, all ok |
| SE2 | SpecificToolErrorDetector | must fire | Researcher's search tool fails 3 of 5 calls (60%) |
| SE3 | SpecificToolErrorDetector | must NOT fire | search_kb 0/5 fail, lookup 1/5 fail (20%) |
| SE4 | SpecificToolErrorDetector | must NOT fire | retrieve 1/8 fail (12.5%) |
| TL1 | ToolLatencyDetector | must fire | search_kb avg 100ms; one lookup call takes 500ms (5x avg) |
| TL2 | ToolLatencyDetector | must fire | retrieve avg 200ms; one retrieval takes 1200ms (6x avg) |
| TL3 | ToolLatencyDetector | must NOT fire | All tool calls 80-120ms (tight cluster) |
| TL4 | ToolLatencyDetector | must NOT fire | Tool calls 100ms, 120ms (1.2x avg) |
| TT1 | ToolTimeoutDetector | must fire | lookup_account takes 90s before failing |
| TT2 | ToolTimeoutDetector | must fire | retrieve across 50 documents takes 180s |
| TT3 | ToolTimeoutDetector | must NOT fire | Tool calls all under 30s |
| TT4 | ToolTimeoutDetector | must NOT fire | Standard retrieval under 10s |
| RC1 | RedundantToolCallDetector | must fire | retrieve called 4x returning same document |
| RC2 | RedundantToolCallDetector | must fire | search called 5x, all return empty "no results" |
| RC3 | RedundantToolCallDetector | must NOT fire | retrieve called 2x, different documents |
| RC4 | RedundantToolCallDetector | must NOT fire | retrieve called 3x, 3 different docs |
| CV1 | CostVsBaselineDetector | must fire | Cohort baseline $2.50; run costs $6.00 (2.4x) |
| CV2 | CostVsBaselineDetector | must fire | Cohort avg $0.80; heavy refactor run costs $3.20 (4x) |
| CV3 | CostVsBaselineDetector | must NOT fire | Cohort baseline $2.50; run costs $3.00 (1.2x) |
| CV4 | CostVsBaselineDetector | must NOT fire | Cohort has <5 baseline runs |
| CE1 | CostEfficiencyDetector | must fire | $8.00 cost for 10 tool calls ($0.80/tool) |
| CE2 | CostEfficiencyDetector | must fire | Successful run with 25 tool calls, $2.00 total |
| CE3 | CostEfficiencyDetector | must NOT fire | $4.00 for 15 tool calls ($0.27/tool) |
| CE4 | CostEfficiencyDetector | must NOT fire | Failed run with 30 tool calls |
| TK1 | TokenExplosionDetector | must fire | Early steps use 100 tokens; late Writer steps use 500 tokens (5x) |
| TK2 | TokenExplosionDetector | must fire | Early: 50 token retrievals; late: full-doc synthesis at 400 tokens (8x) |
| TK3 | TokenExplosionDetector | must NOT fire | All spans ~200 tokens |
| TK4 | TokenExplosionDetector | must NOT fire | Fewer than 4 spans total |
| PT1 | PerToolCostSpikeDetector | must fire | search_kb is 6/8 tool calls (75% share, 3x dominance) |
| PT2 | PerToolCostSpikeDetector | must fire | lookup_account is 8/10 calls (80% share, 4x dominance) |
| PT3 | PerToolCostSpikeDetector | must NOT fire | 3 tools each ~33% share |
| PT4 | PerToolCostSpikeDetector | must NOT fire | Dominant tool has only 2 calls |
| WC1 | WastedToolCallsDetector | must fire | retrieve returns same doc string 4x |
| WC2 | WastedToolCallsDetector | must fire | search returns empty result 3x |
| WC3 | WastedToolCallsDetector | must NOT fire | retrieve returns 3 different docs |
| WC4 | WastedToolCallsDetector | must NOT fire | Only 2 tool calls total |
| RD1 | RunDurationDetector | must fire | Workload avg 10s; run takes 65s (6.5x) |
| RD2 | RunDurationDetector | must fire | Workload avg 8s; browser-use run takes 90s (11x) |
| RD3 | RunDurationDetector | must NOT fire | Workload avg 10s; run takes 25s (2.5x) |
| RD4 | RunDurationDetector | must NOT fire | Workload avg 5s; run takes 4s |
| MS1 | MaxStepHitDetector | must fire | Agent runs 95 steps, hits configured max, status=max_steps_hit |
| MS2 | MaxStepHitDetector | must fire | Agent loops close to max, hits 100-step limit |
| MS3 | MaxStepHitDetector | must NOT fire | Agent completes in 10 steps |
| MS4 | MaxStepHitDetector | must NOT fire | 3-step retrieval + answer |
| SF1 | StepEfficiencyDetector | must fire | Successful run with 25 tool calls |
| SF2 | StepEfficiencyDetector | must fire | Successful run with 50 tool calls |
| SF3 | StepEfficiencyDetector | must NOT fire | Successful run with 8 tool calls |
| SF4 | StepEfficiencyDetector | must NOT fire | 25 tool calls but status=failed |
| IA1 | InactivityDetector | must fire | Researcher pauses 45s before Analyst starts |
| IA2 | InactivityDetector | must fire | 90s gap waiting for Writer approval |
| IA3 | InactivityDetector | must NOT fire | Steps 2-5s apart |
| IA4 | InactivityDetector | must NOT fire | 15s gap between Researcher and Analyst |
| PC1 | PrematureCompletionDetector | must fire | Agent errors after 1 tool call (status=error) |
| PC2 | PrematureCompletionDetector | must fire | Agent fails before invoking any tools, status=error |
| PC3 | PrematureCompletionDetector | must NOT fire | Agent completes normally in 3 steps, status=success |
| PC4 | PrematureCompletionDetector | must NOT fire | Agent errors after 5 tool calls |
| SR1 | SystemicRetryDetector | must fire | 5 retries, all fail (0% success) |
| SR2 | SystemicRetryDetector | must fire | Analyst rejects Researcher output 6x, 0 success |
| SR3 | SystemicRetryDetector | must NOT fire | 5 retries, 4 succeed (80% success) |
| SR4 | SystemicRetryDetector | must NOT fire | 0 retries |
| TR1 | TransientRetryDetector | must fire | 3 temporary network errors, all retry and succeed |
| TR2 | TransientRetryDetector | must fire | 5 LLM timeout retries, all eventually succeed |
| TR3 | TransientRetryDetector | must NOT fire | 2 retries, both succeed |
| TR4 | TransientRetryDetector | must NOT fire | 3 retries, all fail |
| CR1 | CascadingRetryDetector | must fire | Researcher→retry1→retry2→retry3, all failed downstream |
| CR2 | CascadingRetryDetector | must fire | retrieve→retry1→retry2→retry3→retry4, deep cascade |
| CR3 | CascadingRetryDetector | must NOT fire | 1 retry, immediate success |
| CR4 | CascadingRetryDetector | must NOT fire | Parallel 4 retrievals (not cascading) |
| RP1 | RecoveryPathDetector | must fire | 3 error tool calls + 7 recovery steps |
| RP2 | RecoveryPathDetector | must fire | 6 errors + 10 recovery steps |
| RP3 | RecoveryPathDetector | must NOT fire | 1 error + 1 recovery step |
| RP4 | RecoveryPathDetector | must NOT fire | 0 errors |
| IF1 | InterventionFrequencyDetector | must fire | Analyst asks for human confirmation 4x |
| IF2 | InterventionFrequencyDetector | must fire | 3 interventions in a 3-agent crew (Researcher, Analyst, Writer each ask) |
| IF3 | InterventionFrequencyDetector | must NOT fire | Fully automated, 0 interventions |
| IF4 | InterventionFrequencyDetector | must NOT fire | 2 requests for confirmation |
| ER1 | EscalationRateDetector | must fire | 3 interventions / 5 tool calls (60% ratio) |
| ER2 | EscalationRateDetector | must fire | 4 interventions / 5 tool calls (80% ratio) |
| ER3 | EscalationRateDetector | must NOT fire | 1 intervention / 20 tool calls (5% ratio) |
| ER4 | EscalationRateDetector | must NOT fire | 0 interventions |
| AP1 | ApprovalLatencyDetector | must fire | await_approval span takes 90s |
| AP2 | ApprovalLatencyDetector | must fire | await_approval span takes 200s |
| AP3 | ApprovalLatencyDetector | must NOT fire | await_approval span takes 15s |
| AP4 | ApprovalLatencyDetector | must NOT fire | No await_approval spans |
| IR1 | InterventionRejectionDetector | must fire | 2 human interventions, both rejected |
| IR2 | InterventionRejectionDetector | must fire | 3 interventions, all rejected |
| IR3 | InterventionRejectionDetector | must NOT fire | 2 interventions, both accepted |
| IR4 | InterventionRejectionDetector | must NOT fire | No human intervention spans |
| EM1 | EmptyResponseDetector | must fire | Agent returns empty string as final response |
| EM2 | EmptyResponseDetector | must fire | Agent errors mid-response, produces no output |
| EM3 | EmptyResponseDetector | must NOT fire | Normal 200-char answer |
| EM4 | EmptyResponseDetector | must NOT fire | Tool-only run with generated report |
| LO1 | LowOutputDetector | must fire | Response contains 20 characters ("Answer: yes") |
| LO2 | LowOutputDetector | must fire | Response contains 10 characters ("OK.") |
| LO3 | LowOutputDetector | must NOT fire | Response 200 characters |
| LO4 | LowOutputDetector | must NOT fire | Writer produces a 2000-word report |
| ID1 | IndeterminateDetector | must fire | Run completes with status=unknown |
| ID2 | IndeterminateDetector | must fire | Agent exits with status=None (timeout) |
| ID3 | IndeterminateDetector | must NOT fire | Run completes with status=success |
| ID4 | IndeterminateDetector | must NOT fire | Run exits with status=error |
| OD1 | OutputDriftDetector | must fire | Baseline avg output 100 chars; run output 350 chars |
| OD2 | OutputDriftDetector | must fire | Baseline avg 200 chars; run produces 1200 chars |
| OD3 | OutputDriftDetector | must NOT fire | Baseline 100 chars; run 150 chars (1.5x) |
| OD4 | OutputDriftDetector | must NOT fire | Baseline <5 runs |
| AC1 | AnomalyClusterDetector | must fire | Run triggers loop + retry_storm + cost_spike (3 types) |
| AC2 | AnomalyClusterDetector | must fire | Run triggers loop + tool_error_rate + token_explosion + empty_response |
| AC3 | AnomalyClusterDetector | must NOT fire | Run triggers only 2 anomaly types |
| AC4 | AnomalyClusterDetector | must NOT fire | Clean run, 0 anomalies |
| RF1 | RunFrequencyAnomalyDetector | must fire | Cohort average 5 runs/hour; this agent generates 20 runs |
| RF2 | RunFrequencyAnomalyDetector | must fire | Cohort avg 3 runs/hour; agent generates 15 runs (5x) |
| RF3 | RunFrequencyAnomalyDetector | must NOT fire | Cohort avg 5 runs; agent at 8 (1.6x) |
| RF4 | RunFrequencyAnomalyDetector | must NOT fire | Cohort has <5 baseline runs |
| FH1 | FirstRunHeuristicDetector | must fire | First run of agent version v2; v1 has 10 prior runs |
| FH2 | FirstRunHeuristicDetector | must fire | Aider bumped from v1.0 to v1.1; first v1.1 run |
| FH3 | FirstRunHeuristicDetector | must NOT fire | Agent v1, run# 25 of this version |
| FH4 | FirstRunHeuristicDetector | must NOT fire | Agent v2 first run, but v1 has 0 baseline runs |

**Total: 50 runnable field-test cases + 154 ported detector
scenarios = 202 cases.**
### 5c.3  Playwright E2E test cases (screenshots + acceptance + a11y)

These run as part of **FT-09** (full Playwright suite), **FT-32** (a11y subset),
and **FT-36** (screenshot capture). Specs live at `apps/web/tests/e2e/*.spec.ts`.
Every test is `pass`/`fail` — no skips.

#### `a11y.spec.ts` — WCAG 2.2 AA — automated checks

| Test |
|---|
| dashboard has no axe violations (including contrast) |
| fleet has no axe violations (including contrast) |
| run timeline has no axe violations (including contrast) |
| compare has no axe violations (including contrast) |
| anomalies has no axe violations (including contrast) |
| navigates every view and opens a run with the keyboard alone |
| activates a span in the timeline with Enter |

#### `acceptance.spec.ts` — Demo Acceptance

| Test |
|---|
| ACC-01 success and error runs distinguishable in fleet |
| ACC-02 fleet shows multiple agent names and versions |
| ACC-03 version compare shows non-zero deltas |
| ACC-04 anomaly inbox filters change visible rows |

#### `anomalies.spec.ts` — Anomaly Inbox

| Test |
|---|
| ANM-01 default list loads with anomaly items |
| ANM-02 type filter reduces to loop-only items |
| ANM-03 severity filter shows critical-only |
| ANM-04 agent filter narrows results |
| ANM-05 click-through navigates to run timeline |
| ANM-06 loading skeletons visible on slow response |
| ANM-07 error state with retry on 500 |
| ANM-08 empty filters show empty state |

#### `compare.spec.ts` — Version Compare

| Test |
|---|
| CMP-01 two versions produce non-empty deltas |
| CMP-02 version selectors are populated and functional |
| CMP-03 single version shows appropriate message, no crash |
| CMP-04 sparse cohort warning for small cohort (<5 runs) |
| CMP-05 zero-delta when comparing same version to itself |

#### `dashboard.spec.ts` — Dashboard

| Test |
|---|
| DASH-01 overview cards show non-zero aggregates |
| DASH-02 agent cards grid shows agent name, version, workload |
| DASH-03 card click navigates to fleet filtered by agent |
| DASH-04 empty state shown when fleet API returns empty |

#### `fleet.spec.ts` — Fleet Health

| Test |
|---|
| FLEET-01 default table renders with rows and columns |
| FLEET-02 agent filter narrows results to selected agent |
| FLEET-03 version filter shows only matching versions |
| FLEET-04 combined filters produce intersection subset |
| FLEET-05 empty filter result shows EmptyState |
| FLEET-06 row click navigates to run timeline |
| FLEET-07 loading skeletons visible while fetching |
| FLEET-08 error state with retry on 500 |

#### `screenshots.spec.ts` — Field-test screenshots

| Test |
|---|
| dashboard-overview |
| dashboard-to-fleet |
| fleet-default |
| anomalies-default |
| anomalies-critical |
| timeline-normal |
| timeline-spans |
| compare-deltas |

#### `timeline.spec.ts` — Run Timeline

| Test |
|---|
| TL-01 enter run ID navigates to timeline view |
| TL-02 empty spans shows placeholder text |
| TL-03 stubbed span tree with expand/collapse interaction |
| TL-04 anomaly badges shown on anomalous runs |
| TL-05 back navigation preserves context |

**Total Playwright tests: 49** (across 8 spec files; `a11y.spec.ts` generates its 5 route
checks from a `for` loop).
Screenshots are captured to `results/<run-id>/cases/FT-36/artifacts/screenshots/`
via `FT_SCREENSHOT_DIR` — one full-page PNG per view: dashboard, fleet, compare, anomalies.

---

## 11. Rollout

1. Scaffold `scripts/fieldtest/` (overlay + `lib.sh` + README) and **FT-04** as the first
   recorder smoke.
2. Add FT-01, FT-05, FT-06 (no LLM) → first real run.
3. Add FT-03, FT-07, FT-08, FT-10, then the CUJs.
4. Add FT-02 + FT-11 (OMLX) and fold `make e2e` in as FT-09.
5. **Port the predecessor set (5a):** detector matrix + `examples/demo-agent` fixtures →
   FT-15; `synthetic-llm-validation-plan` + `m13-100-trace-report` → FT-11/11b; bulk-trace generator →
   FT-06b; `m13-agents` → FT-11c/FT-29; report template → `FIELD_TEST_REPORT.md`.
6. **Add the PRD-derived tests (5b):** start with the fail-closed cluster (FT-12/13/14/16/17/18) and
   self-observability (FT-24/33), then performance/operability (FT-25/26/27) and the remainder.
7. Wire a nightly `fieldtest.yml`, publish `FIELD_TEST_REPORT.md`, close #141–#145.
