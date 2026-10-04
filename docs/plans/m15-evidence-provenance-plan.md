# M15 — Evidence & Provenance (PRD 31) Implementation Plan

> **For agentic workers:** Work task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn stored records into **artifacts a third party can trust off-machine**: a self-contained,
offline-verifiable evidence bundle, a standalone dependency-free verifier, an Agent Bill of Materials,
a schema-level `producer` provenance field, a store-access audit trail, operator annotations, and
redaction receipts.

**Architecture:** Read-side/derived work only — no new capture path, enforcement, or egress. New modules
under `packages/python-sdk/src/agentwatch/` (`provenance`, `annotate`, `evidence`, `bom`, `receipts`),
new CLI verbs, and one additive record-schema change (`producer`, S26). Bundle format is versioned and open.

**Tech Stack:** Python 3.10+; `pytest` + `pytest-cov` (≥95%); `ruff`; `mypy --strict`. No new runtime
dependency (S12 verifier is stdlib-only; S9 BOM is hand-rendered CycloneDX JSON).

**Spec:** PRD [31](../prd/31-evidence-and-provenance.md) · WBS
[Part 9](../wbs/v0.1.0/wbs-v0.1.0-part9-rigor-and-evidence.md) · issues #231–#237.

## Global Constraints

- Fail closed, never silent (PRD 17); redaction before storage (DD-06); no egress by default (NFR-9).
- Read-only on the store except for the audit/marker records S21/S20 are *documented* to append.
- Coverage ≥95%, `ruff` zero, `mypy --strict` clean. Run tests from `packages/python-sdk`.
- `producer` is additive: legacy stores read as inferred `hook` and are never rewritten silently.

## Review Focus

1. The three verdicts (intact / complete / leak-free) are reported **independently**, never collapsed.
2. A bundle is verifiable **offline with no store and no Python env** (S12 stdlib zipapp), and a tampered
   member fails.
3. Receipts name rules and field paths, **never values**; `redact --preview` leaves the store byte-identical.

---

## Tasks

### Task 1 — S26 (#234): A `producer` field on every record  ✅ COMPLETE
- [x] Add `Producer` + `ProducerKind` to `records.py`; serialize/validate; reject unknown kind (F8).
- [x] Add `producer` to the allowed record fields and `schema/agent-record.schema.json` (additive).
- [x] `effective_producer(record)` infers `hook` for legacy records; never written back silently.
- [x] Tag construction sites: hook (Claude Code), import, event, ingest, proxy, sdk (modeled/soak/markers).
- [x] `search --producer` filter.
- [x] Tests added: round-trip, legacy inferred `hook`, unknown kind rejected (`tests/test_producer.py`).
- [x] Update adapter/golden expected fixtures (35 files) — guarded so the *only* change is `producer`.
- [x] Docs: `record-format-spec.md`, `cli-reference.md`.
- [x] Green: SDK 959 passed / 1 skipped, coverage 95.30%, `ruff` clean, `mypy --strict` clean; repo guard
      26, analytics 706, API 42.
- [ ] S1/S2 report per-producer counts (deferred to their tasks).

### Task 2 — S20 (#236): `agentwatch annotate`
- [x] `agentwatch annotate <session-id> --note "…" [--tag NAME]` writes a metadata-only `operator-note`.
- [x] Redact + length-cap the note before storage; empty note rejected.
- [x] `sessions --tag` filter; purge-marker edge case. (findings section deferred to S1)
- [x] Tests: round-trip, tag filter, secret masked, purged-session context.

### Task 3 — S21 (#235): Log reads of the store
- [x] Append metadata-only `store-access` records for `export`, `export-session`, `evidence`, `bom`.
- [x] Record timestamp/command/scope/destination-kind; failed export records `attempted` + error.
- [x] `search`/`view`/`replay` append none; `verify-store` stays green.
- [x] Tests: exactly one record per allowed command, none for reads.
- Note: `export`/`evidence`/`bom` call sites land with their own tasks; the allow-list + API are in place.

### Task 4 — S32 (#237): Redaction receipts
- [x] `replay <id> --receipts` and a `receipt` block on `--json` (fields kept/dropped + rule id).
- [x] `agentwatch redact --preview SAMPLE` (before/after, stores nothing).
- [x] Field paths + rule ids only, never values.
- [x] Tests: masked secret + dropped arg both listed; `--preview` byte-identical store.

