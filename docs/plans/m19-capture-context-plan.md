# M19 — Capture Context (PRD 35) Implementation Plan

> **For agentic workers:** Work task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the record's context: who authorized each call (S14), whether the context was
compacted (S15), what revision the agent acted on (S16), what OS principal it ran as (S29), and a
one-command `agentwatch demo` that proves the pipeline (S31).

**Architecture:** Two additive record fields (`approval`, `environment`), two new hook phases
(`Notification`, `PreCompact`), a new `context_snapshot.py` (git + principal + OS metadata), and a new
`demo.py` that drives synthetic events through the real adapter→redaction→store→chain path. New CLI verbs
`demo`; `search --approval`.

**Tech Stack:** Python 3.10+; `pytest` + `pytest-cov` (≥95%); `ruff`; `mypy --strict`. No new runtime
dependency.

**Spec:** PRD [35](../prd/35-capture-context.md) · WBS
[Part 11](../wbs/v0.1.0/wbs-v0.1.0-part11-forensics-and-context.md) · issues #255–#259.

## Global Constraints

- **Record `unknown` rather than infer** (PRD 35 discipline). A guessed approval is a false audit record.
- Additive only: legacy records read as `approval=unknown`, `environment=None`; never write back.
- Session-start enrichment never blocks and never captures env-var *values* or home paths.
- Demo data is never evidence: `producer.kind: demo`, excluded from coverage and bundles, self-cleaning.
- Coverage ≥95%, `ruff` zero, `mypy --strict` clean. Run tests from `packages/python-sdk`.

## Review Focus

1. Approval is `unknown` wherever the harness cannot prove user vs auto — never guessed.
2. No compaction payload / env-var value reaches the store; only allow-listed metadata.
3. A failing `git` / no TTY never blocks a hook (always exits 0) and degrades to `unavailable`/`headless`.
4. `demo --purge` leaves the store exactly as found (tombstones, chain intact).

---

## Tasks

### Task 1 — S16/S29 (#257, #258): session-start environment snapshot
- [x] `records.py`: add optional `environment` field (+ validation, schema, round-trip).
- [x] `context_snapshot.py`: `git_snapshot` (git｜none｜unavailable), `principal_snapshot`,
      `classify_context` (interactive|headless|ci), `environment_snapshot`, `filter_snapshot`.
- [x] `hook.py`: attach the snapshot to `session-start` (async path); update `_VALID_PHASES`.
- [x] Adapter: allow-list `environment` onto the session-start record; set `host`; honour
      `include_principal`.
- [x] Config: `privacy.include_principal` (default true) so metadata-only installs can drop it.
- [x] Tests `tests/test_context_snapshot.py`.

### Task 2 — S15 (#256): context compaction
- [x] `install.EVENT_PHASES` + `hook._VALID_PHASES`: `PreCompact` → `compact`.
- [x] Adapter: `context-compacted` metadata-only step; allow-listed trigger/tokens; unknown trigger →
      `unknown`; repeated compactions one step each; no payload content.
- [x] `coverage._NON_TOOL_NAMES`: add `context-compacted`.
- [x] Tests `tests/test_capture_context.py`.

### Task 3 — S14 (#255): approval provenance
- [x] `records.py`: `Approval` enum + optional `approval` field + `effective_approval`.
- [x] Adapter: `derive_approval`; `Notification` → `permission-prompt` marker; `denied` → `denied`.
- [x] Daemon: track a pending permission prompt per `tool_use_id` so the next `pre` is `user`.
- [x] `search --approval`; replay/view show approval.
- [x] Tests in `tests/test_capture_context.py` + daemon correlation.

### Task 4 — S31 (#259): `agentwatch demo`
- [x] `ProducerKind.DEMO`; `demo.py` synthetic events through the real adapter/store; chain verdict +
      redaction result; `--purge` tombstones the demo session.
- [x] `coverage`/`evidence` exclude `producer.kind: demo`.
- [x] CLI `demo [--purge] [--json]`.
- [x] Tests `tests/test_demo.py`.

### Task 5 — Docs, exit criteria
- [x] PRD 35 status, WBS M19, index, CLI reference, CHANGELOG, record-format spec, schema JSON,
      design doc for the approval derivation table.
- [x] Full suite + coverage; `ruff`/`mypy --strict`; commit; push; close #255–#259.

---

## Progress log

- 2026-10-03 — plan created; starting Task 1 (session-start environment snapshot).
- 2026-10-03 — all tasks implemented; SDK 1268 passed / 1 skipped, coverage 95.15%, ruff + mypy
  clean. Docs updated, issues #255–#259 closed.
