# M21 — Configuration, Profiles & Capture Hygiene (PRD 37) Implementation Plan

**Goal:** Make the recorder legible and safe: `config explain` (S34), install profiles (S35), a
pathological-record guard (S36), a read-time SDK/hook union (S11), and a standalone redactor (S13).

**Spec:** PRD [37](../prd/37-config-and-capture-hygiene.md) · WBS
[Part 12](../wbs/v0.1.0/wbs-v0.1.0-part12-interop-and-config.md) · issues #265–#269.

## Tasks

### Task 1 — S34 (#265): `config explain`
- [x] `config_explain.py`: layered origins, winning layer, overrides, `--diff`, never a secret value.
- [x] CLI `config explain [KEY] [--diff] [--json]`.
- [x] Tests `tests/test_config_explain.py`.

### Task 2 — S35 (#266): install profiles
- [x] `profiles.py`: `solo | team | compliance | ci`, validated, printed consent-first.
- [x] CLI `init --profile NAME` (+ `--set` wins); `config-changed` recorded.
- [x] Tests `tests/test_profiles.py`.

### Task 3 — S36 (#267): pathological-record guard
- [x] `guard.py` + `truncated` record marker + config `limits`; applied on append.
- [x] Receipts show the truncation rule. Tests `tests/test_guard.py`.

### Task 4 — S11 (#268): read-time SDK/hook union
- [x] `union.py`: `source` field, read-only composition, chain-protection stated.
- [x] CLI `union [--session-id] [--source] [--json]`. Tests `tests/test_union.py`.

### Task 5 — S13 (#269): standalone redactor
- [x] `redactor.py`: `redact(text|value, mode) -> (masked, findings)`; findings never a value.
- [x] CLI `redact --mode` stdin/stdout filter. Tests `tests/test_redactor.py`.

### Task 6 — Docs, exit criteria
- [x] PRD 37, WBS M21, index, CLI reference, CHANGELOG, record-format spec, schema.
- [x] Full suite + coverage; lint; commit; push; close #265–#269.

## Progress log

- 2026-10-03 — plan created; starting Task 1 (config explain).
- 2026-10-03 — all tasks implemented; SDK 1338 passed / 1 skipped, coverage 95.20%, ruff + mypy
  clean. Docs updated, issues #265-#269 closed.