### Task 5 — S9 (#233): `agentwatch bom` (CycloneDX)
- [x] `agentwatch bom [--session-id ID | --project PATH | --machine] --format cyclonedx|json`.
- [x] Components: models, MCP servers (+ tool-surface digest), prompt/ruleset digests, harness, agentwatch.
- [x] Mandatory `coverage` field ("observed", window, non-claims); unknown model kept by name, no version.
- [x] Tests: validates against CycloneDX shape; `coverage` present; "none observed" case.

### Task 6 — S1 (#231): `agentwatch evidence` bundle
- [x] `agentwatch evidence <session-id> [--out bundle.zip] [--include-bom] [--redact-paths]`.
- [x] Members: `manifest.json`, `records.ndjson`, `chain.json`, `verify.json`/`.txt`, `privacy.json`,
      `coverage.json` (per-producer counts), `inventory.json`/`bom.cdx.json`, `findings.json`
      (operator notes, S20), `summary.md`, `SCHEMA/`.
- [x] `agentwatch evidence verify bundle.zip` re-verifies offline; tampered member fails.
- [x] Tests: round-trip offline; three verdicts independent; tombstone/purge/broken-chain edge cases.
- Note: `coverage.json` is a minimal complete-verdict until S2 (M16) lands the full reconciliation; it now
  carries the per-producer counts S26 (#234) asks S1 to report. `findings.json` satisfies S20's
  "S1 bundles include notes as a findings section".

### Task 7 — S12 (#232): Standalone dependency-free verifier
- [x] `agentwatch-verify` stdlib-only zipapp + docs reference implementation.
- [x] Both run the Q6 conformance vectors in CI; tampered vectors fail both.
- [x] Unknown bundle format version rejected with the version named.
- [x] Tests: shipped + reference verifiers agree on bundle vectors and the Q6 table.
- Files: `scripts/agentwatch_verify/{__main__,reference}.py`, `scripts/build_verify_zipapp.py`,
  `docs/reference/evidence-verifier.md`, `tests/test_verify_zipapp.py`.

---

## Progress log

- 2026-10-03 — plan created; starting Task 1 (S26).
- 2026-10-03 — **Task 1 (S26) complete.** `producer` schema field + validation + legacy inference +
  `search --producer`; 35 adapter/golden fixtures updated; docs updated. All SDK/analytics/API/repo-guard
  suites green; coverage 95.30%. Next: Task 2 (S20 annotate).
- 2026-10-03 — **Task 2 (S20) complete.** `annotate` + `operator_notes`/`tagged_sessions` +
  `sessions --tag`; tests `tests/test_annotate.py`. SDK 971 passed, coverage 95.36%.
- 2026-10-03 — **Task 3 (S21) complete.** `store_access` allow-list + `record_store_access` wired into
  `export-session`; tests `tests/test_store_access.py`. SDK 978 passed, coverage 95.37%.
  Next: Task 4 (S32 redaction receipts).
- 2026-10-03 — **Task 4 (S32) complete.** `receipts.py` (`record_receipt`/`session_receipts`/
  `redact_preview`) + `replay --receipts/--json` + `redact --preview`; tests
  `tests/test_receipts.py`. SDK 991 passed, coverage 95.05%. Next: Task 5 (S9 BOM).
- 2026-10-03 — **Task 5 (S9) complete.** `bom.py` (observed CycloneDX 1.5 + coverage) +
  `agentwatch bom`; tests `tests/test_bom.py`. SDK 1004 passed, coverage 95.37%.
  Next: Task 6 (S1 evidence bundle).
- 2026-10-03 — **Task 6 (S1) complete.** `evidence.py` (bundle build/verify, three independent
  verdicts, redact-paths) + `agentwatch evidence [verify]`; tests `tests/test_evidence.py`.
  SDK 1015 passed, coverage 95.28%. Next: Task 7 (S12 standalone verifier).
- 2026-10-03 — **Task 7 (S12) complete — M15 code complete.** stdlib-only `agentwatch-verify` zipapp +
  published reference + build script + docs; both verifiers pass the bundle vectors and the Q6 store
  table; tests `tests/test_verify_zipapp.py`. SDK 1034 passed, coverage 95.23%.
  Remaining: WBS/index status update, CHANGELOG, close issues #231–#237.
- 2026-10-03 — **M15 verification pass.** Checked every issue against its stated behavior. Two
  requirements were unmet and are now fixed: S20's "S1 bundles include notes as a findings section"
  (new `findings.json` + a `## Findings` summary section) and S26's "S1 reports per-producer counts"
  (`coverage.json.producers`). Also fixed 21 real `mypy --strict .` errors in the M15 tests that
  `make typecheck` masked (its per-package loop returns only the last status). Tests
  `tests/test_evidence.py` (25). WBS/index status and issues #231–#237 closed.
