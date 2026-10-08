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

## Review checklist (M28)

| Item | Verification | Verdict |
|---|---|---|
| ADR-0019 — derived-index invariant | `DATA-1` DDL carries `source_seq`/`source_hash` back-refs on every table and the header states the chain is the source of truth; `tests/test_derived_index_ddl.py` guards it. `PG-1..3` are phased (no Postgres tier in M28), so nothing bypasses the chain | ✅ upheld |
| ADR-0020 — identity hashing | `IDN-4` exports the credential **class** only (`agentwatch.credential_class`), never a value; `principal`/`delegation_chain` hashing is unchanged, and the `agentwatch.credential_class` attribute is a classification | ✅ upheld |
| ADR-0024 — foreign data | `COR-3`/`COR-4` add registry-facing artifacts; the incident report is redacted and egress-audited (`test_module_has_no_egress_path`), fixtures are shape-synthesized and cited, no reader executes foreign content | ✅ upheld |
| ADR-0025 — A2A recorded-not-trusted | `A2A-1/2` are phased; the identity mapping states a card-verification outcome is recorded `verified`/`unverified` and is **never** treated as authorization | ✅ upheld (phased) |
| Phased items listed + re-pointed | `PG-1..3` → M30; `A2A-1/2`, `SYS-1`, `ACS-1` → M29; each issue carries a phasing comment | ✅ recorded |
| Registry export is human-initiated only | Incident report `submission.mode = manual-voluntary`, `auto_egress: false`; no submission anywhere is automatic | ✅ upheld |

## Sign-off (M28)

- **Automated review evidence:** recorded above; the final gate is green (table above).
- **Deferrals:** six tickets phased to M29/M30 with reasons recorded.
- **Independent human risk sign-off:** ✅ **approved** by the maintainer (Debashish Ghosal, `@deghosal-2026`)
  on **2026-10-06** — the review checklist above is verified, the six findings are fixed or waived with reasons,
  and the deferrals are accepted. Closes #382.

## Code review & risk sign-off (M29)

**Scope:** all 17 M29 feature tickets plus the four M28 tickets re-pointed into M29 (A2A-1/2, SYS-1, ACS-1),
merged into `feat-v0.2.0` one worktree at a time, plus 29.T/29.D/29.R.

### Gate (merged HEAD)

| Check | Evidence |
|---|---|
| `make lint` (ruff zero) | clean (SDK/API/analytics per package) |
| `make typecheck` (mypy `--strict`) | clean (362 + 14 + 58 source files) |
| `make test` (unit + coverage ≥ 95% + repo guard) | `packages/python-sdk` **2210 passed, 2 skipped, 95.76%**; `services/api` **53 passed, 95.75%**; `services/analytics` **742 passed, 96.22%**; repo guard **47 passed** |
| Claims ledger | `scripts/check_claims.py` green |

### Review checklist

| Item | Verification | Verdict |
|---|---|---|
| ADR-0027 — authorization taxonomy v2 | `authorization.{source,deny,evidence}` is additive/metadata-only; legacy S14 `approval` mapped at read time by `effective_authorization`; no value inferred from `outcome=ok`; a classifier/bypass call is never `user`/`rule` (`tests/test_authorization.py`, `test_claude_otel.py`) | upheld |
| ADR-0028 / ADR-0029 — managed install + attestation | `doctor` returns `effective | blocked by managed policy | unknown` and never "installed" under managed policy; attestation carries digests/booleans only (property test) | upheld |
| ADR-0030 — hook wall-clock budget | `scripts/hook_perf_gate.py` + workflow gate macOS/Linux against a committed baseline; Windows leg declared blocked on WIN-1 | upheld (Windows declared) |
| ADR-0031 — native-telemetry join | hook↔OTel join by `tool_use_id`; disagreements are classified discrepancies; `coverage` reports joined/hook-only/otel-only/discrepancies; redaction on ingest, B4 quarantine | upheld |
| ADR-0025 — A2A recorded-not-trusted | agent-card verification outcome recorded `verified`/`unverified`; `agent-delegation` is evidence-only, never an authorization verdict | upheld |
| ADR-0040 / ADR-0041 — fleet roles + legal hold | least-privileged default; cross-role read returns nothing and is `store-access`-recorded; held records survive retention/purge/rebuild; `purge` fails closed without a recorded reason | upheld |
| Guardrails | monitor-only, local-first, no egress without opt-in, redaction-before-store, deterministic trust path, no LLM in the trust path; identity hashed by default | upheld |

### Declared, honest blocks

- DEP-1/DEP-3 Windows runtime leg → **WIN-1 (M31)**; macOS/Linux measured and gated.
- EXT-3 `capability-changed` → forward-compatible placeholder pending **M30 CAP-2**.
- ASI-1 rows requiring **M30 CAP-1** / SBX are stated `not evidenced` with the dependency named.
- FWK-1/2 live pinned framework runs blocked (not installable in CI); fixture-driven conformance shipped.

