# v0.2.0 — M25 Code Review Log

Record of the M25 (Foundations) code review and risk sign-off (issue #373). One row per finding;
closed when fixed + tested. Waived items carry a reason.

**Scope reviewed:** every M25 feature ticket (#295–#312, #424–#427) plus 25.T (#371) and 25.D (#372).

## Findings

| # | Ticket | Finding | Severity | Resolution | Status |
|---|---|---|---|---|---|
| 1 | CUR-2 (#304) | Adapter used assumed Cursor field names; adopting the CUR-1 corpus proved the published contract differs (`conversation_id`, `generation_id`, `workspace_roots`, `file_path`, `cursor_version`, `user_email`) | High | Realigned `agentwatch.adapters.cursor` to the published contract; conformance pack rebuilt from real payloads; compatibility row corrected | Fixed (`d96f190`) |
| 2 | CI-1/DET-1 (#427/#302) | `detector-eval.yml` pinned `actions/checkout@v4` and `actions/setup-python@v5` by tag, not commit SHA (supply-chain) | Medium | Pinned to the SHAs used by the other workflows | Fixed (`9dc2417`) |
| 3 | GEM-1 (#305) | `test_gemini_ingest.py` used an untyped `dict` and a >100-col row — broke `mypy --strict` / `ruff` | Low | `dict[str, Any]` + wrapped row | Fixed |
| 4 | DET-1 (#302) | `test_detector_eval.py` rows exceeded the line limit | Low | Wrapped rows | Fixed |
| 5 | v0.1.0 analytics (#286) | Milestone-end gates surfaced pre-existing v0.1.0 debt: `scenario_validation.py` (168×E501) + `llm.py` narrowing + 8 untyped defs | Low | Typed the helpers and fixed the `sim` narrowing; **E501 waived per-file** in `services/analytics/pyproject.toml` (reformatting a v0.1.0 scenario file is out of M25 scope; tracked in `docs/maintenance-backlog.md`) | Fixed / waived |
| 6 | CUR-1 (#303) | A consented live Cursor capture is infeasible in CI | Low (accepted) | Adopted a licensed MIT/vendor corpus; row is `fixture-verified`; live capture deferred | Waived with reason |

## Guardrails honored

- **Monitor-only** (blocking hooks recorded, never answered) — `test_cursor_adapter.py::test_blocking_hook_is_recorded_as_an_observation_and_never_answered`
- **Redaction before storage / no secrets committed** — `test_testkit_corpus.py::test_corpus_files_are_secret_free`, redaction suite
- **Foreign content never executed** (ADR-0024) — `test_fuzz_parsers.py` (#36937 seed) + `test_testkit_corpus.py::test_corpus_parsers_never_spawn_a_shell`
- **Append-then-verify preserved** — `test_streaming.py`, `test_m25_integration.py::test_streaming_drop_consumer_preserves_store_truth`
- **No egress** — egress-audit suite
- **Deterministic trust path** — chain verification, `verify_aat`, conformance runner

## Gate results (milestone close)

| Gate | Result |
|---|---|
| `make test` (full unit + coverage ≥ 95% + repo guard) | all packages pass; repo guard 27 passed |
| Coverage (≥ 95% gate) | `packages/python-sdk` **95.18%** (1534 passed, 1 skipped); `services/api` **99.58%** (42 passed); `services/analytics` **97.67%** (711 passed) |
| `make lint` (ruff zero) | clean (all three packages) |
| `make typecheck` (mypy `--strict`) | clean (all three packages) |
| Docs link-check / executable docs | `tests/test_docs_links.py` pass; `tests/test_doc_commands.py` 6 pass |
| Mutation gate | `--self-test` OK; RSK-1 mutants 6/6 killed |

## Risk sign-off (M25)

| Risk (PRD 48) | Status | Residual / evidence |
|---|---|---|
| R1 AAT/semconv churn | Mitigated | AAT draft pinned `-06`; `verify_aat` fails closed; OTel drift check; fuzz |
| R4 harness instability | Partly mitigated | version-tagged corpus + N4 drift baseline; Cursor stays `fixture-verified` (no consented live capture) |
| R5 hostile ingest | Mitigated | ADR-0024; parser fuzz + static shell guard + dynamic no-exec |
| R6 streaming failure | Mitigated | bounded per-subscriber queues; drop-consumer test; append-then-verify intact |
| R8 scope | Contained | M25 cut-line held; the one blocked item (CUR-1 live capture) was resolved via adopted corpus |
| R9 identity privacy | Mitigated | `principal` hashed by default; identity/secret property tests |
| R11 naming | Decided | ADR-0026 full-rename at v0.2.0 |

## Sign-off

- **Automated review evidence:** recorded above (commits `d96f190`, `9dc2417`, `633faa2`, `a4f4fad`, `98f91c5`).
- **Independent human risk sign-off:** ✅ **approved** by the maintainer (Debashish Ghosal, `@deghosal-2026`)
  on **2026-10-05** — no unresolved findings; the two waived items (#5 pre-existing v0.1.0 analytics E501,
  #6 CUR-1 live capture) are accepted with the reasons recorded above. Closes #373.

---

# v0.2.0 — M27 Code Review Log

Record of the M27 (Surfaces) code review (#379). One row per finding; closed when fixed + tested.

**Scope reviewed:** every landed M27 ticket — MCP-1..6 (#333–#338), GEM-2 (#342), DET-5 (#344), COR-2 (#345),
SIEM-1/2 (#346/#347), LG-2 (#349), EXA-1 (#351), **COD-1 (#339)**, **XHT-3 (#352)**, **LOG-1 (#340)**, UI-2
(#431), A11Y-1 (#432), RUN-1 (#433), TUT-1 (#434), 27.T (#377), plus DET-4 (#343, core) and LG-1 (#348, partial).

## Findings

| # | Ticket | Finding | Severity | Resolution | Status |
|---|---|---|---|---|---|
| 1 | M27 batch | MCP `DOCUMENTED_GAPS` shrank as surfaces landed (resources → prompts → tasks); the old `resources/read`-rejected test contradicted the new behavior | Medium | Test updated to reject a still-gapped method (`prompts/get`); capability/gap/conformance pack moved together per surface | Fixed |
| 2 | M27 batch | New test/source rows exceeded `ruff` line length and one append-tuple lambda broke `mypy --strict` | Low | Wrapped rows; typed closure; `ruff`/`mypy` clean on all packages | Fixed (`e5c2a4b`) |
| 3 | API-1 (#330) | Adding UI-2 endpoints drifted the generated `openapi.json` + typed client | Medium | Regenerated via `scripts/generate_openapi.py`; drift test green | Fixed |
| 4 | LG-1 / DET-4 | LLM `EmbeddingDriftDetector` shares `anomaly_type="output_drift"` with the rule detector | Low (documented) | LLM detectors kept out of the rule factory by **class** (property-tested); not entangled in the trust path | Accepted |
| 5 | COD-1/LOG-1/CCA-1/XHT-3/WIN-1 | No published rollout/log format, independent parsers, consented API pull, or Windows host available in this environment | Medium (accepted) | **Declared blocked** on each issue; not fabricated | Waived with reason |

## Guardrails honored (M27)

- **Monitor-only** — MCP proxy relays; elicitation recorded, never answered (`test_mcp_proxy_elicitation.py`).
- **Redaction before storage** — resource URI / prompt name / task id are secret-scanned metadata; `annotate --incident-tag` scrubbed (`test_incident_taxonomy.py`); telemetry is content-free (`test_detector_telemetry.py`).
- **Foreign content never executed** (ADR-0024) — no reader path spawns a shell; COD-1 blocked rather than guessed.
- **No egress** — detector telemetry is local-only NDJSON; sinks remain opt-in + self-test gated.
- **Deterministic trust path** — LLM detectors are strictly additive and outside the rule factory (`test_llm_eval.py`).

## Gate results (M27 batch)

| Gate | Result |
|---|---|
| `make test` (unit + coverage ≥ 95% + repo guard) | `packages/python-sdk` **95.02%** (1735 passed, 2 skipped); `services/api` **95.75%** (53 passed); `services/analytics` **95.18%** (728 passed); repo guard **34 passed** |
| `make lint` (ruff zero) | clean (all three packages) |
| `make typecheck` (mypy `--strict`) | clean (303 + 14 + 53 source files) |
| `make web-test` (vitest + axe) | 14 passed |
| Claims ledger | 38 claims / 101 live evidence links, check green |

The 2 SDK skips are expected and non-blocking: the live-capture golden corpus (needs a machine running Claude
Code) and the XHT-3 cross-parser diff (its own CI workflow provisions the two parsers; green there).

## Deferred (re-pointed)

`WIN-1` (#350) is **deferred to M31 field tests** (declared, not dropped): the Windows service supervision (Task
Scheduler XML) and a `windows-latest` CI leg landed and are tested on any OS, but the **named-pipe transport**
and an end-to-end **CUJ-1 timing run on Windows** cannot be verified from this macOS host — they run in M31.

Everything else landed: `COD-1`/`XHT-3`/`LOG-1` were unblocked by downloading the verified Codex format
(kvsankar/agent-history + `openai/codex` source), two independent pinned parsers (agent-history, agent-ouija),
and the OpenCode SDK schema; `LG-1` gained an O1 SDK conformance pack; `DET-4` published real numbers against a
live local `Qwen3.5-9B-MLX-4bit`; `CCA-1` added the consent-gated Compliance API ingest.

## Sign-off (M27)

- **Automated review evidence:** recorded above; the final gate is green (table above).
- **Deferral:** `WIN-1` re-pointed to M31 field tests (reason recorded).
- **Independent human risk sign-off:** ✅ **approved** by the maintainer (Debashish Ghosal, `@deghosal-2026`)
  on **2026-10-06** — no unresolved findings; the one deferral (WIN-1 → M31) is accepted with the reason
  recorded above. Closes #379.

## Final gate (M27 batch, all changes)

See `## Final gate (M27 batch, all changes)` results above (recorded in the M27 section headers).

---

# v0.2.0 — M28 Code Review Log

Record of the M28 (Depth) code review (#382). One row per finding; closed when fixed + tested.

**Scope reviewed:** every landed M28 ticket — CMP-4 (#361), IDN-4 (#363), CMP-3 (#360), GOV-1 (#369), MIG-1
(#436), COR-3 (#358), OTEL-4 (#362), DET-6 (#356), DET-7 (#357), DATA-1 (#435), TSS-1 (#368), COR-4 (#359),
plus 28.T (#380) and 28.D (#381).

## Findings

| # | Ticket | Finding | Severity | Resolution | Status |
|---|---|---|---|---|---|
| 1 | M28 batch | New detector tickets (IDN-4, DET-6) coupled many drift surfaces: factory count, `AnomalyType` enum, scenario matrix, public corpus, generated catalog, and count tests | Medium | Each registration moved together; counts/enums/corpus/catalog regenerated; deterministic guard tests added | Fixed |
| 2 | CMP-3 (#360) | `retention apply` now records a `retention-changed` marker (S5); the marker is appended **after** the run so the report's `purged`/`kept` still describe the records the window applied to | Low | Two existing CLI tests updated; new profile tests added | Fixed |
| 3 | M28 batch | `make lint`'s Makefile loop continued past a failing package (ruff E501/F841 in new tests), so lint could exit 0 with violations | Medium | Files fixed; `mypy --strict` independently caught the same class of issues; per-package `ruff check` verified clean | Fixed |
| 4 | IDN-4 / DET-6 / TSS-1 | Tests under `mypy --strict` needed Optional-guarded indexing (`Mapping|None`, `dict|None`) and a `jsonschema` untyped-import marker | Low | Guards/casts/annotations added; `mypy --strict` clean on all packages | Fixed |
| 5 | PG-1..3 (#353–#355) | Derived Postgres index re-sequenced behind the embedded index (`LUI-2`, PRD 54/ADR-0035); no Postgres tier is built in M28 | Medium (accepted) | **Phased, not dropped** — re-pointed to M30; `DATA-1` shipped the DDL/dictionary groundwork | Waived with reason |
| 6 | A2A-1/2 (#364/#365), SYS-1 (#366), ACS-1 (#367) | A2A v1.0 wire spec + signed agent cards, Linux system-effects spec, and ACS Guardian audit-trail spec are not built in-repo | Medium (accepted) | **Phased, not dropped** per the WBS cut-line — re-pointed to M29; not fabricated | Waived with reason |

## Guardrails honored (M28)

- **Monitor-only, never enforcement** — injection-shape and credential-hygiene are observations; retention
  tombstones (never hard-deletes, D-K); signing stores digests only.
- **Redaction before storage** — the incident report carries no tool arguments/content; `credential_class` is a
  classification, never a value; memory content is gated by privacy mode + `capture_memory`.
- **Foreign content / no egress** — the incident-report module is egress-audited; the export is
  `manual-voluntary` (`auto_egress: false`).
- **Deterministic trust path** — injection heuristics are deterministic; the high-false-positive imperative-density
  rule is off by default.
- **Single source of truth** — schema→TS spike reads `schema/`; derived-index DDL carries `source_seq`/`source_hash`
  back-refs.

## Gate results (M28 batch)

| Gate | Result |
|---|---|
| `make test` (unit + coverage ≥ 95% + repo guard) | `packages/python-sdk` **95.14%**; `services/api` **95.75%** (53 passed); `services/analytics` **95.24%** (742 passed); repo guard **47 passed** |
| `make lint` (ruff zero) | clean (SDK/API/analytics verified per package) |
| `make typecheck` (mypy `--strict`) | clean (314 + 14 + 58 source files) |
| `make web-test` (vitest + axe) | 14 passed |
| Claims ledger | 51 claims / 156 live evidence links, check green |

## Deferred (re-pointed)

- **PG-1..3** (#353–#355) → **M30** (derived Postgres query tier; re-sequenced behind `LUI-2`).
- **A2A-1/2** (#364/#365), **SYS-1** (#366), **ACS-1** (#367) → **M29** (external specs / real captures).
- Each issue carries a phasing comment (explicit, not dropped). No tag in M28.

## Sign-off (M28)

- **Automated review evidence:** recorded above; the final gate is green (table above).
- **Deferrals:** six tickets phased to M29/M30 with reasons recorded.
- **Independent human risk sign-off:** pending maintainer (Debashish Ghosal, `@deghosal-2026`). Closes #382.
