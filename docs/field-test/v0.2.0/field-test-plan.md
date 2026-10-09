# Field-Test Plan — agentwatch v0.2.0

**Milestone:** M31 Field Tests (execution) · **Authored:** M25 `25.FLD-1a` (#370), revised 2026-10-07
**Plan (this doc) →** report `docs/field-test/v0.2.0/FIELD_TEST_REPORT.md` · **Harness:** `scripts/fieldtest/` ·
**Results:** `field-test/v0.2.0/results/` · **Supersedes:** the 2026-10-05 stub in this directory.

**BLUF.** v0.1.0 field-tested the record layer and published a 50-case / 226-detector / 49-Playwright result with
evidence bundles ([v0.1.0 PLAN](../v0.1.0/field-test-plan.md), [v0.1.0 REPORT](../v0.1.0/FIELD_TEST_REPORT.md)).
v0.2.0 adds standards-native interop (AAT, OTel agent spans, W3C trace), real harness fidelity (Cursor/Gemini/Codex),
streaming, honest detector effectiveness, identity/delegation, one-command compliance, capability supply chain, code
provenance, a zero-Docker console, agent interfaces, policy-from-history, governance/retention, investigation depth,
and ephemeral capture — **CUJ-15 through CUJ-34 plus a CUJ-8 extension** (PRD 04).

This plan **extends** the v0.1.0 plan; it does not replace it. The v0.1.0 suite runs unchanged as the **regression
gate** (the record layer must not regress), and **94 new cases** are added so that **every P0 v0.2.0 feature and every
new CUJ appears in ≥1 end-to-end field case** — the field-test case is the seventh item of the v0.2.0 definition of
done (PRD 48 §5). The case roster is frozen here now so M31 execution is a matter of running, not deciding.

Sources: [PRD 40](../../prd/40-v0.2.0-program.md) §1a/§1b/§5, [PRD 04](../../prd/04-users-and-cujs.md) (CUJ-15–34),
[PRDs 41–48](../../prd/README.md), [PRDs 49–59](../../prd/README.md),
[docs/wbs/v0.2.0 Part 7](../../wbs/v0.2.0/wbs-v0.2.0-part7-field-test-release.md) (M31 work items #408–#410, #389–#395,
#488–#491), [v0.2.0-expanded execution plan](../../plans/v0.2.0-expanded-execution-plan.md) §5.

---

## 0. Readiness, doctrine, and status

### 0.1 Doctrine (inherited from v0.1.0, unchanged)

- **No skips.** Every case is `pass`/`fail`. A case that cannot run is a **failure**, not a skip, and the run exits
  non-zero. The v0.1.0 `STACK_ON_NO_DOCKER=fail` / `ft_require_docker` hard-fail discipline is preserved.
- **Boot the whole stack per case.** Each case extends `scripts/stack_lib.sh` (`stack_up`, `stack_verify`,
  `stack_teardown_on_exit`) + the recorder overlay, and verifies every container + endpoint before assertions.
- **Trust-path determinism.** No LLM in redaction, validation, or chain verification. The LLM is a **test oracle**
  only (PRD 19–30 cross-cutting rules). The v0.1.0 lesson "silent `None` is not a pass" becomes a rule: every
  LLM-backed assertion also asserts the LLM was actually called.
- **Verify the verifier.** Every case's assertions are themselves exercised against a known-bad input (a "deliberately
  broken" fixture) so a green run cannot hide an unexercised path (v0.1.0 learning #8).
- **One plan, one lifecycle primitive, layered under test.** Recorder layer (hook/SDK/ingest → store → chain → replay
  → coverage → export → evidence) and analyst layer (derived index/Postgres read-model + API + analytics + web +
  Jaeger + otel-collector) both reuse the existing primitives.

### 0.2 The "declare" class (v0.2.0 only)

Four v0.2.0 gates are explicitly worded **"verified … or declared"** (PRD 40 §5-expanded items 9, 13; PRD 50;
PRD 57 SBX-1/CNC-1). For those only, a case may resolve to **`pass`** (environment available and exercised) or
**`declared`** (environment genuinely unavailable), where `declared` requires **all** of:

1. a named limitation with a PRD reference,
2. an evidence artifact showing the failed/blocked attempt (`commands.log` + `stderr.log` + environment fingerprint),
3. a new line in `reference/known-limitations.md` **with its proving test** (its own policy), and
4. the corresponding release-gate item is the one that permits "declared".

`declared` is **not** allowed for any hard gate. The `declare` class is fixed in the roster below (`Class` column:
`P/F` = must pass/fail; `P/F|D` = pass or named declaration). A `declared` case **fails the suite** unless the
release gate for that item explicitly allows it, so the run stays honest.

### 0.3 Status at authoring (2026-10-07)

M25–M29 are complete on `feat-v0.2.0` (index progress block); M30 (code/capabilities/console/investigation) is in
progress; M31 (this plan's execution) and M32 (release) are not started. The plan below therefore names the owning
ticket for every case, so a case whose feature has not landed is visibly "blocked on ticket X", not silently absent.

| Item | Status |
|---|---|
| v0.1.0 regression suite (50 cases / 226 detectors / 49 Playwright) | ✅ available |
| Harness overlay + `lib.sh` + runners + `collect-results.py` | ✅ available |
| New environment topologies (fleet 3-host, A2A, gateway, runner, Windows, managed-policy) | ☐ to add (M31.1/31.4) |
| New fixtures (golden corpora, hostile set, AAT vectors, capability/memory, provenance repo) | ☐ to add (M31.2/31.3) |
| New case specs + registry entries (94 cases) | ☐ to add (M31.3) |
| New runners (per-suite) | ☐ to add (M31.4) |

**Overall status: READY TO BUILD THE HARNESS.** The roster is frozen; execution is M31.

---

## 1. What v0.1.0 already gives us (reuse as-is — do not fork)

| Asset | Role in the v0.2.0 plan |
|---|---|
| `scripts/fieldtest/lib.sh`, `run-case.sh`, `run-all.sh`, `collect-results.py`, `gen_cases.py`, `cases/registry.json` | case lifecycle, generated specs/steps, aggregation — **extended**, not replaced |
| `scripts/fieldtest/emit-hook.py`, `seed-fixtures.py`, `run-soak.py`, `drive-agent.py`, `otel-probe.py`, `corpus.sh`, `llm-validation.sh` | hook/OMLX/soak/OTLP/corpus drivers |
| `scripts/stack_lib.sh`, `docker-compose.fieldtest.yml`, `recorder.Dockerfile` | lifecycle, overlay, recorder image |
| `scripts/offline_e2e.py`, `first_run_timing.py`, `soak.py`, `perf_gate.py`, `export-e2e-data.py`, `reload-e2e-data.py` | offline/timing/soak/perf/seed primitives |
| `apps/web/tests/e2e/*.spec.ts`, `playwright.config.ts`, `screenshots.spec.ts` | analyst UI + screenshots |
| The 50 v0.1.0 case specs + the 226-scenario detector matrix + report template | the **baseline regression suite** and report structure |
| `examples/demo-agent/fixtures/{normal,loop,high_cost}.json`, `m13-agents/` | deterministic detector + cross-framework inputs |

**Do not create a parallel harness.** New cases source the same `lib.sh` / `stack_lib.sh` and reuse the seed, timing,
soak, and offline primitives.

---

## 2. What v0.2.0 must additionally prove (the gap this plan closes)

The v0.1.0 report's Deferred table explicitly left these for v0.2.0, and PRD 40 §5/§5-expanded turns them into gates:

- **Closed "partial" gates** — R2 clean-OS first-run timing (3 OSes) and R4 a second live OTLP backend.
- **Standards** — AAT export accepted by a third party (CUJ-15); OTel agent spans in ≥2 backends; OTLP/gRPC.
- **Real-time** — streaming p99 hook→view ≤1 s with classified reconciliation (CUJ-17).
- **Distributed attribution** — one causal chain across agents/hosts + identity/delegation (CUJ-16).
- **Detector honesty** — published numbers reproduced on a **second** corpus (CUJ-19); ≥80% rule detectors non-silent.
- **Compliance** — offline report, every row regenerable (CUJ-18); AAT/retention/signing posture.
- **Fidelity** — no "modeled" Tier-1 rows; Cursor/Gemini/Codex real captures or declared tiers (CUJ-1/13/20).
- **Trust in the operator** — approval v2 never records classifier/bypass as `user` (CUJ-21); recorder attestation.
- **Artifact boundaries** — `suggest-policy`/`what-if` write nothing outside `--out` (CUJ-27); ASI rows all run
  (CUJ-18 ext); held records survive retention/purge/rebuild (CUJ-32); read-only MCP safe (CUJ-26); runner segment
  distinguishes imported from locally-witnessed (CUJ-30).

---

## 3. Topology (extends §3 of the v0.1.0 plan)

Base `docker-compose.yml` is unchanged; the v0.1.0 overlay gains new services:

| Service / env | Role | Added by | Notes |
|---|---|---|---|
| `recorder` / `agent` / `llm` / `verifier` | system under test, traffic, OMLX, clean auditor | v0.1.0 | unchanged |
| `jaeger`, `otel-collector`, `postgres`, `api`, `analytics`, `web`, `tempo` | analyst tier | base | unchanged; `tempo` active as the **second live OTLP backend** (closes R4) |
| `otel-grpc` receive path | OTLP/gRPC + protobuf ingest | OTEL-3 | new listener; 100 MB streaming fixture |
| `fleet-h1` / `fleet-h2` / `fleet-h3` | 3 hosts × 3 harnesses for trace correlation | TRACE-1/2, IDN | separate containers + network namespaces; opt-in fleet |
| `a2a-proxy` | A2A interposition | A2A-1/2 | records both directions; card verification outcome recorded |
| `litellm` (fixture) | gateway OTel source | GWY-1/2 | exact vs estimated cost |
| `runner` | ephemeral CI/cloud capture (no daemon home) | RUN-1 | sealed segment export/import |
| `managed-hooks` profile | `allowManagedHooksOnly` / `strictPluginOnlyCustomization` fixture | DEP-1/2 | simulated managed config; real MDM where available |
| `windows-latest` CI leg | Windows daemon/service + named pipe | WIN-1 | GitHub Actions, not Compose |
| static browser verifier | `file://` page, zero network | VFY-1 | released static artifact, not a service |

**Boot:** append the needed services to `STACK_SERVICES`, then
`docker compose -f docker-compose.yml -f scripts/fieldtest/docker-compose.fieldtest.yml up -d`, exactly as v0.1.0.
Windows and managed-policy cases run outside Compose and carry their own environment fingerprint.

---

## 4. Local models (OMLX) — unchanged pins

All LLM-backed cases continue to use the on-box OMLX (OpenAI-compatible) with the v0.1.0 pins; no case calls a hosted
model. CCO-1/GEM-1/COD-1/GWY cases use **recorded telemetry fixtures**, not live models (deterministic).

| Role | Model | Used by |
|---|---|---|
| Primary | `Qwen3-4B-Instruct-2507-4bit` | LLM-backed recorder/detector cases |
| Ablation | `Qwen3.5-9B-MLX-4bit` | detector 4B-vs-9B comparison |
| No-LLM baseline | — | all rule-based and fixture cases |

Endpoint/model are asserted into `env.json`; `temperature=0`, `enable_thinking=false`. If OMLX is unreachable, the
deterministic fallback runs and the case still asserts on recorder/detector evidence — a fallback is not a skip. **New
rule from v0.1.0 learning #1:** every LLM-backed assertion also asserts `llm_called_ok = (llm_calls + embed_calls) > 0`.

---

## 5. Layer 0 — the v0.1.0 regression gate (mandatory, unchanged)

v0.2.0 must not regress the record layer. The **entire v0.1.0 suite runs first** in every M31 full run:

| Regression block | Count | Source |
|---|---|---|
| v0.1.0 field cases (`FT-01…FT-36`, `CUJ-08…14`) | 50 | [`../v0.1.0/field-test-plan.md`](../v0.1.0/field-test-plan.md) |
| Detector scenarios (35 rule + Claude Code + LLM + boundary) | 226 | `scripts/fieldtest/cases/FT-15` |
| Playwright UI tests + a11y + screenshots | 49 | `apps/web/tests/e2e/*.spec.ts` |

**Pass condition:** 50/50 · 226/226 · 49/49, zero skips, before any v0.2.0 case is evaluated. A v0.1.0 regression is a
**release blocker**, and any defect it exposes is fixed with its own regression test (M31 31.7).

### 5a. v0.1.0 case parity & disposition matrix

Nothing from v0.1.0 disappears silently. **Unchanged features keep their original case as-is**; changed features keep
it **plus** a v0.2.0 companion; superseded cases name their replacement.

**Group A — unchanged, original case retained as-is (19):** FT-05, FT-06, FT-06b, FT-09, FT-10, FT-11, FT-12,
FT-13, FT-14, FT-15b, FT-15c, FT-16, FT-18, FT-20b, FT-23, FT-26, FT-28, FT-30, FT-32.

**Group B — extended, original case kept + a v0.2.0 companion:**

| v0.1.0 case | v0.2.0 companion |
|---|---|
| FT-01 | FT-ENV-0, FT-DEP-1, FT-WIN-1 |
| FT-02 | FT-APV-3, FT-CAP-2, FT-ENV-1 |
| FT-03 | FT-OTEL-1/2/4, FT-BACKEND-2 |
| FT-04 | FT-RED-1, FT-OTEL-3, FT-PRV-3, FT-GEM-1, FT-CCO-1 |
| FT-07 | FT-DEMO-1 |
| FT-08 | FT-CMP-2, FT-CMP-3 |
| FT-11b | FT-DET-4, FT-DET-6 |
| FT-11c | FT-XHT-2, FT-FWK-1, FT-LG-1 |
| FT-11d | FT-COR-1 |
| FT-15 | FT-DET-6, FT-DET-7 |
| FT-17 | FT-AAT-2, FT-OTEL-2, FT-COD-1, FT-MCP-2 |
| FT-19 | FT-SIEM-1 |
| FT-20 | FT-SIEM-1, FT-DET-5 |
| FT-22 | FT-TRACE-2 |
| FT-24 | FT-CMP-3, FT-DEP-2, FT-STR-2 |
| FT-27 | FT-WIN-1 |
| FT-29 | FT-XHT-1..4, FT-MATRIX-1 |
| FT-31 | FT-ACC-1, FT-WIN-1 |
| FT-33 | FT-DET-5, FT-SIEM-1, FT-STR-2 |
| FT-34 | FT-GWY-1, FT-CCO-1, FT-OUT-1 |
| FT-35 | FT-PRV-3, FT-OTEL-4 |
| FT-36 | report / console screenshots |
| CUJ-08 | FT-VFY-1, FT-IR-1, FT-COR-2 |
| CUJ-09 | FT-DEP-2, FT-CLAIM-1 |
| CUJ-10 | FT-GWY-1, FT-CCO-1, FT-OUT-1 |
| CUJ-11 | FT-SDK-1, FT-LG-1, FT-FWK-1/2, FT-TSS-1, FT-PG-3 |
| CUJ-12 | FT-HLD-1 |
| CUJ-13 | FT-MCP-1/2, FT-CAP-1 |
| CUJ-14 | FT-APV-1/2/3, FT-CCO-1, FT-GEM-1, FT-CCA-1 |

**Group C — superseded, never dropped:** FT-01b → FT-ENV-0 (same proof, now on 3 OSes, closes R2); FT-25 →
in-process latency stays under the perf gate, user-visible wall-clock moves to FT-DEP-3.

**v0.1.0 deferred → closed here:** R2 → FT-ENV-0; R4 → FT-OTEL-1 + FT-BACKEND-2; live OCSF/Syslog reference
consumers → FT-SIEM-1; real authenticated captures → FT-STR-1, FT-APV-1, FT-CCO-1, FT-SBX-1, FT-CUR-1 (Cursor).

### 5b. Playwright UI coverage — analyst web + local console

Two browser UIs are exercised by Playwright; both recapture screenshots for v0.2.0.

- **Analyst web UI** — `apps/web/tests/e2e/*.spec.ts` (dashboard, fleet, timeline, anomalies, compare, a11y,
  acceptance, screenshots). `screenshots.spec.ts` recaptures the 8 user-guide images into `docs/assets/screenshots/`
  via `FT_SCREENSHOT_DIR`. Runs in the Layer-0 regression block and again at M31 (FT-36 / `make e2e`); the suite
  count is reconciled against the "49" the plan claims (a count discrepancy is recorded in the report, not waived).
- **Local console** (`agentwatch ui`, FT-LUI-1/2; PRD 54, CUJ-24) — **gap closed in v0.2.0.** The console is a
  Python-served loopback UI (`packages/python-sdk/src/agentwatch/ui.py`) with no browser test of its own; its only
  prior evidence was `ui --check` plus axe-under-jsdom (no real browser). v0.2.0 adds
  `apps/web/tests/e2e/console.spec.ts` — screenshots of the console views (`#health`/`#sessions`/`#signatures`) and a
  real-browser axe gate — run against a live console (`FT_CONSOLE_URL`, started by the LUI driver).

**Pass condition:** analyst-web Playwright green (`passed/total` recorded), the 8 guide PNGs refreshed, and the
console spec green (screenshots captured, **0 serious/critical axe violations**, UI == CLI `--json`). A missing
console spec is a gap to close, never a silent skip.

---

## 6. Master scenario matrix — 94 new cases

`Class`: **P/F** = must pass or fail (no declaration). **P/F|D** = pass, or declared with a named limitation (only
where the release gate says "or declared"). `Env` keys: mac=local-macos, lin=local-linux, ci=ci-hermetic, cm=clean
machine, fleet=3-host, win=Windows CI, mgd=managed-policy.

### S1 — Fresh install, deployability & recorder attestation (M31.1, M29; CUJ-1/25)

| ID | Capability | PRD/ticket | CUJ | Env | Driver | Pass condition | Class |
|---|---|---|---|---|---|---|---|
| FT-ENV-0 | Fresh install → first record, **≤15 min on 3 OSes** (closes R2) | EXT-10, 13 NFR-4, 46 WIN-1, 25 NAM-1 | 1,25 | cm | `first_run_timing.py` | ≤15 min each of macOS/Linux/Windows; zero agent-code change; record+verify green | P/F |
| FT-WIN-1 | Windows support (named-pipe daemon + service) | WIN-1 | 1 | win | Windows CI leg | hooks+daemon+store+verify+replay green; matrix row `live-verified` | P/F\|D |
| FT-DEP-1 | Managed-policy environment, honest `doctor` | DEP-1 | 25 | mgd | managed config | `doctor` says "hooks effective: yes/blocked/unknown", **never** "installed" when blocked; recipe works or limitation named | P/F\|D |
| FT-DEP-2 | Hook-strip → `recorder-config-changed` + gap | DEP-2 | 25 | mac | strip hooks | Next session raises `recorder-config-changed`; unattested interval classified; attestation digest/booleans only | P/F |
| FT-DEP-3 | End-to-end hook wall-clock per OS + budget gate | DEP-3 | 1,25 | mac,lin,win | perf gate | p50/p99 published; budget "< X ms/tool call p99" enforced; 500-call figure quoted | P/F\|D |

### S2 — Standards & interop II (M25–M26; PRD 41; CUJ-15/16)

| ID | Capability | PRD/ticket | CUJ | Env | Driver | Pass condition | Class |
|---|---|---|---|---|---|---|---|
| FT-AAT-1 | AAT export → **third-party** consumer round-trip | AAT-1/2/4 | 15 | ci | external AAT consumer | Bundle validates against AAT fixtures; external tool round-trips; `unmapped` explicit, never invented | P/F |
| FT-AAT-2 | Foreign AAT ingest + quarantine | AAT-3 | — | ci | synthetic bundle | Lossless-or-explicit ingest; non-normalizable records quarantined with reason; chain intact | P/F |
| FT-AAT-3 | AAT draft pin + drift check | AAT-5 | — | ci | simulated draft bump | Drift job fails on a simulated field change; pinned revision cited in `--version`/export | P/F |
| FT-OTEL-1 | Canonical OTel **agent-span** conformance in ≥2 backends | OTEL-1 | 3 ext | ci | Jaeger + Tempo | Agent-span trees render in both; semconv pin + operation alignment carried | P/F |
| FT-OTEL-2 | OTLP/gRPC + protobuf, streaming | OTEL-3 | 3 ext | ci | gRPC fixture | 100 MB ingest within memory bound; no whole-document load; records validate | P/F |
| FT-OTEL-3 | Privacy-mode ↔ content-capture mapping | OTEL-2 | 3 ext | ci | property test | metadata-only by default; no content leaks on export across modes | P/F |
| FT-OTEL-4 | Skill / command-execution agent-span mapping | OTEL-4 | 3 ext | ci | SDK corpus + property test | Spans mapped where a harness exposes them; a non-exposing harness carries a **declared gap**, never invented spans | P/F\|D |
| FT-TRACE-1 | One causal chain across 3 hosts × 3 harnesses | TRACE-1/2 | 16 | fleet | 3-host scenario | One ordered chain; broker gap classified (never absorbed); `trace <tid>` correct | P/F |
| FT-TRACE-2 | Cross-host clock skew ordering | TRACE-2, F9 | 16 | fleet | skewed clocks | Documented ordering rules; skew bounded/flagged; propagation break classified | P/F |
| FT-PG-1 | Drop-Postgres mode + bit-for-bit rebuild | PG-1 (phased) | 11 | ci | rebuild | All commands work with PG down; `--rebuild` reproduces index bit-for-bit | P/F\|D |
| FT-PG-2 | Cross-tenant isolation + audit | PG-2 (phased) | 11 | ci | 2 tenants | Cross-tenant query returns nothing and is `store-access`-recorded | P/F\|D |
| FT-PG-3 | SDK spans in the unified store, chain-protected | PG-3 (phased) | 11 | ci | SDK emit | SDK spans land chain-protected; `union` remains the no-PG fallback; integrity distinction visible | P/F\|D |

### S3 — Harness fidelity, real-time & cross-harness test kit (M25–M27; PRD 42/47; CUJ-1/13/17)

| ID | Capability | PRD/ticket | CUJ | Env | Driver | Pass condition | Class |
|---|---|---|---|---|---|---|---|
| FT-CUR-1 | Cursor full-fidelity golden-corpus audit | CUR-1/3 | 1 | mac | golden corpus | Version-tagged fixtures replay green; reads/reasoning step types; coverage reconciliation vs transcript | P/F\|D |
| FT-CUR-2 | Cursor blocking events + IDE/CLI/remote | CUR-2 | 1 | mac | fixture matrix | Blocking events recorded as observations, never answered; env variants tagged `ide` | P/F |
| FT-GEM-1 | Gemini native-OTel ingest + `logPrompts` redaction | GEM-1/2 | 1,14 | ci | captured telemetry | Ingest→validated records; `active_approval_mode`→approval; `user.email`→hashed principal; redaction runs | P/F |
| FT-COD-1 | Codex rollout reader (dedup, `.zst`, dangling) | COD-1 | 1 | ci | rollout fixtures | Fixture-verified; dedup; `crashed/inferred` end-state; weaponized `.zst` contained | P/F |
| FT-MCP-1 | MCP full surface across 3 protocol revisions | MCP-1..6 | 13 | ci | MCP fixtures | `resources/read`(+links), `prompts/get`, elicitation, `tasks/*` recorded; Streamable HTTP default | P/F |
| FT-MCP-2 | Closed-by-spec surfaces + malformed frames | MCP-5, B4 | 13 | ci | fixtures | sampling/roots/logging marked closed-by-spec; unknown method quarantined with reason | P/F |
| FT-LOG-1 | Long-tail coding-agent log readers, `log-read` tier | LOG-1 | 1 | ci | per-agent fixtures | Each reader fixture-verified; `log-read` fidelity label; no shell execution on ingest | P/F |
| FT-STR-1 | Live view p99 ≤ 1 s | STR-1/2 | 17 | mac | claude-code + daemon | hook→view p99 ≤1 s; anomalies land in live inbox | P/F |
| FT-STR-2 | Drop-consumer reconciliation + 24 h soak | STR-2/3 | 17 | lin | streaming soak | No store loss on consumer crash; back-fill reconciles; every gap classified | P/F |
| FT-LG-1 | LangGraph + raw-Python Tier-2 at full fidelity | LG-1/2 | 11 | ci | framework run | One command instruments a LangGraph app; spans chain-protected; conformance pack green | P/F |
| FT-XHT-1 | Payload corpus replay + self-test | XHT-1 | 1,19 | ci | replay runner | Every registered adapter ≥N fixtures; a deliberately broken adapter **fails** | P/F |
| FT-XHT-2 | Live soak on OpenCode (real agent) | XHT-2 | 1,17 | ci | OpenCode | 24 h soak green; matrix row gains `live-verified`; discovered quirk feeds a fixture | P/F\|D |
| FT-XHT-3 | Cross-validate vs 2 independent OSS parsers | XHT-3 | 1 | ci | golden corpus | Normalized diff within tolerance or documented interpretation gap; divergence fails | P/F |
| FT-XHT-4 | Honest fidelity tiers in the generated matrix | XHT-4 | — | ci | matrix generator | Emits `live-verified\|fixture-verified\|modeled`; no "modeled" Tier-1 row survives (PRD 40 §5.3) | P/F |

### S4 — Detector credibility, corpus & redaction quality (M25–M30; PRD 43/56)

| ID | Capability | PRD/ticket | CUJ | Env | Driver | Pass condition | Class |
|---|---|---|---|---|---|---|---|
| FT-DET-1 | One-command deterministic detector eval | DET-1/2 | 19 | ci | `detectors eval` | Deterministic, offline; reproduces the published per-detector numbers | P/F |
| FT-DET-2 | ≥80% of rule detectors non-silent; catalog CI-guard | DET-3 | 19 | ci | catalog | ≥80% non-silent on the public corpus; a detector without a catalog entry fails CI | P/F |
| FT-DET-3 | LLM detectors in the same harness | DET-4 | 19 | mac | OMLX | LLM detectors run under the harness; `llm_called_ok` on every scenario | P/F |
| FT-DET-4 | Injection + memory-surface observations | DET-6/7 | 8 ext | ci | injection corpus | Observations fire with published precision/recall; signals only, never verdicts; high-FP rules off by default | P/F |
| FT-DET-5 | Detector telemetry (SIEM-feedable, content-free) | DET-5 | 19 | ci | `detector status` | Off by default; fired/suppressed/false-positive markers are content-free, bounded, NDJSON, feedable to a SIEM | P/F |
| FT-DET-6 | New-class scenario depth (injection/memory/credentials/sandbox) | DET-6 | 19 | ci | scenario matrix | Positive/negative/boundary scenarios per class per harness; per-harness numbers published in the catalog | P/F |
| FT-DET-7 | Real-harness trace replay (not fixtures alone) | DET-7 | 19 | ci | real testkit traces | Detectors fire measurably on real Claude Code / Cursor / Codex traces; the non-silent claim rests on measured firing | P/F |
| FT-COR-1 | Public corpus + **second-corpus** reproduction | COR-1 (31.10) | 19 | ci | corpus v1 | Local numbers match published within stated bounds; corpus/method/CIs cited | P/F |
| FT-COR-2 | Incident-registry export (COR-2/3) | COR-2/3 | 8 ext | ci | AIR-shaped export | Export validates against schema fixture; **no auto-submission path exists** (test) | P/F |
| FT-RED-1 | Redaction quality benchmark | RED-1 | — | ci | redaction corpus | Per-class recall/FP reproduced deterministically; misses listed in known-limitations | P/F |

### S5 — Identity, compliance & SIEM (M25–M29; PRD 44/59; CUJ-16/18)

| ID | Capability | PRD/ticket | CUJ | Env | Driver | Pass condition | Class |
|---|---|---|---|---|---|---|---|
| FT-IDN-1 | Attribution end-to-end in one command | IDN-1..4 | 16 | fleet | multi-agent fixture | `impact`/`blame`/`tree`/`trace` answer identity+delegation or honest `unknown`, never inferred | P/F |
| FT-IDN-2 | Identity fields never contain secret material | IDN-1, DD-06 | — | ci | property test | Hashed by default in metadata-only; secret-material property test passes | P/F |
| FT-IDN-3 | Ambient / shared credential hygiene observation | IDN-3, DD-07 | 16 ext | ci | credential fixture corpus | `credential_class: ambient/shared` fires with published precision/recall; an observation, never a verdict; AIMS/WIMSE mapping cited | P/F |
| FT-CMP-1 | One-command **offline** compliance report | CMP-1/2 | 18 | ci | `compliance report` | Every row regenerable from its cited command; zero unverifiable claims; offline/air-gapped | P/F |
| FT-CMP-2 | Retention profiles + signed default posture | CMP-3/4 | 18 | ci | retention+sign | Signed default verify succeeds; unverifiable is never "ok"; missing key names key id + epoch | P/F |
| FT-CMP-3 | All five compliance templates + key rotation | CMP-3/4 | 18 | ci | rotate + verify | All templates run offline; rotation appends a metadata-only `key-rotation` chain event; missing-epoch verdict is exactly "signed by key id X, key unavailable" | P/F |
| FT-SIEM-1 | OCSF 1.5.0 + Syslog event stream | SIEM-1/2 | 18,16 | ci | reference consumers | Conformance-tested (Splunk/Sentinel/Exabeam-shaped); redaction gate blocks an unconfigured sink; `degraded` on failure | P/F |
| FT-ASI-1 | OWASP ASI-2026 + AST10 report | ASI-1 | 18 ext | ci | `compliance report` | All ten ASI rows + AST10 present; **every row's command runs**; nothing claims prevention | P/F |

### S6 — New capture surfaces (M26–M29; PRD 45; CUJ-10/20)

| ID | Capability | PRD/ticket | CUJ | Env | Driver | Pass condition | Class |
|---|---|---|---|---|---|---|---|
| FT-A2A-1 | Cross-org delegation provable | A2A-1/2 | 20 | ci | A2A proxy | Task lifecycle + signed-card provenance recorded; **unverified cards recorded unverified**, never trusted as authorization | P/F |
| FT-GWY-1 | Gateway OTel ingest + exact vs estimated cost | GWY-1/2 | 10 | ci | LiteLLM fixture | Recipe green; `cost` distinguishes exact vs estimated, source-stamped per record | P/F |
| FT-SYS-1 | System-effects ingest join (Linux, opt-in) | SYS-1 | 8 ext | lin | AgentSight-shaped stream | Synthetic process tree joins its session; `source: system-ingest` label; false-join precision published; macOS/Win not-covered stated | P/F\|D |
| FT-CCA-1 | Claude Compliance API ingest (consent-first) | CCA-1 | 14 | ci | compliance fixture | Consent gating; pull recorded as `store-access`; feed-vs-hook discrepancy classified; credentials never stored | P/F |
| FT-ACS-1 | ACS Guardian audit-trail ingest (watch) | ACS-1 | 8 ext | ci | ACS fixture | Fixture stream ingests + chains with `record_phase: pre_execution`; **no decision executes** | P/F\|D |

### S7 — Platform, SDK, agent interfaces & policy (M25–M30; PRD 46/51/55; CUJ-26/27/28)

| ID | Capability | PRD/ticket | CUJ | Env | Driver | Pass condition | Class |
|---|---|---|---|---|---|---|---|
| FT-SDK-1 | Flush-on-exit, sampler determinism, no-op after shutdown | SDK-1..3 | 11 | ci | crash/exit tests | Records not lost on exit; sampler deterministic (same session→same decisions); valid no-op after shutdown; concurrency safe | P/F |
| FT-API-1 | OpenAPI publication + typed client drift | API-1 | 4,18 | ci | generated client | `openapi.json` present; contract test fails on live-app drift | P/F |
| FT-EXA-1 | Examples gallery recipes | EXA-1 | 3,15 | ci | recipes | Every recipe green in CI or explicitly illustrative; no secrets in recipes | P/F |
| FT-GOV-1 | Community plugin API + codemod | GOV-1 | 1 | ci | codemod | Codemod tested against migration examples; plugin without a conformance registration fails CI | P/F |
| FT-AGI-1 | Read-only MCP server safety | AGI-1 | 26 | ci | MCP server | Tool enumeration proves **no write tool**; injection fuzz holds; every query `store-access`-recorded; off by default | P/F |
| FT-AGI-2 | Investigation skill + versioned CLI JSON | AGI-2 | 26 | ci | scripted agent | Skill reaches documented answers on the demo store; CLI JSON schemas published + changelog-guarded | P/F |
| FT-POL-1 | `suggest-policy` + broad-rule lint | POL-1/2 | 27 | ci | local corpus | **No write outside `--out`**; broad-rule lint flags wildcard exec/network; destructive never allow-by-default; deterministic | P/F |
| FT-FWK-1 | Certified framework recipes (ADK/Strands/OpenAI/Claude SDK) | FWK-1 | 28 | ci | pinned frameworks | Each recipe runs in CI against a pinned version; ≤2 lines/1 config block; `unmapped` explicit; `source`+integrity carried | P/F\|D |
| FT-FWK-2 | `instrument()` auto-detect | FWK-2 | 28 | ci | local frameworks | Prints detected frameworks + gaps (no silent partial); no-op safe; flush-on-exit; idempotent | P/F |
| FT-CCO-1 | Claude Code native-OTel ingest + `tool_use_id` join | CCO-1 | 21 | mac | captured OTel | ≥95% join; hook-only/otel-only/discrepancies classified; exact vs estimated cost source-stamped; redaction on ingest | P/F |
| FT-CCO-2 | Claude Agent SDK / headless via same path | CCO-2 | 28 | ci | SDK run | Telemetry lands as `source: sdk-native` with identity from resource attributes; gallery example runs | P/F |
| FT-TSS-1 | TS-SDK span-taxonomy spike | TSS-1 (PRD 46) | — | spike | spike report | Taxonomy derived from observed spans, not taxonomy-first; findings land as new M31 tickets; nothing in production depends on the spike | P/F\|D |

### S8 — Authorization & oversight provenance (M29; PRD 49; CUJ-21)

| ID | Capability | PRD/ticket | CUJ | Env | Driver | Pass condition | Class |
|---|---|---|---|---|---|---|---|
| FT-APV-1 | Classifier/bypass/user fidelity | APV-1 | 21 | mac | claude-code fixture | Every call's authorization correct; **none misreported as `user`**; indeterminate → `unknown` with a reason; never inferred from `outcome=ok` | P/F |
| FT-APV-2 | Oversight report on corpus | APV-3 (31.11) | 21 | ci | local corpus | Offline, version-stamped; cross-tab matches hand-computed totals; latency only when both timestamps exist | P/F |
| FT-APV-3 | Permission-mode per call + transitions | APV-2 | 21 | ci | mode-transition fixture | default→bypass→default reconstructs; bypass interval flagged in `impact`; missing mode → `unknown`, counted in coverage | P/F |

### S9 — Capability supply chain & memory (M30; PRD 52; CUJ-23)

| ID | Capability | PRD/ticket | CUJ | Env | Driver | Pass condition | Class |
|---|---|---|---|---|---|---|---|
| FT-CAP-1 | Plugin4Shell-shape drift | CAP-1/2 (31.12) | 23 | mac | capabilities | One command lists active capabilities with scope+digest; "**content changed, version unchanged**" is a distinct class; digests never content | P/F |
| FT-CAP-2 | Capability load attribution | CAP-3 | 23 | mac | session | `replay` shows loads inline; `impact` lists loaded capabilities; wording "followed the load of", never "caused" | P/F |
| FT-MEM-1 | Out-of-band memory edit | MEM-1 (31.12) | 23 | mac | memory store | Memory change not attributable to any session flagged as such; per-harness exposure matrix honest | P/F |

### S10 — Code provenance & attribution (M30; PRD 53; CUJ-22)

| ID | Capability | PRD/ticket | CUJ | Env | Driver | Pass condition | Class |
|---|---|---|---|---|---|---|---|
| FT-PRV-1 | Commit → session | PRV-1 (31.12) | 22 | mac | git repo | Commit resolves to its session in <2 s; no-activity says so (not "human"); hand-edited ranges `mixed`; gaps flagged | P/F |
| FT-PRV-2 | Agent Trace export + content-free ranges | PRV-2/3 | 22 | ci | git repo | Export validates vs pinned schema revision; **contains no code content**; redaction attack pack passes; write-to-repo only by explicit command | P/F |
| FT-PRV-3 | Range + content-hash capture under every privacy mode | PRV-2 | 22 | ci | property test + attack pack | Ranges + hashes exist under `metadata-only` too; **no content/diff text anywhere**; unsupported edit tools declare the file-level `heuristic` fallback; cost inside the DEP-3 budget | P/F |

### S11 — Local console & embedded query tier (M30; PRD 54; CUJ-24)

| ID | Capability | PRD/ticket | CUJ | Env | Driver | Pass condition | Class |
|---|---|---|---|---|---|---|---|
| FT-LUI-1 | Clean-machine console ≤60 s, no Docker | LUI-1 (31.13) | 24 | cm | `agentwatch ui` | Browser view ≤60 s from `ui`; loopback+token; read-only; zero egress; **UI numbers == CLI `--json`**; axe passes | P/F |
| FT-LUI-2 | Embedded index rebuildable / deletable | LUI-2 | 24 | ci | 1M-record store | Delete index → commands still work + rebuild bit-for-bit; targets met in `performance.md`; purge/retention propagate | P/F |

### S12 — Governance, retention integrity (M29; PRD 56; CUJ-31/32)

| ID | Capability | PRD/ticket | CUJ | Env | Driver | Pass condition | Class |
|---|---|---|---|---|---|---|---|
| FT-ACC-1 | Role × data-class matrix + access log | ACC-1 (31.14) | 31 | fleet | role matrix | Cross-role read returns **nothing** and is recorded; user sees who accessed their records; default fleet profile least-privileged | P/F |
| FT-ACC-2 | Notice + DPIA from effective config | ACC-2 | 31 | ci | `governance notice` | Every statement maps to a config key/guarantee; unbackable statements omitted and listed; "not legal advice" banner | P/F |
| FT-HLD-1 | Legal hold vs retention/purge/rebuild | HLD-1 (31.14) | 32 | ci | hold | Held records survive retention+purge+index rebuild; `purge` fails closed with the hold ref; override requires reason and is conspicuous | P/F |

### S13 — Investigation depth & evidence verification (M30; PRD 57; CUJ-33/34, CUJ-8 ext)

| ID | Capability | PRD/ticket | CUJ | Env | Driver | Pass condition | Class |
|---|---|---|---|---|---|---|---|
| FT-ENV-1 | Seeded model-version change | ENV-1 (31.14) | 33 | ci | env fingerprint | Environment delta surfaces above behavior delta; `drift` annotates "coincides with"; names/versions/digests only; absent → `unknown` | P/F |
| FT-VFY-1 | Browser verifier parity (offline) | VFY-1 (31.14) | 8 ext | ci | static page | Opens from `file://`, **zero network requests**; verdicts equal CLI on the whole fixture set; tampered bundle names the first broken link | P/F |
| FT-IR-1 | Multi-session incident case | IR-1 (31.14) | 34 | ci | case bundle | `case create/add/show/export`; merged timeline with ordering rules + classified gaps; bundle verifies offline; no registry egress | P/F |
| FT-CNC-1 | Concurrency report + `ambiguous` | CNC-1 | — | ci | overlap fixture | Two-session overlap reported; `provenance` marks multi-session ranges `ambiguous` (demand validated in field test) | P/F\|D |
| FT-SBX-1 | Sandbox-boundary events | SBX-1 | 21 ext | mac | claude-code | `oversight` shows "% calls unsandboxed" + denial counts by class; `impact` separates attempted-blocked from contacted; harness exposing none says so | P/F\|D |

### S14 — Outcomes, ephemeral capture & growth (M30/v0.2.x; PRD 58; CUJ-29/30)

| ID | Capability | PRD/ticket | CUJ | Env | Driver | Pass condition | Class |
|---|---|---|---|---|---|---|---|
| FT-OUT-1 | Outcome facts + cost per retained change | OUT-1 | 29 | ci | local corpus | `outcomes` shows numerator/denominator + derivation version; `cost --per retained-change` source-stamped; network-disabled determinism | P/F\|D |
| FT-OUT-2 | Recurring failure signatures | OUT-2 | 29 | ci | `digest` | Top-N patterns with counts/first-last seen/example sessions; grouping rules versioned; each links to replay/diff | P/F\|D |
| FT-RUN-1 | Sealed runner segment | RUN-1 (31.14) | 30 | ci | runner container | CI records → sealed segment; `import-segment` verifies+anchors; tampered segment fails; **imported visibly weaker than locally witnessed** | P/F |
| FT-DEMO-1 | Static synthetic demo bundle | DEMO-1 | — | ci | VFY-1 page | Opens offline, zero network; synthetic + secret-scanned; linked from README/GTM | P/F\|D |
| FT-NTF-1 | Alert-routing recipes | NTF-1 | — | ci | recipes | Three CI-tested recipes (Alertmanager/Grafana/Slack/PagerDuty shape); docs state routing lives in the user's stack | P/F\|D |

### S15 — Hostile data, claims ledger & closed partial gates (PRD 48, 40 §5)

| ID | Capability | PRD/ticket | CUJ | Env | Driver | Pass condition | Class |
|---|---|---|---|---|---|---|---|
| FT-HOSTILE-1 | Weaponized ingest containment | R5, ADR-0024, RSK-1 | — | ci | hostile fixtures | Codex #36937 backtick payload (and AAT/Cursor/OTel/A2A/gateway fuzz) **never executed**; quarantined; parsers fuzz-clean | P/F |
| FT-CLAIM-1 | Claims ledger green + limitations shrink | PRD 48 §5, G1/G2/G4/G7/G8 | — | ci | ledger + limitations | Every published number has a ledger entry; G1/G2/G4/G7/G8 leave with proving tests; no unresolved claim | P/F |
| FT-MATRIX-1 | Compatibility matrix honest tiers | XHT-4, PRD 40 §5.3 | — | ci | matrix | No "modeled" Tier-1 row; every row carries `live-verified\|fixture-verified` with corpus citation | P/F |
| FT-BACKEND-2 | Second live OTLP backend (closes R4) | EXT-10, OTEL-1 | 3 | ci | Tempo + Jaeger | Export loads unmodified in both backends; second live backend proven | P/F |

**Totals: 94 new cases** (S1 5 · S2 12 · S3 14 · S4 10 · S5 8 · S6 5 · S7 12 · S8 3 · S9 3 · S10 3 · S11 2 ·
S12 3 · S13 5 · S14 5 · S15 4). Of these, 19 carry the `P/F|D` declare class (only where the release gate says
"or declared"). Combined with the v0.1.0 regression block: **50 + 226 + 49 + 94 = 419 checks.**

---

## 7. Detailed case specifications

Each case follows the v0.1.0 lifecycle and generated-spec shape
(`scripts/fieldtest/cases/<ID>-*.md` + `cases/steps/<ID>.sh`, produced from `cases/registry.json` by `gen_cases.py`).
Below, each case gives **Goal · Preconditions · Steps · Assertions · Artifacts · Fallback**. Assertions are
machine-checkable (`ft_assert`, each recorded in `assertions.ndjson`); **pass = all assertions true**. A missing
prerequisite fails the case. The flagship and novel-mechanics cases are specified in full; the remainder follow the
same template and are frozen in the roster and the registry.

### 7.1 S1 — Install, deployability & attestation

- **FT-ENV-0 — Fresh install on 3 OSes.** Goal: close R2 and prove the NAM-1 install guard. Preconditions: clean
  macOS/Linux/Windows VM, no agentwatch, Claude Code + Cursor present. Steps: run `init`; use the harness; assert first
  tool call recorded; attempt a bare-name install to trigger the distribution-check warning. Assertions:
  `first_run_timing.py` ≤ 900 s per OS; `verify-store` green; no agent-code change; `env.json` OS-tagged; the bare-name
  install produces the loud warning and names the qualified package (**NAM-1**, ADR-0026). Artifacts: per-OS timing
  JSON + store copy. Fallback: none (hard gate). Class P/F.
- **FT-WIN-1 — Windows.** Goal: named-pipe daemon + `init --service` + CI leg. Steps: run the Windows CI leg;
  bootstrap on a Windows host if available. Assertions: full hook→store→verify→replay green; matrix row
  `live-verified`; named-pipe permissions differ from UDS and are documented. Artifacts: CI log + matrix diff.
  Fallback: if no Windows host, **declare** with the CI leg evidence + a known-limitations line. Class P/F|D.
- **FT-DEP-1 — Managed policy.** Steps: apply the `allowManagedHooksOnly`/`strictPluginOnlyCustomization` fixture
  (and a real managed config where available); run `init`/`doctor`; attempt the supported managed install path.
  Assertions: `doctor` prints "hooks effective: yes / blocked by managed policy / unknown" per harness and **never**
  "installed" while blocked; managed recipe works or the limitation is named; `uninstall` byte-identical for user
  installs and a clean no-op for managed. Artifacts: `doctor` output + managed-config fingerprint. Class P/F|D.
- **FT-DEP-2 — Hook strip.** Steps: record a session; strip the hooks between sessions; start a new session.
  Assertions: `recorder-config-changed` raised at next session start; unattested interval classified as a gap;
  attestation carries digest+booleans only (property test: no config values/secrets); `coverage`/`evidence` include
  the attestation; a session without one is `attestation:absent`. Artifacts: attestation records + gap report.
- **FT-DEP-3 — Hook cost.** Steps: run the perf gate for a 500-call session on each OS. Assertions:
  `reference/performance.md` gains an end-to-end table; p50/p99 within the user-visible budget (**< 500 ms per tool
  call at p99, 250 ms per hook**) against the committed baseline; a missed budget yields a
  tracked ADR (not a silent miss); a blocked OS leg is reported blocked, never measured. Artifacts: perf-gate
  output. Class P/F|D (Windows leg).

### 7.2 S2 — Standards & interop

- **FT-AAT-1 — Third-party AAT round-trip (flagship).** Steps: `export-session <id> --format aat --out s.aat.json`;
  feed it to an **independent AAT consumer** (not agentwatch); re-ingest its round-tripped output. Assertions:
  validates against `schema/vectors/` AAT fixtures; external consumer accepts + chain verifies; `lossless-or-explicit`
  (no invented fields); draft revision cited. Artifacts: bundle + external consumer log + dual-verifier vectors.
- **FT-AAT-2 — Foreign ingest.** Steps: `ingest --format aat <synthetic-bundle>` containing normalizable and
  non-normalizable records. Assertions: normalizable records chain; non-normalizable quarantined (0600, excluded from
  export) with a reason; no egress. Artifacts: quarantine log + store diff.
- **FT-AAT-3 — Draft pin/drift.** Steps: run the drift job; then simulate a draft-revision field change. Assertions:
  pinned revision surfaces in `--version`/export; the simulated bump opens a failure (drift job), not a silent pass.
- **FT-OTEL-1 / FT-BACKEND-2 — Agent spans in 2 backends.** Steps: emit a canonical agent-span tree; query Jaeger
  and Tempo. Assertions: both render the tree; semconv pin + operation-name alignment carried; R4 second backend
  closed. Artifacts: two backend queries.
- **FT-OTEL-2 — gRPC streaming.** Steps: stream the 100 MB OTLP/gRPC fixture. Assertions: ingest succeeds within the
  memory bound; no whole-document load (RSS sampled); records validate.
- **FT-OTEL-3 — Privacy mapping.** Steps: property-test the privacy-mode ↔ content-capture mapping per mode.
  Assertions: metadata-only default; no content on export for metadata-only/truncated/hashed.
- **FT-OTEL-4 — Skill spans.** Steps: run the SDK corpus; property-test the skill / command-execution agent-span
  mapping per harness. Assertions: spans mapped where a harness exposes them; a harness that exposes nothing carries
  a **declared gap** — spans are never invented. Artifacts: property-test output. Class P/F|D.
- **FT-TRACE-1 — Cross-host chain (flagship).** Steps: 3 hosts × 3 harnesses; `traceparent` propagated; one broker
  interruption injected. Assertions: `trace <tid>` reconstructs one ordered chain; the broker gap is **classified**
  (not absorbed); each hop shows identity/delegation/approval or `unknown`. Artifacts: trace tree JSON.
- **FT-TRACE-2 — Skew.** Steps: skew one host's clock; re-run. Assertions: documented ordering rules applied; skew
  bounded/flagged (F9 discipline); propagation break classified.
- **FT-PG-1/2/3 — Derived Postgres (phased).** Steps: `--rebuild` twice; two-tenant query; SDK emit with PG down.
  Assertions: bit-for-bit rebuild; cross-tenant returns nothing + audited; SDK spans chain-protected, `union` is the
  no-PG fallback. Class P/F|D (explicitly phased → v0.2.1; if not landed, declared with the ADR-0035 decision).

### 7.3 S3 — Harness fidelity, real-time & test kit

- **FT-CUR-1/2 — Cursor.** Steps: replay the version-tagged golden corpus; exercise blocking events and
  IDE/CLI/remote env variants. Assertions: canonical record output per event; `beforeReadFile`/`afterAgentThought`
  captured; blocking payloads recorded but **never answered** (agent not stalled); cloud-agent gaps declared, not
  silent. Fallback (live capture on a non-Cursor machine): `fixture-verified` tier + declaration. Class P/F|D.
- **FT-GEM-1 — Gemini.** Steps: point Gemini telemetry at the collector; ingest. Assertions: validated records;
  `active_approval_mode`→approval; `user.email` hashed in metadata-only; **redaction runs on the logPrompts path**.
- **FT-COD-1 — Codex.** Steps: ingest rollout fixtures incl. `.jsonl.zst`, duplicate plaintext, dangling session,
  and a weaponized backtick payload. Assertions: fixture-verified; dedup; `crashed/inferred`; hostile fixture
  contained, never executed.
- **FT-MCP-1/2 — MCP full surface.** Steps: replay fixtures across 2025-06-18 / 2025-11-25 / 2026-07-28.
  Assertions: `resources/read`(+links), `prompts/get`, elicitation (linked to approval), `tasks/*` recorded;
  Streamable HTTP default; sampling/roots/logging closed-by-spec; malformed frame quarantined.
- **FT-LOG-1 — Log readers.** Steps: per-agent reader fixtures (Codex/Gemini/Copilot/OpenCode/long tail).
  Assertions: `log-read` tier; read-only; no shell on ingest; unknown version states the range, no guessing.
- **FT-STR-1 — Live p99 (flagship).** Steps: open the live timeline while an agent works; measure hook→view.
  Assertions: p99 ≤ 1 s; anomalies in the live inbox. Artifacts: latency histogram.
- **FT-STR-2 — Reconciliation + soak.** Steps: 24 h streaming soak; kill the consumer mid-run. Assertions: **no
  store loss on consumer crash**; back-fill reconciles; derived views never diverge from the chain; gaps classified.
  The 24 h target runs on the dedicated soak runner; the hosted-CI 6 h cap runs a bounded nightly and is a declared
  environment limit, never a green claim.
- **FT-LG-1 — Tier-2.** Steps: instrument a LangGraph app + a raw-Python path. Assertions: one command; spans
  chain-protected; `source: sdk`; conformance pack green.
- **FT-XHT-1 — Corpus replay self-test.** Steps: run the replay runner; inject a deliberately broken adapter.
  Assertions: every registered adapter has ≥N fixtures; the broken adapter **fails** (verify the verifier).
- **FT-XHT-2 — OpenCode soak.** Steps: hermetic OpenCode run with the recorder attached for the nightly window.
  Assertions: full pipeline green; row gains `live-verified`. Fallback: synthetic soak retains; declare if the pinned
  model endpoint is unavailable. Class P/F|D.
- **FT-XHT-3 — Cross-parser diff.** Steps: run our reader + two independent OSS parsers on the golden corpus.
  Assertions: normalized diff within tolerance or a documented interpretation gap; divergence fails.
- **FT-XHT-4 / FT-MATRIX-1 — Tiers.** Assertions: generator emits the tier column with corpus citations; no
  "modeled" Tier-1 row survives.

### 7.4 S4 — Detector credibility & redaction quality

- **FT-DET-1/2/3 — Eval.** Steps: `detectors eval --corpus v1` twice (rule + LLM). Assertions: byte-identical
  output across runs; published per-detector precision/recall reproduced; ≥80% of rule detectors non-silent; a
  detector without a catalog entry fails CI; `llm_called_ok` on every LLM scenario.
- **FT-DET-4 — Injection/memory signals.** Steps: replay the injection corpus + memory edit fixtures. Assertions:
  observations fire with published precision/recall; signals only (no enforcement); high-FP rules off by default.
- **FT-DET-5 — Detector telemetry.** Steps: enable opt-in detector telemetry; emit markers; feed them to a
  SIEM-shaped consumer. Assertions: off by default; fired/suppressed/false-positive markers carry no content (no
  trace/argument/prompt), are bounded, and are feedable.
- **FT-DET-6 — New-class scenario depth.** Steps: run the scenario matrix over the v0.2.0 classes (injection
  heuristics, memory-surface, credential hygiene, sandbox denials) plus EXT-12 fixtures (bypass-heavy sessions,
  capability drift, mode transitions). Assertions: positive/negative/boundary scenarios per class; per-harness
  numbers published in the catalog.
- **FT-DET-7 — Real-harness trace replay.** Steps: replay detectors over the real testkit traces (Claude Code
  transcripts, Cursor session-tracer output, Codex rollouts). Assertions: the "non-silent on real harnesses" claim
  rests on measured firing on real traces, not on the fixture list alone.
- **FT-COR-1 — Second corpus (flagship).** Steps: run the eval harness on a **second, independent** corpus.
  Assertions: numbers match the published ones within the stated bounds; corpus version + method + CIs cited;
  "your corpus may differ" statement present.
- **FT-COR-2 — Registry export.** Steps: `evidence <id> --include incident-report.json`. Assertions: validates
  against the AIR-shape schema fixture; **no auto-submission path exists** (test asserts it).
- **FT-RED-1 — Redaction benchmark.** Steps: `redact eval --corpus vN`. Assertions: per-class recall/FP reproduced
  deterministically; misses listed as known limitations with the proving test; corpus carries no real secrets.

### 7.5 S5 — Identity, compliance & SIEM

- **FT-IDN-1 — Attribution (flagship).** Steps: multi-agent fixture across the fleet; run
  `impact`/`blame`/`tree`/`trace`. Assertions: "which agent, on which machine, under whose approval, on whose
  behalf" complete or honest `unknown`; identity fields pass the secret property test.
- **FT-IDN-3 — Credential hygiene.** Steps: run the credential fixture corpus (ambient / shared secrets).
  Assertions: `credential_class: ambient/shared` fires with published precision/recall; it is an observation, never
  a verdict; the AIMS / WIMSE mapping is cited. Artifacts: corpus output.
- **FT-CMP-1 — Offline compliance report (flagship).** Steps:
  `compliance report --framework iso-42001 --period Q3-2026 --out audit/`; then re-run one row's cited command from
  scratch. Assertions: every row has verdict + regenerating command + bundle refs + retention/signature status;
  **zero unverifiable claims**; runs offline/air-gapped; non-certification statement present.
- **FT-CMP-2 — Retention + signing.** Steps: apply a retention profile; verify a signed checkpoint; then tamper.
  Assertions: signed default verifies; tampered signature fails; missing key → "signed by key id X, key unavailable";
  a missed retention run degrades visibly.
- **FT-CMP-3 — Templates + rotation.** Steps: run all five templates (eu-ai-act-art12, iso-42001, iso-27001,
  soc2, nist-800-92); `checkpoint rotate`; verify with the old key absent. Assertions: all five run offline;
  rotation appends a metadata-only `key-rotation` chain event (previous → new key id); the missing-epoch verdict is
  exactly "signed by key id X, key unavailable"; signing posture surfaces via `verify-store`, `evidence`, AAT
  export, `doctor`, and `/healthz`.
- **FT-SIEM-1 — OCSF/Syslog.** Steps: run the reference consumers per flavor; unconfigure a sink's redaction.
  Assertions: conformance green; redaction gate blocks the unconfigured sink; unreachable sink → bounded queue +
  `degraded`; over-limit event → truncated marker.
- **FT-ASI-1 — OWASP ASI.** Steps: `compliance report --framework owasp-asi-2026`; run **every row's command**.
  Assertions: all ten ASI rows + AST10 present; each row has an evidence command or explicit "not evidenced"; no
  prevention claim; non-certification statement present.

### 7.6 S6 — New capture surfaces

- **FT-A2A-1 — Cross-org delegation (flagship).** Steps: run the A2A proxy round-trip with a signed card and an
  unverifiable card. Assertions: task lifecycle + messages + artifacts + card exchange recorded; card verification
  outcome recorded (verified/unverified); **unverified card never trusted as authorization**; `tree`/`trace` extend
  across the boundary. Artifacts: signed-card provenance.
- **FT-GWY-1 — Gateway.** Steps: ingest the LiteLLM fixture stream. Assertions: recipe green; `cost` shows exact vs
  estimated, source-stamped; gateway absent → no effect.
- **FT-SYS-1 — System effects.** Steps: ingest an AgentSight/Tracee-shaped stream. Assertions: synthetic process tree
  joins its session; `source: system-ingest` label; false-join precision published; macOS/Windows stated not-covered.
  Class P/F|D (Linux-only, opt-in).
- **FT-CCA-1 — Compliance API.** Steps: consent-gated pull of the compliance fixture. Assertions: pull recorded as
  `store-access`; feed-vs-hook discrepancy classified; credentials session-scoped, never stored; local records
  unaffected if the API is unavailable.
- **FT-ACS-1 — ACS.** Steps: ingest an ACS Guardian audit-trail fixture. Assertions: `denied`/`policy-fired` with
  `record_phase: pre_execution`; no decision executes in agentwatch; unknown frame quarantined. Class P/F|D (watch item).

### 7.7 S7 — Platform, SDK, interfaces & policy

- **FT-SDK-1 — SDK lifecycle.** Steps: exit mid-span; replay for sampler determinism; call after shutdown; concurrent
  tracer creation. Assertions: flush-on-exit loses no record; sampler deterministic (same session→same decisions);
  security events never sampled; `coverage` shows sampling; valid no-op after shutdown; existing `@trace_agent`
  unchanged (DD-12).
- **FT-API-1 / FT-EXA-1 / FT-GOV-1.** Assertions: `openapi.json` present and drift-checked; every gallery recipe
  green or explicitly illustrative; codemod tested; unregistered plugin fails CI.
- **FT-AGI-1 — Read-only MCP (flagship).** Steps: enumerate MCP tools; run the injection fuzz over record content.
  Assertions: **no tool mutates store/config/hooks** (enumerated); responses labeled untrusted with record IDs;
  metadata-only default leaves no content to inject; every query `store-access`-recorded; off by default.
- **FT-AGI-2 / FT-FWK-2.** Steps: scripted agent uses the skill; `instrument()` detects frameworks. Assertions:
  documented answers on the demo store; CLI JSON schemas published; `instrument()` prints gaps (no silent partial),
  flush-on-exit, idempotent.
- **FT-POL-1 — suggest-policy (flagship).** Steps:
  `suggest-policy --since 30d --target claude-settings --out proposed.json`; then `what-if proposed.json --since 30d`;
  monitor filesystem writes. Assertions: **no write outside `--out`**; each rule shows evidence (n calls/sessions/
  approvals/last seen); broad-rule lint flags wildcard exec/network; destructive never `allow` without `--include`;
  `what-if` (**POL-2**) is labeled a simulation, format-version-stamped, and shows prompts avoided + would-be denials
  with sessions; parse errors explicit.
- **FT-FWK-1 — Framework recipes.** Steps: run ADK/Strands/OpenAI-Agents/Claude-Agent-SDK recipes against pinned
  versions. Assertions: each runs in CI; ≤2 lines/1 block; `unmapped` explicit; `source` + integrity carried.
  Class P/F|D (live pinned runs).
- **FT-CCO-1 — Native OTel join (flagship).** Steps: ingest captured Claude Code OTel; join to hook records by
  `tool_use_id`. Assertions: ≥95% join; hook-only/otel-only/discrepancies classified; `approval` uses native
  `decision_source` (fallback S14 only with `evidence:"inferred"`); exact vs estimated cost source-stamped; redaction
  on ingest; no prompt text unless the harness *and* privacy mode permit.
- **FT-CCO-2.** Steps: Agent-SDK program via the same path. Assertions: `source: sdk-native`; identity from resource
  attributes; gallery example runs.
- **FT-TSS-1 — Span-taxonomy spike.** Steps: drive the SDK corpus; derive the tool taxonomy from observed spans.
  Assertions: the taxonomy is span-driven (not taxonomy-first); every finding lands as a new M31 ticket in the WBS;
  no production code depends on the spike. Class P/F|D.

### 7.8 S8 — Authorization & oversight

- **FT-APV-1 — Approval fidelity (flagship).** Steps: replay classifier-approved, bypass-mode, human-once,
  human-remembered, rule, hook, denied, and indeterminate fixtures. Assertions: each value proven by a fixture; a
  classifier-approved call is `classifier`, **never `user`/`auto`**; a bypass call is `bypass` even with no prompt;
  no value inferred from `outcome=ok`; taxonomy + legacy mapping published.
- **FT-APV-2 — Oversight report (flagship).** Steps: `oversight --since 30d --project infra` over the field corpus;
  compute totals by hand. Assertions: cross-tab (destructive × authorization source) matches hand totals; report is
  deterministic/offline/version-stamped; latency only when both timestamps exist, else "n/a (n calls)"; <5 s on 100k.
- **FT-APV-3 — Permission mode.** Steps: `search --mode bypass --since 30d`; replay a default→bypass→default fixture.
  Assertions: mode recorded per call + transitions as observations; bypass interval flagged in `impact`; missing mode
  → `unknown`, counted in coverage.

### 7.9 S9 — Capability supply chain & memory

- **FT-CAP-1 — Plugin4Shell drift (flagship).** Steps: inventory; swap a pinned plugin/skill/hook for changed
  content with the same version; diff. Assertions: one command lists capabilities with scope+digest; "content
  changed, version unchanged" is a distinct highlighted class; `capability-changed` in sink + `tail`; digests never
  content; no verdict language; new non-agentwatch hook surfaced.
- **FT-CAP-2 — Load attribution.** Steps: `replay <id>`; `search --capability <name>`; `impact <id>`. Assertions:
  loads shown inline; sessions after a load returned; `impact` lists loaded capabilities; wording "followed the load
  of", never "caused".
- **FT-MEM-1 — Out-of-band memory edit (flagship).** Steps: edit the memory store outside the agent between
  sessions; diff. Assertions: the change is flagged as not attributable to any recorded session; `search --memory`
  returns sessions following a memory change; exposure matrix honest.

### 7.10 S10 — Code provenance

- **FT-PRV-1 — Commit → session (flagship).** Steps: commit from a recorded session, then hand-edit a file, then
  query. Assertions: resolves in <2 s; a commit with no recorded session says "no recorded agent activity", **not
  "human"**; hand-edited-after-agent ranges `mixed`; confidence per range; sessions with coverage gaps in the window
  flagged.
- **FT-PRV-2 — Agent Trace.** Steps: `export-session <id> --format agent-trace`; run the redaction attack pack;
  cross-validate against git-ai notes where present. Assertions: validates vs pinned revision; **no code content**
  (ranges/hashes/ids only); classifications agree/disagree/agentwatch-only/notes-only; write-to-repo only by
  explicit consented command ("as of revision X" wording).
- **FT-PRV-3 — Range + hash capture.** Steps: make file-modifying calls under each privacy mode; run the
  redaction attack pack. Assertions: line ranges + content hashes exist under every mode including `metadata-only`;
  **no content or diff text anywhere** (property + attack pack); edit tools without range support declare the
  file-level `heuristic` fallback; capture cost stays inside the FT-DEP-3 hook budget.

### 7.11 S11 — Local console & query tier

- **FT-LUI-1 — Console (flagship).** Steps: on a clean machine with one recorded session, time `agentwatch ui` to
  first browser view; run `apps/web/tests/e2e/console.spec.ts` against the live console (`FT_CONSOLE_URL`) to recapture
  its screenshots (`console-overview`, `console-signatures`) and run the real-browser axe gate; compare UI numbers to
  CLI `--json`. Assertions: ≤60 s; loopback only; per-launch token; read-only (no mutation endpoint exists); zero
  network; broken chain/tombstones/gaps visible; UI == CLI for sessions/impact/cost/coverage/oversight; axe passes
  (0 serious/critical); the console screenshots are written to the case artifacts.
- **FT-LUI-2 — Index.** Steps: delete the embedded index; run commands; rebuild; compare. Assertions: commands still
  work (slower); rebuild bit-for-bit; targets met on a 1M-record store; no heavyweight new dep (ADR-0035); purge/
  retention propagate (EXT-5).

### 7.12 S12 — Governance & retention

- **FT-ACC-1 — Role matrix (flagship).** Steps: attempt cross-role reads. Assertions: cross-role read returns
  **nothing** and is itself recorded; the user sees who (by role) accessed their records; resolving a hashed
  principal requires an explicit recorded action; default fleet profile least-privileged.
- **FT-ACC-2 — Notice/DPIA.** Steps: `governance notice` from the live config; inspect the DPIA starter. Assertions:
  every statement maps to a config key/guarantee; unbackable statements omitted and listed; "not legal advice" banner.
- **FT-HLD-1 — Legal hold (flagship).** Steps: `hold add`; `retention apply --dry-run`; attempt `purge`; rebuild the
  index; override. Assertions: held records survive retention+purge+rebuild; `purge` fails closed with the hold ref;
  override requires a stated reason and is conspicuous in `evidence` + report; holds/releases/overrides are chain
  records.

### 7.13 S13 — Investigation depth & verification

- **FT-ENV-1 — Env delta (flagship).** Steps: seed a model-version change; `diff <good> <bad>`; `drift`;
  `sessions --group-by-env`. Assertions: environment delta printed **above** the behavior diff (model/harness/mode/
  capability/config); "coincides with" wording, no causal claim; names/versions/digests only; absent → `unknown`.
- **FT-VFY-1 — Browser verifier (flagship).** Steps: open the static page from `file://`; drop a valid and a
  tampered bundle; capture the network log. Assertions: **zero network requests**; verdicts equal the CLI on the whole
  fixture set (differential test); tampered bundle names the first broken link; page is a signed, checksummed release
  artifact; shows "recording attested" from DEP-2.
- **FT-IR-1 — Incident case (flagship).** Steps: `case create INC-4471`; add sessions across hosts; `case show`;
  `case export`. Assertions: case membership changes are chain records; merged timeline states ordering rules and
  classifies gaps; per-session verdict table; bundle verifies offline; **no registry egress** (test).
- **FT-CNC-1 — Concurrency.** Steps: two overlapping sessions on one repo; `concurrency --project . --since 7d`.
  Assertions: overlap reported; `provenance` marks multi-session ranges `ambiguous`.
- **FT-SBX-1 — Sandbox events.** Steps: run a session with denied network/file attempts and an unsandboxed command.
  Assertions: `oversight` shows "% calls unsandboxed" + denial counts by class; `impact` separates attempted-blocked
  from contacted; harness exposing none says so, no inference from absence; event in the security-event schema with
  an OCSF mapping.

### 7.14 S14 — Outcomes, ephemeral capture & growth

- **FT-OUT-1 — Outcome facts (flagship).** Steps: `outcomes --since 30d --by project`; `cost --by project --per
  retained-change`. Assertions: numerator/denominator + derivation version; source-stamped; determinism with network
  disabled + no model configured; unknown stays unknown.
- **FT-OUT-2 — Failure signatures.** Steps: `digest`. Assertions: top-N patterns with counts/first-last seen/example
  sessions/trend; grouping rules versioned; each links to replay/diff.
- **FT-RUN-1 — Runner segment (flagship).** Steps: a CI job records a run and uploads a sealed segment;
  `import-segment`; tamper the segment; re-verify. Assertions: segment verifies + anchors; tampered fails; imported
  records **visibly distinguished** from locally-chained; zero egress; attack pack passes; `traceparent` joins the
  runner to the originating local session.
- **FT-DEMO-1 / FT-NTF-1.** Assertions: demo bundle opens offline, zero network, secret-scanned; the three shipped
  recipes — Slack incoming webhook, PagerDuty Events API v2, Prometheus Alertmanager v2 — are CI-tested via the
  webhook sink, with claims-ledger entries and the "routing lives in your stack; agentwatch forwards events
  rule-free" statement.

### 7.15 S15 — Hostile data, claims ledger, closed gates

- **FT-HOSTILE-1 — Weaponized ingest (flagship).** Steps: ingest weaponized AAT/Cursor/Codex/Gemini/gateway/A2A
  fixtures including the Codex #36937 backtick HOME-deletion payload; monitor for any shell/eval/pipe execution.
  Assertions: nothing executes; hostile content quarantined; `replay` is render-only; bundles label content
  untrusted; fuzz (`RSK-1`) reports no un-caught crash. This is the ADR-0024 threat-model proof.
- **FT-CLAIM-1 — Ledger/closures.** Steps: run the claims-ledger check; walk G1/G2/G4/G7/G8. Assertions: every public
  number has a ledger entry; each removed limitation has a proving test; no unresolved claim.
- **FT-MATRIX-1 / FT-BACKEND-2.** Assertions: matrix emits tiers, no "modeled" Tier-1; both Jaeger and Tempo load
  the export unmodified.

---

## 8. CUJ coverage matrix (CUJ-15–34 + CUJ-8 extension)

Every new CUJ is proven end-to-end by ≥1 case; flagship journeys map to several.

| CUJ | Journey | Proving cases |
|---|---|---|
| CUJ-15 | Auditor accepts agent logs (AAT) | FT-AAT-1, FT-AAT-2, FT-EXA-1 |
| CUJ-16 | One action across agents/hosts | FT-TRACE-1/2, FT-IDN-1, FT-IDN-3, FT-SIEM-1 |
| CUJ-17 | Watch a live agent | FT-STR-1, FT-STR-2, FT-XHT-2 |
| CUJ-18 | Prove compliance continuously | FT-CMP-1, FT-CMP-2, FT-CMP-3, FT-SIEM-1, FT-ASI-1 |
| CUJ-19 | Does the detector fire for us? | FT-DET-1/2/3/5/6/7, FT-COR-1, FT-XHT-1 |
| CUJ-20 | Who did my agent delegate to? | FT-A2A-1 |
| CUJ-21 | Was a human in the loop? | FT-APV-1/2/3, FT-CCO-1, FT-SBX-1 |
| CUJ-22 | Which commit did the agent write? | FT-PRV-1, FT-PRV-2, FT-PRV-3 |
| CUJ-23 | Did a skill/plugin/rules change? | FT-CAP-1, FT-CAP-2, FT-MEM-1 |
| CUJ-24 | Browser view in 60 s, no Docker | FT-LUI-1, FT-LUI-2 |
| CUJ-25 | Roll out under managed settings | FT-DEP-1/2/3, FT-WIN-1, FT-ENV-0 |
| CUJ-26 | Let an agent query safely | FT-AGI-1, FT-AGI-2 |
| CUJ-27 | Turn history into policy | FT-POL-1 |
| CUJ-28 | Instrument in two lines | FT-FWK-1, FT-FWK-2, FT-CCO-2 |
| CUJ-29 | Cost vs what stuck | FT-OUT-1, FT-OUT-2 |
| CUJ-30 | Unattended runner evidence | FT-RUN-1 |
| CUJ-31 | Roll out lawfully/transparently | FT-ACC-1, FT-ACC-2 |
| CUJ-32 | Legal hold for this case | FT-HLD-1 |
| CUJ-33 | It worked last week — what changed? | FT-ENV-1 |
| CUJ-34 | Package this incident | FT-IR-1, FT-CNC-1 |
| CUJ-8 ext | Verify with nothing installed | FT-VFY-1, FT-DEMO-1 |
| CUJ-1 | Install & record (closed on 3 OSes) | FT-ENV-0, FT-WIN-1 |
| CUJ-3 | Export to a backend you own | FT-OTEL-1, FT-BACKEND-2, FT-OTEL-2, FT-OTEL-3, FT-OTEL-4 |
| CUJ-10 | What did our agents cost? | FT-GWY-1, FT-CCO-1 |
| CUJ-11 | Instrument my own agent | FT-SDK-1, FT-LG-1, FT-PG-3, FT-TSS-1 |
| CUJ-13 | MCP server changed under me | FT-MCP-1, FT-MCP-2 |
| CUJ-14 | Did a human approve? | FT-GEM-1, FT-CCA-1 |

No CUJ is left without a case. A `declared` outcome for a `P/F|D` case still requires its CUJ to be named in the
report with the limitation, per PRD 40 §5-expanded.

---

## 9. Harness work (M31 31.1–31.4)

Extend `scripts/fieldtest/` — do **not** fork it.

1. **Environment (31.1, #408).** Add the §3 services to `docker-compose.fieldtest.yml`: `otel-grpc`, `fleet-h1..3`,
   `a2a-proxy`, `litellm`, `runner`, `managed-hooks` profile, plus the Windows CI leg and the static verifier
   artifact. Seed/reset/teardown for each (reuse `stack_up`/`stack_teardown_on_exit`).
2. **Scripts/drivers (31.2, #409).** New runners alongside `emit-hook.py`/`drive-agent.py`:
   `ingest-fixture.py` (AAT/OTel/Cursor/Gemini/Codex/MCP/A2A/gateway/ACS), `stream-probe.py` (STR p99 + drop
   consumer), `fleet-run.py` (3-host trace), `native-otel-join.py` (CCO), `capability-drift.py` (CAP/MEM),
   `provenance-repo.py` (PRV), `verifier-page.py` (VFY zero-network capture), `segment-runner.py` (RUN),
   `oversight-corpus.py` (APV), `hostile-ingest.py` (R5). Each reuses an existing primitive where possible.
3. **Cases (31.3, #410).** Add 94 registry entries + generated specs/steps to `cases/registry.json` via `gen_cases.py`
   (the generator already prunes stale files). Hand-write the flagship specs where the generated template is too thin.
4. **Harness port (31.4, #389).** Extend `lib.sh` assertions for the new services, add per-case environment
   fingerprints (`env.json` records OS/arch/model/fixture revisions), and extend `collect-results.py` to carry the
   `P/F|D` class and a `declared` reason field. Preserve **no-skips** and **verify-the-verifier** (a broken-adapter /
   broken-verifier self-test per suite).

**Fixtures (31.2/31.3).** Version-tagged and secret-scanned: AAT vectors + external consumer; Cursor/Gemini/Codex/MCP
golden corpora; Claude Code OTel capture; gateway stream; A2A signed/unverifiable cards; capability/memory stores;
git repo for provenance; hostile pack (ADR-0024, incl. Codex #36937); a 100 MB OTLP/gRPC stream; a second detector
corpus; a redaction corpus; role/tenant matrices; a mode-transition session.

**Playwright (31.3/31.4).** Extend the browser tests for v0.2.0: keep `screenshots.spec.ts` recapturing the 8 guide
images, and add `apps/web/tests/e2e/console.spec.ts` for the local console (screenshots + axe). The console driver
(wired into FT-LUI-1) starts `agentwatch ui` and passes its `FT_CONSOLE_URL`; the spec skips only when the URL is
absent, so a console run that is *claimed* but not exercised fails the case rather than passing by default.

---

## 10. Results (all under `field-test/v0.2.0/results/`)

```
field-test/v0.2.0/results/<suite>/<case>/
  commands.log stdout.log stderr.log verdict.json assertions.ndjson
  env.json                 # OS/arch, docker/compose, image digests, OMLX model, fixture revisions
  artifacts/…              # bundles, traces, reports, screenshots, network captures
```

Plus `summary.md` / `summary.json` per suite and a top-level rollup. `verdict.json` carries `status` (`pass|fail`) and,
for the declare class only, `declared` + `limitation` + `release_gate_item`. `field-test/v0.2.0/results/` is gitignored
except `.gitkeep`. Evidence paths mirror the WBS suites (`install/ aat/ harness/ mcp/ stream/ trace/ comply/ det/
hostile/ apv/ dep/ cap/ lui/ prv/ agi-pol/ gov/`).

---

## 11. Execution

```bash
make setup
(cd apps/web && npm ci && npx playwright install --with-deps chromium)

# Layer 0 — v0.1.0 regression (must be green first)
bash scripts/fieldtest/run-all.sh                      # the 50 v0.1.0 cases
make e2e                                               # Playwright: analyst web + screenshots (8 guide PNGs)

# Console Playwright (FT-LUI-1): starts the loopback console + runs the console spec
python3 scripts/fieldtest/console_playwright.py

# Layer 1 — v0.2.0 suites (per-suite so a failure localizes)
OMLX_BASE_URL=http://host.docker.internal:8000/v1 OMLX_MODEL=Qwen3-4B-Instruct-2507-4bit \
  bash scripts/fieldtest/run-suite.sh s1-install
# … s2-interop s3-harness s4-detectors s5-identity s6-surfaces s7-platform \
#     s8-apv s9-capability s10-provenance s11-console s12-governance \
#     s13-investigation s14-outcomes s15-hostile

# One case
bash scripts/fieldtest/run-case.sh FT-APV-1 --keep
```

Windows (`FT-WIN-1`, FT-DEP-3 Windows leg) runs on the `windows-latest` CI leg; managed-policy (`FT-DEP-1`) runs
against the `managed-hooks` profile and, where available, a real MDM config. Both are outside Compose and tag their
own environment fingerprint.

**M31 issue mapping:** environment #408, scripts #409, cases #410, harness #389; execution #390; report #391; defect
fixes #392; nightly CI #393; XHT validation #394; detector replay #395; expanded cases #488 (APV/CCO/DEP),
#489 (CAP/MEM/PRV), #490 (LUI/AGI/POL/ASI/FWK), #491 (ACC/HLD/ENV/VFY/IR/RUN); umbrella FLD-1 #370.

---

## 12. Gates, release-gate mapping & honesty

- A case passes only on explicit assertions; anything else is a failure. `declared` is reserved for the 19 `P/F|D`
  cases and only where the release gate says "or declared"; it needs evidence + a known-limitations line.
- **PRD 40 §5 mapping:** (1) FT-AAT-1/AAT-2; (2) FT-CLAIM-1; (3) FT-MATRIX-1/XHT-4; (4) FT-DET-1/2/3, FT-COR-1;
  (5) FT-CMP-1; (6) FT-STR-1/2; (7) FT-IDN-1; (8) FT-CLAIM-1 + this report.
- **§5-expanded mapping:** (9) FT-ENV-0, FT-DEP-3; (10) FT-OTEL-1 + FT-BACKEND-2; (11) FT-APV-1; (12) FT-LUI-1;
  (13) FT-DEP-1; (14) FT-CAP-1, FT-PRV-1, FT-PRV-2; (15) FT-POL-1, FT-ASI-1; (16) FT-HLD-1.
- **Known-limitations shrink (PRD 40 §1a):** G1→FT-STR-1; G2→FT-TRACE-1; G4→FT-DET-2; G7→FT-OTEL-1/2;
  G8→FT-CMP-2. G3/G5/G6/G9/G10/G11/G12 leave if their PRD lands, else carried forward by name.
- **Defects (31.7, #392):** every field-test defect is fixed with its own regression test; the report records
  root-cause analysis in the v0.1.0 style.
- **Naming (ADR-0026):** the install-guard `FT-ENV-0` also asserts the namesake install warning.
- **Do not claim a gate passed unless it was run on the merged HEAD.** A `declared` case is never reported as "done".

---

## 13. Report template (`docs/field-test/v0.2.0/FIELD_TEST_REPORT.md`)

Mirrors the v0.1.0 report and the WBS required sections:

1. BLUF + release-gate verdict (the 16 §5 / §5-expanded items).
2. Environment (per-OS, per-suite fingerprints; models; backend versions).
3. What was tested (v0.1.0 regression + 94 v0.2.0 cases + suites).
4. **Scenario Results (master table)** — all 94 rows with `pass|fail|declared` + evidence path.
5. Per-suite results (install/AAT/harness/MCP/stream/trace/comply/detector/hostile/apv/dep/cap/lui/prv/agi-pol/gov).
6. Detector & redactor published-numbers reproduction (FT-DET/COR/RED).
7. **CUJ-15–34 + CUJ-8 extension verification table.**
8. Root-cause analysis for every defect (fix + regression evidence).
9. Coverage & gaps; the `declared` register (named limitation + release-gate item).
10. **Observations · Learnings · Takeaways** (v0.1.0-style articles).
11. Claims-ledger status + known-limitations shrink evidence.
12. Evidence paths + reproduce commands.

---

## 14. Out of scope (declared) & limitations

Enforcement, attack/eval frameworks, hosted SIEM, prompt analytics, and injection **classification as a security
boundary** remain out of scope (PRD 14, unchanged). Browser-resident agents are a documented non-feature
(PRD 45). Postgres (`PG-1..3`) is explicitly phased to v0.2.1; if it has not landed at M31 it is a `declared`
outcome with the ADR-0035 decision cited — never silently dropped. TCK/Soak/SYS/ACS/CNC/OUT/RUN/DEMO/NTF/RED/STD are
`P/F|D` because PRD 40 §1b and the execution plan phase them to v0.2.x; each absent item is named with its target
milestone.

---

## 15. Rollout

1. Build the environment + scripts + fixtures (M31.1–31.2): §3 services up, hostile pack reports clean.
2. Land the 94 case specs + registry (M31.3) and the harness extensions (M31.4).
3. Run **Layer 0** (v0.1.0 regression) to green — no v0.2.0 case is evaluated before this.
4. Run S1–S4 (install/interop/harness/detectors), then S5–S8 (identity/surfaces/platform/APV), then S9–S15
   (capability/provenance/console/governance/investigation/outcomes/hostile).
5. Fix defects with regressions (31.7); wire the nightly `fieldtest.yml` (31.8, #393).
6. Publish the report (31.6, #391); close #389–#395, #408–#410, #488–#491, FLD-1 #370.

---

## 16. Appendix — PRD 41–59 feature coverage index

Every v0.2.0 / v0.2.0-expanded PRD names its proving cases. Non-runtime deliverables are carried by the WBS, not by a
field case: **COR-4** (registry/postmortem fixture mining, 28.COR-4), **RSK-2** (threat-model rows + ADRs 0016–0026,
26.RSK-2), and **STD-1** (standards-participation plan / DD-05, 29.STD-1) produce docs, ADRs, and fixtures rather than
an end-to-end scenario.

| PRD | Theme | Proving cases |
|---|---|---|
| 41 | Standards & interop II (AAT, OTel agent spans, W3C trace) | FT-AAT-1..3, FT-OTEL-1..4, FT-TRACE-1/2, FT-BACKEND-2 (PG-1..3 phased, §14) |
| 42 | Harness fidelity & real-time (Cursor/Gemini/Codex/MCP/streaming) | FT-CUR-1/2, FT-GEM-1, FT-COD-1, FT-MCP-1/2, FT-STR-1/2, FT-LG-1 |
| 43 | Detector credibility & evaluation | FT-DET-1..7, FT-COR-1/2, FT-RED-1 |
| 44 | Agent identity, enterprise & compliance | FT-IDN-1..3, FT-CMP-1..3, FT-SIEM-1 |
| 45 | New capture surfaces (A2A/gateway/system/CCA/ACS) | FT-A2A-1, FT-GWY-1, FT-SYS-1, FT-CCA-1, FT-ACS-1 |
| 46 | Platform, SDK & growth (Windows/TS spike/OpenAPI/gallery) | FT-SDK-1, FT-API-1, FT-EXA-1, FT-GOV-1, FT-WIN-1, FT-TSS-1 |
| 47 | Cross-harness test kit (corpus/replay/fidelity tiers) | FT-XHT-1..4, FT-MATRIX-1 |
| 48 | v0.2.0 risks, testing & decisions | FT-CLAIM-1 + the §12 release-gate mapping |
| 49 | Authorization & oversight provenance | FT-APV-1..3 |
| 50 | Deployability & recorder attestation | FT-ENV-0, FT-DEP-1..3 |
| 51 | Harness-native telemetry & framework reach | FT-CCO-1/2, FT-FWK-1/2 |
| 52 | Capability supply chain & memory | FT-CAP-1/2, FT-MEM-1 |
| 53 | Code provenance & attribution | FT-PRV-1..3 |
| 54 | Local console & embedded query tier | FT-LUI-1/2 |
| 55 | Agent interfaces & policy-from-history | FT-AGI-1/2, FT-POL-1 (POL-1/2) |
| 56 | Governance, retention integrity & redaction quality | FT-ACC-1/2, FT-HLD-1, FT-RED-1 |
| 57 | Investigation depth & evidence verification | FT-ENV-1, FT-IR-1, FT-CNC-1, FT-VFY-1, FT-SBX-1 |
| 58 | Outcomes, ephemeral capture & growth | FT-OUT-1/2, FT-RUN-1, FT-DEMO-1, FT-NTF-1 |
| 59 | OWASP Agentic & standards coverage | FT-ASI-1 (STD-1 non-runtime, §16 intro) |

**Folded feature-IDs:** `POL-2` (`what-if`) is exercised by FT-POL-1; `NAM-1` (naming install guard) is asserted by
FT-ENV-0. Both are named in the case specs above and in §12, so no ID is covered only "in spirit".
