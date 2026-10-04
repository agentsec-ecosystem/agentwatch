# M16 — Coverage & Recorder Trust (PRD 32) Implementation Plan

> **For agentic workers:** Work task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Answer "did you capture everything?" — reconcile the store against an independent
ground truth (`coverage`), record the recorder's own state transitions in the chain, detect harness
drift from real traffic, give operators tools for the quarantine, archive old chain segments, and
publish the anti-forensics matrix that treats the recorder as an attack target.

**Architecture:** Mostly read-side/derived work plus a small amount of new capture. New module
`recorder_state.py` (S5 markers + coverage windows), `harness_drift.py` (S19 observation),
`coverage.py` (S2 reconciliation), `archive.py` (S28 segment sealing). The quarantine tools (S27)
extend the existing `quarantine.py` and CLI. The attack suite (S30) is tests + a docs matrix; no
enforcement. One new store envelope shape: the **anchor record** and segment file (S28), reusing the
existing chain rules.

**Tech Stack:** Python 3.10+; `pytest` + `pytest-cov` (≥95%); `ruff`; `mypy --strict`. No new
runtime dependency.

**Spec:** PRD [32](../prd/32-coverage-and-recorder-trust.md) · WBS
[Part 10](../wbs/v0.1.0/wbs-v0.1.0-part10-trust-and-investigation.md) · issues #238–#243.

## Global Constraints

- Fail closed, never silent (PRD 17); redaction before storage (DD-06); no egress by default (NFR-9).
- Marker records are metadata-only, agentwatch-authored (`MARKER_PRODUCER`), append-only.
- The A5 transcript read path is reused **verbatim** and must never read content — same canary test.
- Coverage ≥95%, `ruff` zero, `mypy --strict` clean. Run tests from `packages/python-sdk`.
- `gap:unexplained` must be zero on clean fixtures; every read that crosses a missing archive reports
  it **present-but-unavailable**, never empty.

## Review Focus

1. `coverage` classifies every gap by cause and never collapses "unknown" into 100%.
2. Recorder-state transitions leave chain records; a deliberate uninstall is visible.
3. A missing archive never silently narrows `search`/`replay`/`verify`.
4. The drift canary records **field names only**, allow-listed and capped, never a value.

---

## Tasks

### Task 1 — S5 (#239): Recorder-state audit records
- [x] `recorder_state.py`: `recorder-installed`/`recorder-uninstalled`/`config-changed`/
      `privacy-mode-changed`/`retention-changed`/`export-configured`/
      `coverage-window-open`/`coverage-window-close` markers (metadata-only, secrets masked).
- [x] `reconcile_config(store, cfg)` appends a marker per changed key; identical state is coalesced.
- [x] `coverage_windows(store)` reader; open-ended window (no close) reported as open, not complete.
- [x] Wire `init`/`uninstall` to append markers + open/close the coverage window.
- [x] Tests `tests/test_recorder_state.py`: each transition one marker; coalesce; no secret value;
      window read; open-ended window.
- [ ] S2 reads the coverage window and cites drift (lands with Task 3).

### Task 2 — S19 (#240): Harness-drift canary
- [x] `harness_drift.py`: `unknown_event_fields()`/`DriftTracker` (allow-listed names, capped,
      debounced), `harness-drift` metadata-only observation, `harness_drift_observations()` reader.
- [x] Adapter/daemon observe live frames; forward unknown hook phases instead of dropping them.
- [x] `doctor` and `/healthz` surface drift; `coverage` cites it as `gap:harness-drift` (Task 3).
- [x] Tests `tests/test_harness_drift.py`: unknown field -> one debounced observation naming the
      field and no value; repeat in-session does not duplicate; additive framed as additive.

### Task 3 — S2 (#238): `agentwatch coverage`
- [x] `coverage.py`: reconcile transcript tool calls vs store records per project/session; classify
      `gap:daemon-down`/`gap:quarantined`/`gap:trust-gated-headless`/`gap:hook-not-installed`/
      `gap:transcript-format-drift`/`gap:harness-drift`/`gap:unexplained`.
- [x] Extend the A5 extractor (`transcript.extract_tool_calls`) verbatim discipline: counts + names
      only; no transcripts -> "unknown", never 100%.
- [x] CLI `agentwatch coverage [--since] [--project] [--session] [--transcripts] [--json]`; reads S5
      coverage windows.
- [x] Tests `tests/test_coverage.py`: seeded gap of each class classified; unexplained zero on clean;
      transcript-content canary.