### Sign-off (M29)

- **Automated review evidence:** the gate above is green; no unresolved findings.
- **Risk sign-off:** approved for milestone closure by the maintainer (Debashish Ghosal, `@deghosal-2026`), 2026-10-06;
  closure recorded on #457. Closes #457.

## Code review & risk sign-off (M30)

**Scope:** all 27 M30 feature tickets (#458–#484) plus M26 **UI-1 (#428)** re-pointed into M30, the four PG tickets
re-pointed out to v0.2.x, and 30.T/30.D/30.R. Delivered by **six partitioned workstreams** (WS-1..WS-6) with disjoint
module ownership and reserved claim/ADR/fixture namespaces; each branch merged into `feat-v0.2.0` **one worktree at a
time** (WS-6 → WS-4 → WS-3 → WS-2 → WS-1 → WS-5), conflicts resolved to the union of the additive shared files
(`cli/main.py` auto-merged throughout; the claims ledger was rebuilt as a real union and its table regenerated), and
re-verified on the merged HEAD.

### Gate (merged HEAD, `feat-v0.2.0`)

| Check | Evidence |
|---|---|
| `make test` (unit + coverage ≥ 95% + repo guard) | `packages/python-sdk` **2473 passed, 2 skipped, 95.26%**; `services/api` **53 passed, 95.75%**; `services/analytics` **742 passed, 96.28%**; repo guard **47 passed** |
| `make lint` (ruff zero) | clean (SDK/API/analytics per package) |
| `make typecheck` (mypy `--strict`) | clean |
| `make web-test` (vitest + axe) | green |
| Claims ledger | `scripts/check_claims.py` green — **105 claims / 417 live evidence links** |
| Browser verifier | `scripts/build_browser_verifier.py --check` — checksum OK |

### Review checklist

| Item | Verification | Verdict |
|---|---|---|
| ADR-0032 — capability inventory scope / digest / no-content | digests are sha256 of **content**, never the declared pin; content never retained (property test); per-harness coverage honest (`exposed`/`partial`/`none`) | upheld |
| ADR-0033 — content-free range+hash | `provenance.capture_ranges` stores ranges + keyed hashes, never content/diff; `is_content_free` + property + attack pack | upheld |
| ADR-0034 — Agent Trace pin + write policy | pinned-revision bundle, zero code content; repo written only by explicit `--write-notes` | upheld |
| ADR-0035 — embedded index tier + PG re-sequence | stdlib `sqlite3`, deletable, rebuilds **bit-for-bit**; no heavyweight dep; PG re-sequenced (EXT-8) | upheld |
| ADR-0036 — console security | loopback-only bind, per-launch token, Host-header check, read-only / no mutation endpoints / no egress (enumerated by tests) | upheld |
| ADR-0037 — MCP read-only server | tool set enumerated by test; untrusted labeling + citations; `store-access` recorded; off by default | upheld |
| ADR-0038 — policy suggestion boundary | no write outside `--out`; every rule evidence-linked; destructive/network/credential never allow-by-default | upheld |
| ADR-0039 — runner segment custody | imported records visibly weaker; tampered segment fails and is not imported; join by `traceparent` only | upheld |
| ADR-0042 / ADR-0043 — environment / memory | digests only (`env1:<sha256>`); out-of-band memory edit flagged `unattributed` | upheld |
| ADR-0044 — browser verifier trust | offline, zero-network; verdicts equal CLI; signed at release (key never committed) | upheld |
| Guardrails | monitor-only, local-first, no egress without opt-in, redact-before-store, deterministic trust path, no LLM in the trust path; identity hashed by default | upheld |

### Declared, honest gaps

- **SBX-1** Cursor raw-hook `sandbox` capture (adapter not owned by that stream) — the published matrix states
  `cursor partial` rather than inferring.
- **CAP-3 / MEM-1** load / memory exposure is `claude-code partial` (loads are API-driven; no session-start hook yet).
- **LUI-1** clean-install ≤60 s wall-clock is the M31 field test `FT-LUI-1`; functional acceptance met.
- **PRV-3** end-to-end hook persistence under `metadata-only` routes through the record/redaction path (owned by the
  schema stream) and is declared, not silently assumed.
- `suggest-policy` quality is bounded by captured arguments; `what-if` is a labeled simulation over recorded calls.

### Sign-off (M30)

- **Automated review evidence:** the gate above is green on the merged HEAD; no unresolved findings.
- **Deferrals:** PG-1..3 (#353–#355) re-pointed to v0.2.x (ADR-0035/EXT-8) with phasing comments; nothing dropped.
- **Risk sign-off:** automated review complete; independent human risk sign-off recorded by the maintainer on closure
  of #487 (2026-10-08). Closes #487.
