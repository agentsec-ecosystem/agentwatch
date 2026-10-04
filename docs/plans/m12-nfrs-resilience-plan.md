# M12 — NFRs + Resilience + Error Handling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement/verify NFR-1..NFR-12 (PRD 13) and F1–F10 (PRD 17): bounded overhead, bounded storage, self-observability, fail-closed behavior, least-privilege posture, durability, checkpoints, repair, clock-skew detection, service supervision, offline proof, and soak.

**Architecture:** Most recording primitives (hash chain, size cap, health states, quarantine, export gating) already exist (M3–M5). M12 hardens the store (posture, durability modes, checkpoints, incremental verify, repair), the daemon (clock-skew flag, rotated logs, mid-session chain re-verify), the CLI (`verify-store --repair`, `init --service`), and adds the NFR verification suites (perf, sizing, fault-injection F1–F10, health contract, i18n/UTC) plus CI jobs (no-network E2E, nightly soak).

**Tech Stack:** Python 3.10+ stdlib only; `pytest` + `pytest-cov` (≥95%); `ruff`; `mypy --strict`.

**Spec:** WBS [Part 7](../wbs/v0.1.0/wbs-v0.1.0-part7-hardening-release.md) M12 · PRD [13](../prd/13-non-functional-requirements.md) · PRD [17](../prd/17-error-handling.md) · PRD [21](../prd/21-data-integrity.md) · PRD [22](../prd/22-self-observability.md) · PRD [28](../prd/28-performance-operability.md). Issues #93–#101, #137, #138, #174, #179, #180, #186, #187, #189, #206–#209.

## Global Constraints

- Fail closed, never silent (PRD 17); no egress by default (NFR-9); redaction before storage (DD-06).
- Additive changes only; `schema_version`/`event_version`/`store format` stay `0.1.0`.
- Coverage ≥95%, `ruff` zero, `mypy --strict` clean. Run tests from `packages/python-sdk`.

## Review Focus

1. A silent stop is a bug: every failure flips health to `degraded`/`stopped` with a reason.
2. Durability is an explicit, surfaced choice — never hidden (NFR/healthz reports the mode).
3. `state=recording` only when the chain is intact and hooks fired.
4. Repair preserves evidence (byte-identical copy) and never silently drops records.
5. No runtime dependency becomes egress-capable under the audit gate.

---

### Task A (#179/#180/#186/#189/#206, 12.F5/E1/E2/G2/K1): Store hardening

**Files:** Create `src/agentwatch/posture.py`; Modify `src/agentwatch/store.py`, `src/agentwatch/cli/main.py`, `src/agentwatch/doctor.py`, `src/agentwatch/daemon.py`; tests `tests/test_posture.py`, `tests/test_store_checkpoints.py`, `tests/test_store_repair.py`.

**Interfaces:** `posture.secure_dir/secure_file/mode_of`; `RecordStore(..., durability="record"|"checkpoint"|"none", checkpoint_every:int|None)`; `RecordStore.checkpoint()`, `.checkpoints()`, `.refresh()`; `repair_store(path, *, evidence_path=None) -> RepairReport`; CLI `verify-store [--repair --yes]`.

- [ ] Steps: failing tests → RED → implement → GREEN → commit.

### Task B (#174/#187/#208, 12.B5/F6/K3): Clock skew, rotated logs, service supervision

**Files:** Modify `src/agentwatch/daemon.py`, `src/agentwatch/install.py`, `src/agentwatch/cli/main.py`, `src/agentwatch/health.py`; create `src/agentwatch/rotating_log.py`, `src/agentwatch/service.py`; tests `tests/test_clock_skew.py`, `tests/test_rotating_log.py`, `tests/test_service.py`.

- [ ] Steps: failing tests → RED → implement → GREEN → commit.

### Task C (#93–#100, #137, 12.1–12.8): NFR + fault verification suites

**Files:** Create `tests/test_perf_budget.py`, `tests/test_sizing.py`, `tests/test_fault_injection.py`, `tests/test_health_contract.py`, `tests/test_i18n.py`; Modify `src/agentwatch/health.py` if the contract needs a field.

- [ ] Steps: failing tests → RED → implement/fix → GREEN → commit.

### Task D (#101, #138, 12.9, #207/#209 12.K2/K4): CI jobs + docs

**Files:** Create `.github/workflows/offline-e2e.yml`, `.github/workflows/soak.yml`, `scripts/dependency_egress_audit.py`; Modify `docs/design/{performance-budget,sizing,ui-accessibility}.md`, `docs/reference/{i18n,resource-cost,cli-reference}.md`, WBS Part 7 + index, `docs/plans/README.md`, `CHANGELOG.md`.

- [ ] Steps: write jobs/audit + tests; update docs; full gate; commit.
