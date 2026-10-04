# M17 — Investigation & Impact (PRD 33) Implementation Plan

> **For agentic workers:** Work task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a recorded session into the answers an investigator asks: what changed in the world
(`impact`), who touched a file (`blame`), what happened in a time window (`at`), what it cost (`cost`),
what the subagents did (`tree`), whether a denial was followed by a workaround, a stable behavior
fingerprint, the human interrupt, and a local weekly digest.

**Architecture:** Pure **derived reads** over already-redacted records — no new capture, no enforcement,
no scoring, no egress. One new shared module `classify.py` (the deterministic argument classifier used by
S3/S18/S25), plus `impact.py`, `blame.py`, `fingerprint.py`, `cost.py` + `pricing.py`, `tree.py`,
`window.py`, `digest.py`, and a small session-state derivation for S33. New CLI verbs; no record-schema
change.

**Tech Stack:** Python 3.10+; `pytest` + `pytest-cov` (≥95%); `ruff`; `mypy --strict`. No new runtime
dependency.

**Spec:** PRD [33](../prd/33-investigation-and-impact.md) · WBS
[Part 10](../wbs/v0.1.0/wbs-v0.1.0-part10-trust-and-investigation.md) · issues #244–#252.

## Global Constraints

- Descriptive, never a verdict: no risk score, no severity, no "exfiltration" judgement (PRD 14).
- The classifier is deterministic and **published**: a versioned pattern table with
  `confidence: exact | heuristic` per entry and a surfaced `unclassified` bucket.
- Timezone: accept explicit offsets, default to local, echo the resolved UTC range (Q12).
- Unknown prices are reported `tokens only, price unknown`, never interpolated.
- Coverage ≥95%, `ruff` zero, `mypy --strict` clean. Run tests from `packages/python-sdk`.

## Review Focus

1. Facts only — every entry names the record it came from; no ranking.
2. `impact`/`blame`/`tree`/`at` never render an empty result when data is merely unavailable.
3. Behavior digest is versioned (`bd1:<sha256>`) and stable across reorderings of equivalent actions.

---

## Tasks

### Task 1 — S3 (#244): shared classifier + `agentwatch impact`
- [x] `classify.py`: versioned pattern table (files written/edited/deleted, side-effect commands, network
      destinations, VCS, credential-adjacent), each with `confidence: exact|heuristic`; `unclassified`.
- [x] `impact.py`: grouped/deduped footprint + blast-radius counts + "widest action".
- [x] CLI `agentwatch impact <id> [--json] [--since]`.
- [x] Tests `tests/test_impact.py`: two hand-derived footprints; reorder vs change distinguished;
      every classification carries exact/heuristic.

### Task 2 — S18 (#246): `agentwatch blame <path>`
- [x] `blame.py`: reverse index per path, newest first, session/agent/tool/outcome/time, `confidence`.
- [x] CLI `agentwatch blame <path> [--since] [--project] [--json]`.
- [x] Tests `tests/test_blame.py`: two sessions newest-first; heuristic shell match labelled; outside-project
      not falsely matched.

### Task 3 — S7 (#249): behavior fingerprint
- [x] `fingerprint.py`: `behavior_digest` over ordered `(server, name, step_type, outcome)`, `bd1:` version.
- [x] `sessions --group-by-behavior`.
- [x] Tests `tests/test_fingerprint.py`: identical sequences share; an added tool differs; version embedded.

### Task 4 — S6 (#252): `agentwatch cost`
- [x] `pricing.py`: versioned pricing table + as-of date; unknown model -> tokens-only.
- [x] `cost.py`: rollup `--by session|project|model|tool|day`, table version in output.
- [x] CLI `agentwatch cost …`.
- [x] Tests `tests/test_cost.py`: hand-derived dollars; unknown model tokens-only; version in `--json`.

### Task 5 — S17 (#245): `agentwatch tree <session>`
- [x] `tree.py`: parent -> subagent fan-out with counts/outcomes/duration/tokens; bounded depth.
- [x] CLI `agentwatch tree <id> [--json] [--by-cost]`.
- [x] Tests `tests/test_tree.py`: two parallel siblings; no-subagent root; orphan attached to root.

### Task 6 — S24 (#247): `agentwatch at <time>`
- [x] `window.py`: cross-session window, resolved UTC range echoed, activity/gap header.
- [x] CLI `agentwatch at "TIME" [--window 30m] [--json]`.
- [x] Tests `tests/test_window.py`: two sessions time-ordered; gap stated; offset echoed.

### Task 7 — S25 (#248): denied-then-retried sequences
- [x] `denials.py`: per-denial follow-up window (N calls), neutral `followed within N calls by …`.
- [x] Surface in `replay`, `impact`, and the evidence bundle.
- [x] Tests `tests/test_denials.py`: different-route retry surfaced; empty window stated.

### Task 8 — S33 (#250): capture the human interrupt
- [x] Session-state derivation: `completed`/`interrupted-by-user`/`errored`/`abandoned`/`unknown`.
- [x] Surface in `sessions` and `diff`.
- [x] Tests `tests/test_session_state.py`: explicit interrupt; no end -> abandoned; error -> errored.

### Task 9 — S37 (#251): `agentwatch digest`
- [x] `digest.py`: markdown with sessions, tool mix, cost, denials, security events, capture rate,
      notable sequences, inventory changes; empty window message.
- [x] CLI `agentwatch digest [--since 7d]`.
- [x] Tests `tests/test_digest.py`: seeded week names sessions/cost/gaps; nothing written/egressed.

---

## Progress log

- 2026-10-03 — plan created; starting Task 1 (S3 classifier + impact).
- 2026-10-03 — **Tasks 1–4 code complete**, Task 5 in progress:
  - S3 `classify.py` (versioned `cls1` pattern table, exact/heuristic) + `impact.py` + `agentwatch
    impact`; `tests/test_impact.py` (16).
  - S18 `blame.py` + `agentwatch blame`; `tests/test_blame.py` (7).
  - S7 `fingerprint.py` (`bd1:`) + `sessions --group-by-behavior`; `tests/test_fingerprint.py` (8).
  - S6 `pricing.py` (`pr1`, as-of) + `cost.py` + `agentwatch cost`; `tests/test_cost.py` (9).
  - S17 `tree.py` written; CLI wiring started (not yet tested).
- Remaining: Task 5 CLI+tests, Tasks 6–9 (`at`, denied-retry, session state, digest), then docs/WBS/
  CHANGELOG + issue close + full green run.
- 2026-10-03 — **All nine tasks complete.** M17 shipped: `classify.py` (`cls1`), `impact.py`, `blame.py`,
  `fingerprint.py` (`bd1:`), `pricing.py` (`pr1`) + `cost.py`, `tree.py`, `window.py`, `denials.py`,
  `session_state.py`, `digest.py`, new CLI verbs, and `docs/design/impact-classification.md`. SDK 1219
  passed / 1 skipped, coverage 95.30%, `ruff` + `mypy --strict` clean; analytics 706, API 42, repo guard
  26. Docs (PRD 33, WBS, index, CLI reference, CHANGELOG) updated; issues #244–#252 closed.
