# M11 — Fleet Aggregation (R13) + Trailing-Baseline Drift Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in, self-hosted **fleet aggregation** over multiple hosts, **trailing-baseline** drift-signal detection (not fixed thresholds), and **deployment correlation** — all local-first in the SDK, emitting drift as a new `drift-detected` security event.

**Architecture:** A record gains an optional `host` tag so a host's local store can be ingested into a self-hosted aggregate store (`agentwatch.fleet`). `agentwatch.drift` builds metric series from stored records, computes a *trailing* baseline (rolling mean/stdev, never a fixed multiplier), flags z-score deviations as `DriftSignal`s, converts them to `drift-detected` security events, and overlays deployment markers. Two CLIs (`agentwatch fleet`, `agentwatch drift`) expose it; nothing exits non-zero on a signal (signals only — PRD 14/30).

**Tech Stack:** Python 3.10+ stdlib only (`dataclasses`, `statistics`, `json`, `argparse`); `pytest` + `pytest-cov` (≥95%); `ruff`; `mypy --strict`.

**Spec:** WBS [Part 6](../wbs/v0.1.0/wbs-v0.1.0-part6-expansion.md) M11 · PRD [05](../prd/05-features.md) R13 · PRD [30](../prd/30-analytics-signals.md) · PRD [13](../prd/13-non-functional-requirements.md) NFR-7 · `docs/design/observability.md`. Issues #87–#92, #135, #136.

## Global Constraints

- Local-first, no egress (R6); opt-in aggregation; signals only, never enforcement (PRD 14/30).
- Additive schema changes only; `schema_version`/`event_version` stay `0.1.0`. Redaction before storage (DD-06).
- Deterministic trust boundary; no LLM.
- Coverage ≥95%, `ruff` zero, `mypy --strict` clean. Run tests from `packages/python-sdk`.

## Review Focus

1. A drift signal never enforces — it is an event/observation, and the CLI exits `0` on signals.
2. Trailing baseline uses only *prior* samples; a single outlier does not poison its own baseline.
3. Low-volume series stay silent (`min_samples` guard); zero-variance baselines do not divide by zero.
4. Deployment correlation aligns a deploy to shifts *after* it, within a window.
5. Ingesting the same host store twice is idempotent (no duplicate records).

---

### Task 1 (#87): `host` record tag + `drift-detected` event type

**Files:** Modify `schema/agent-record.schema.json`, `schema/security-event.schema.json`, `src/agentwatch/records.py`; tests `tests/test_records.py`, `tests/test_schema_contract.py`, fixtures (`records/valid/*host*.json`, `events/valid/drift_detected.json`).

- [ ] Step 1: failing tests (host round-trips + validates; `drift-detected` accepted; unknown-type still rejected).
- [ ] Step 2: RED.
- [ ] Step 3: add `host: str | None` to `AgentRecord` (additive, dropped when None), `DRIFT_DETECTED = "drift-detected"` to `SecurityEventType`, `"host"` to `_RECORD_FIELDS`, schema `host` property + event enum member.
- [ ] Step 4: GREEN.
- [ ] Step 5: commit `feat(records): host tag + drift-detected event type (M11 #87)`.

### Task 2 (#87/#88): Fleet ingestion + aggregation

**Files:** Create `src/agentwatch/fleet.py`; Modify `src/agentwatch/cli/main.py`; test `tests/test_fleet.py`.

**Interfaces:** `FleetSource(host, records_path)`; `ingest_host(source, store) -> FleetIngestStats`; `FleetRollup`; `aggregate(records, *, group_by_host=...) -> list[FleetRollup]`; `build_fleet(store) -> FleetSnapshot`; `render_fleet`/`fleet_to_json`; CLI `agentwatch fleet ingest HOST=PATH...` and `agentwatch fleet show [--json]`.

- [ ] Steps: failing tests (two hosts ingest; idempotent re-ingest; aggregate by host; rollup counts/avg) → RED → implement → GREEN → commit `feat(fleet): multi-host ingestion + aggregation (M11 #87/#88)`.

### Task 3 (#89/#90): Trailing-baseline drift + deployment correlation

**Files:** Create `src/agentwatch/drift.py`; Modify `src/agentwatch/cli/main.py`; test `tests/test_drift.py`.

**Interfaces:** `Sample(at, value)`; `Baseline(mean, stdev, count)`; `trailing_baseline`; `DriftSignal`; `detect_drift(metric, samples, *, window, z_threshold, min_samples) -> list[DriftSignal]`; `signal_to_event`; `emit_signals`; `Deployment`; `correlate_deployments`; `load_deployments`; `metric_series(records, metric, *, bucket)`; CLI `agentwatch drift --metric M [--bucket session|hour] [--window N] [--z Z] [--emit] [--deploys FILE] [--json]`.

- [ ] Steps: failing tests (baseline vs shift; trailing excludes the outlier; low-volume silent; zero-variance safe; signal → `drift-detected` event; deploy aligns to shifts; CLI exits 0) → RED → implement → GREEN → commit `feat(drift): trailing-baseline signals + deploy correlation (M11 #89/#90)`.

### Task 4 (#91/#92/#135/#136): Tests, docs, full gate

**Files:** `docs/design/observability.md`, `docs/reference/cli-reference.md`, `docs/reference/compatibility.md` (regenerated if needed), `docs/wbs/v0.1.0/wbs-v0.1.0-part6-expansion.md`, `docs/wbs/v0.1.0/wbs-v0.1.0-index.md`, `docs/plans/README.md`, `CHANGELOG.md`.

- [ ] Update docs; run full package gate + `ruff` + `mypy --strict` + repo guard; commit `docs(m11): fleet aggregation + drift (#87-#92)`.
