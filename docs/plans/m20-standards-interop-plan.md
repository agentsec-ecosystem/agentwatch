# M20 — Standards & Interop (PRD 36) Implementation Plan

> **For agentic workers:** Work task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit/consume open standards: OCSF + CloudEvents mappings (S8), a reference consumer (S38), an
OTel collector component (S39), opt-in rule-free event forwarding sinks (S10), and MCP tool-surface
drift as a new security event (S4).

**Architecture:** A pure `ocsf.py` mapping/transcode; `sinks.py` for file/webhook/syslog forwarding of
security events only; `mcp_surface.py` for per-session surface snapshots + diff; `examples/` reference
consumer; a thin `integrations/otel-collector` component built on the existing `export.py` semconv
mapping. New event type `tool-surface-changed` through the published schema.

**Tech Stack:** Python 3.10+; `pytest` + `pytest-cov` (≥95%); `ruff`; `mypy --strict`. No new runtime
dependency.

**Spec:** PRD [36](../prd/36-standards-and-interop.md) · WBS
[Part 12](../wbs/v0.1.0/wbs-v0.1.0-part12-interop-and-config.md) · issues #260–#264.

## Global Constraints

- Emitting a standard is **export, not becoming the consumer** (PRD 14): opt-in, open-format, local-first.
- Lossless-or-explicit: fields OCSF cannot express go in `unmapped`; an unmapped event type is exported
  with an explicit marker, never dropped.
- Sinks forward **security events only** (never full records), with **no filtering beyond event type**.
- `tool-surface-changed` is observation-only wording; observed vs enumerated surfaces are distinct
  fields, never merged.
- Coverage ≥95%, `ruff` zero, `mypy --strict` clean. Run tests from `packages/python-sdk`.

## Review Focus

1. Every shipped event type maps to a documented OCSF target or an explicit `unmapped`.
2. No sink egress without explicit opt-in and a passing redaction self-test; only events leave.
3. Surface drift is metadata only and never a malware verdict.
4. Component output carries the pinned semconv version and does not fabricate spans.

---

## Tasks

### Task 1 — S8 (#260): OCSF + CloudEvents mappings
- [x] `ocsf.py`: pinned `OCSF_VERSION`, `MAPPING_TABLE`, `to_ocsf(event)`, `to_cloudevents(event)`,
      `unmapped` fields; `docs/design/ocsf-mapping.md`.
- [x] CLI `export-session --format ndjson|ocsf|cloudevents`.
- [x] Tests `tests/test_ocsf.py`.

### Task 2 — S10 (#263): forwarding sinks
- [x] Config `sinks` (enabled + targets) gated by the redaction self-test.
- [x] `sinks.py`: file / webhook / syslog; bounded queue; `degraded` on failure; events only.
- [x] Daemon forwards recorded security events; tests `tests/test_sinks.py`.

### Task 3 — S4 (#264): MCP tool-surface snapshot + drift
- [x] `SecurityEventType.TOOL_SURFACE_CHANGED` + schema enum.
- [x] `mcp_surface.py`: observed/enumerated surfaces, digest, `detect_surface_changes`, carrier + event.
- [x] CLI `inventory --snapshot` / `inventory --diff [--server]`; daemon session-end carrier.
- [x] Tests `tests/test_mcp_surface.py`.

### Task 4 — S38 (#261): reference consumer
- [x] `examples/security_event_consumer.py` + fixture stream + CI test `tests/test_reference_consumer.py`.

### Task 5 — S39 (#262): OTel collector component
- [x] `otel_component.py` (thin receiver mapping on `export.py`) + `integrations/otel-collector/`.
- [x] Pinned semconv version reported; missing store → unavailable. Tests `tests/test_otel_component.py`.

### Task 6 — Docs, exit criteria
- [x] PRD 36, WBS M20, index, CLI reference, CHANGELOG, schema enum, mapping docs.
- [x] Full suite + coverage; lint; commit; push; close #260–#264.

---

## Progress log

- 2026-10-03 — plan created; starting Task 1 (OCSF + CloudEvents).
- 2026-10-03 — all tasks implemented; SDK 1302 passed / 1 skipped, coverage 95.16%, ruff + mypy
  clean. Docs updated, issues #260-#264 closed.