### Task 4 — S27 (#241): Operator tooling for the quarantine
- [x] `quarantine.py`: stable ids, `list_entries`, `inspect_entry`, `requeue_entries` through the
      adapter, `clear_entries`.
- [x] CLI `agentwatch quarantine list|inspect <id>|requeue [--all]|clear --yes`; `inspect` redacted by
      default, `--raw` gated and recorded as a `store-access` (`quarantine-inspect`).
- [x] Tests `tests/test_quarantine_tools.py`: requeue after a fix; redacted default; gated raw;
      `clear` without `--yes` refused; still-failing entry stays quarantined with a new reason.

### Task 5 — S28 (#243): Seal and archive old segments
- [x] `archive.py`: `agentwatch archive --before DATE [--out DIR]` moves a chain prefix into a sealed
      segment, leaves one anchor record (segment id, range, hash, count), independently verifiable.
- [x] `verify-store` verifies archives; `search`/`replay` read archives when present; missing archive
      = present-but-unavailable; hash disagreement surfaced; restore consumes the anchor.
- [x] Tests `tests/test_archive.py`: archive then verify; anchor preserves range; moved-away archive
      reported unavailable; replay/search across the boundary reads both.

### Task 6 — S30 (#242): Treat the recorder as an attack target
- [x] `tests/test_anti_forensics.py`: kill daemon / truncate store / strip hooks / exhaust disk /
      hold socket / move store / skew clock / replay stale frames — assert the documented outcome.
- [x] `docs/design/recorder-attack-matrix.md`: preventable vs detectable-after-the-fact vs neither,
      each row naming the command that evidences it; linked from the threat model and traceability doc.
- [ ] Docs updated: PRD 32 status, PRD 22, PRD 06, CLI reference, WBS status, CHANGELOG (verification pass).

---

## Progress log

- 2026-10-03 — plan created; starting Task 1 (S5).
- 2026-10-03 — **Task 1 (S5) code complete.** `recorder_state.py` (8 marker tools, coalescing,
  coverage-window pairing, `reconcile_config`), wired into `init`/`uninstall`; tests
  `tests/test_recorder_state.py` (12). SDK 1045 passed / 1 skipped, `ruff` clean, `mypy --strict`
  clean. Next: Task 2 (S19 harness-drift canary).
- 2026-10-03 — **Task 2 (S19) code complete.** `harness_drift.py` (allow-listed/capped names,
  session + cross-session debounce, restart seeding), daemon observation + unknown-phase forward,
  `/healthz` `drift` block, `doctor` `harness-drift` check; tests `tests/test_harness_drift.py` (13)
  plus daemon/doctor/health updates. SDK 1061 passed / 1 skipped, `ruff`/`mypy --strict` clean.
  Next: Task 3 (S2 `agentwatch coverage`).
- 2026-10-03 — **Task 3 (S2) code complete.** `transcript.extract_tool_calls` (A5 allow-list
  extension, counts + names only), `coverage.py` (reconciliation + 7-class gap classification +
  S5 window read), `agentwatch coverage`; tests `tests/test_coverage.py` (25 with the transcript
  tests). SDK 1083 passed / 1 skipped, `ruff`/`mypy --strict` clean. Next: Task 4 (S27 quarantine).
- 2026-10-03 — **Task 4 (S27) code complete.** `quarantine.py` stable ids + list/inspect/requeue/clear,
  `quarantine-inspect` added to the S21 access allow-list, `agentwatch quarantine …` CLI; tests
  `tests/test_quarantine_tools.py` (15). SDK 1096 passed / 1 skipped, `ruff`/`mypy --strict` clean.
  Next: Task 5 (S28 archive).
- 2026-10-03 — **Task 5 (S28) code complete.** `archive.py` (sealed segment + anchor + independent
  verify + boundary-aware combined records + restore), `agentwatch archive`, `verify-store` archive
  verdicts, archive-aware `search`/`replay`; tests `tests/test_archive.py` (10). SDK 1107 passed /
  1 skipped, `ruff`/`mypy --strict` clean. Next: Task 6 (S30 attack suite + matrix).
- 2026-10-03 — **Task 6 (S30) code complete.** `tests/test_anti_forensics.py` (11) covering all eight
  scenarios, `docs/design/recorder-attack-matrix.md` published + linked from the threat model and
  traceability doc. Next: M16 verification pass (docs, WBS/index, CHANGELOG, close #238–#243).
