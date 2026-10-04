# M18 — Content-Flow Forensics (PRD 34) Implementation Plan

> **For agentic workers:** Work task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record two deterministic data-flow facts — where untrusted content came from before it was used
as an instruction (S22), and where an exposed secret went afterward (S23). Observation-only, local, and
keyed so the store holds no recovered content.

**Architecture:** A new `flow.py` owns the per-install HMAC key, shard fingerprinting, and the
`content-flow` observation. `secret_trace.py` links repeated `secret-detected` sightings by keyed
fingerprint and classifies the sink with the M17 classifier. The Claude Code adapter attaches secret
fingerprints to the `secret-detected` event (only when a key is available). New CLI verbs `flow` and
`secrets`. No record-schema change.

**Tech Stack:** Python 3.10+; `pytest` + `pytest-cov` (≥95%); `ruff`; `mypy --strict`. No new runtime
dependency.

**Spec:** PRD [34](../prd/34-content-flow-forensics.md) · WBS
[Part 11](../wbs/v0.1.0/wbs-v0.1.0-part11-forensics-and-context.md) · issues #253–#254.

## Global Constraints

- **A fact, not a verdict:** name it `content-flow`, never "injection"; no score, no block.
- Keyed HMAC (per-install key); the store holds only fingerprints, never recovered content.
- "No evidence of egress" is the honest phrasing — absence of a record is not proof of absence.
- Large responses are capped/sampled; a shard matching many sinks is capped with counts.
- Coverage ≥95%, `ruff` zero, `mypy --strict` clean. Run tests from `packages/python-sdk`.

## Review Focus

1. No raw content in an observation or in `agentwatch flow`/`secrets` output — fingerprints only.
2. Fingerprints are keyed and stable across sightings; an unkeyed run links nothing.
3. The flow edge is deterministic and independent of ordering beyond "source before sink".

---

## Tasks

### Task 1 — S22 (#253): content → argument flow capture
- [x] `flow.py`: per-install HMAC key (`ensure_key`/`hmac_key_or_none`), normalized word-n-gram shards,
      `detect_flows(records)`, `record_flow_observations`, `content_flow_observations`, `render_flows`.
- [x] CLI `agentwatch flow <id> [--record] [--json]`.
- [x] Tests `tests/test_flow.py`: fetched text reappears in a later shell argument → one edge; non-match →
      none; the stored observation holds no raw content.

### Task 2 — S23 (#254): trace an exposed secret
- [x] `secrets.fingerprint_spans` walks raw values and fingerprints detected spans.
- [x] Adapter attaches `fingerprints` to `secret-detected` evidence **only when a key is available**.
- [x] `secret_trace.py`: link sightings by fingerprint, classify sinks (S3), `rotate: recommended` vs
      `no evidence of egress`.
- [x] CLI `agentwatch secrets [--session-id] [--json]`.
- [x] Tests `tests/test_secret_trace.py`: echo into a network tool → recommended with path; single sighting
      → no evidence of egress; no value in output.

---

## Progress log

- 2026-10-03 — plan created; starting Task 1 (S22 flow capture).
