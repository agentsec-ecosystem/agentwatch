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
