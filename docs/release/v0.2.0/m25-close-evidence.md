# M25 (Foundations) — Milestone-close evidence

**BLUF:** The evidence artifacts the [M25 WBS](../../wbs/v0.2.0/wbs-v0.2.0-part1-foundations.md) requires at
close, each with the command that produced it and where the artifact lives. Milestone closure still awaits the
**25.R human risk sign-off** (`codereview-log.md`).

Branch: `feat-v0.2.0` · Review: [codereview-log.md](../../wbs/v0.2.0/codereview-log.md) · Commits: `d96f190`…`a4f4fad`.

## Evidence artifacts

| # | WBS artifact | Command / source | Result | Location |
|---|---|---|---|---|
| 1 | AAT export fixture + validation log | `pytest packages/python-sdk/tests/test_aat.py tests/test_aat_fuzz.py`; `agentwatch export-session <id> --format aat` | bundles validate; tamper detected; `verify_aat` fails closed | `a4f4fad`; `agentwatch.aat` |
| 2 | **OTel agent-span tree in a reference backend** | `docker compose up -d jaeger otel-collector` then `PYTHONPATH=packages/python-sdk/src python3 scripts/m25_otel_backend_evidence.py` | tree rendered from Jaeger API, trace `c8f563d588fb2574ad239bfceef38b32`, service `agentwatch-m25-evidence` | [m25-otel-agent-span-tree.md](m25-otel-agent-span-tree.md) + [.json](m25-otel-agent-span-tree.json) |
| 3 | Identity property-test output | `pytest packages/python-sdk/tests/test_redaction_properties.py tests/test_records.py`; `apply_identity_privacy` | principal hashed by default; identity fields never carry secrets | `agentwatch.identity` |
| 4 | Streaming drop-consumer report | `pytest packages/python-sdk/tests/test_streaming.py tests/test_m25_integration.py` | consumer crash/overflow loses no stored record; `degraded` surfaced; chain intact | `1eeefda`, `dda68f9` |
| 5 | Cursor/Gemini conformance-pack results | `pytest packages/python-sdk/tests/test_conformance_packs.py tests/test_conformance_runner.py tests/test_cursor_adapter.py` | runner green; packs populated; `--self-test` proves a broken adapter fails | `tests/fixtures/{cursor,gemini-cli}`, `tests/testkit/` |
| 6 | SDK flush/crash test log | `pytest packages/python-sdk/tests/test_sdk.py` | `flush` bounded, `shutdown` at-most-once, no-op-after-shutdown, context-manager flush | `405b613` |
| 7 | `replay-fixtures --self-test` output | `pytest packages/python-sdk/tests/test_conformance_runner.py::test_self_test_proves_a_broken_adapter_fails` | `conformance.self_test()` returns true (negative control) | `405b613` |
| 8 | ADR-0026 decision record | file | full-rename at v0.2.0 decided (launch-blocking) | [ADR-0026](../../adr/0026-naming-decision.md) |

## Milestone exit criteria

| Criterion | Result |
|---|---|
| All tests pass · coverage ≥ 95% · lint strict clean · WBS + issues updated · pushed to `feat-v0.2.0` | ✅ suites pass; coverage python-sdk **95.18%** / api **99.58%** / analytics **97.67%**; `make lint` + `make typecheck` clean; pushed |
| All relevant documents updated at close-out | ✅ 25.D (`54dc137`) swept PRDs 41/42/46/47, design + reference docs, README, CHANGELOG |
| AAT validates; OTel agent-span tree renders; identity property green; streaming survives a consumer crash; Cursor/Gemini conformance packs registered; SDK flush proven | ✅ artifacts 1–7 above |
| NAM-1 complete and ADR-0026 decided | ✅ `agentwatch.naming` guard + FAQ + ADR-0026 |

## Accepted gap

- **CUR-1 live capture (Cursor `live-verified`)** — waived; Cursor ships a native-hooks adapter on the published
  contract with a version-tagged, licensed, secret-scanned corpus (`tests/testkit/`, provenance in
  `PROVENANCE.md`), so the compatibility row is **`fixture-verified`**. Reaching `live-verified` still requires a
  consented capture from a real authenticated Cursor install (tracked on #303).

## Reproduce the backend evidence

```sh
docker compose up -d jaeger otel-collector
PYTHONPATH=packages/python-sdk/src python3 scripts/m25_otel_backend_evidence.py
# writes m25-otel-agent-span-tree.{json,md}; Jaeger UI: http://localhost:16686
```
