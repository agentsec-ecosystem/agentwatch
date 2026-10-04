# M10 Phases 4–5 (Tier-2 adapters + ingestion/fixtures/matrix) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish WBS M10 — Tier-2 framework adapters (CrewAI, PydanticAI), OTel/NDJSON ingestion, per-platform fake-harness emitters, and a generated compatibility table + version-drift matrix.

**Architecture:** Tier-2 adapters mirror the modeled Tier-1 adapters (`agentwatch.adapters.modeled`) and register in the shared conformance runner. Ingestion (`agentwatch.ingest`) transcodes foreign OTel GenAI spans / NDJSON into validated, redacted, chained records through the existing store path, quarantining what does not normalize (B4). Fake-harness emitters are test utilities producing deterministic real/malformed/out-of-order streams. A `agentwatch.compatibility` module owns version-tagged fixtures, adapter tested ranges, shape fingerprints, and table rendering; a nightly workflow runs the drift check.

**Tech Stack:** Python 3.10+ stdlib only (`json`, `hashlib`, `argparse`, `sys`); `pytest` + `pytest-cov` (≥95%); `ruff`; `mypy --strict`.

**Spec:** WBS [Part 6](../wbs/v0.1.0/wbs-v0.1.0-part6-expansion.md) · PRD [27](../prd/27-harness-expansion.md) N2–N4 · `docs/design/harness-adapter-design.md` · `docs/reference/adapter-conformance.md` · `docs/reference/compatibility.md`. Issues #84, #213, #214, #215, #86, #133, #134.

## Global Constraints

- Python 3.10+ stdlib only; no new runtime dependency (NFR-5).
- Fail closed, never silent (PRD 17); redaction before storage (DD-06); deterministic trust boundary.
- Foreign content is untrusted: strict validation + quarantine, never invent fields (F8/B4).
- Monitor-only; local-first, no egress (R6). Synthetic data only in emitters.
- Coverage ≥95%, `ruff` zero, `mypy --strict` clean. Run package tests from `packages/python-sdk`.

## Review Focus

1. A declared gap is rejected explicitly, never dropped (conformance).
2. Foreign OTel/NDJSON with an embedded secret is masked before storage.
3. Unmappable foreign input is quarantined with a reason, not silently dropped.
4. Out-of-order / duplicate / malformed emitter events exercise the daemon without crashing.
5. A fixture shape change is detected by the drift check; the generated table is deterministic.

---

### Task 1 (#84): Tier-2 modeled adapters — CrewAI + PydanticAI

**Files:** Create `adapters/crewai.py`, `adapters/pydantic_ai.py`; Modify `adapters/__init__.py`, `tests/conformance_registry.py`; fixtures `tests/fixtures/crewai/*.json`, `tests/fixtures/pydantic-ai/*.json`; tests `tests/test_crewai_adapter.py`, `tests/test_pydantic_ai_adapter.py`.

**Interfaces:** `HARNESS_ID`, `CAPABILITIES`, `DOCUMENTED_GAPS`, `normalize`, error class per adapter; shared `modeled.record_from_event`.

- [ ] **Step 1:** Failing tests (act/observe, error outcome, gap rejection, secret detection, no input mutation).
- [ ] **Step 2:** RED.
- [ ] **Step 3:** Implement adapters + fixtures + register in conformance.
- [ ] **Step 4:** GREEN (`test_crewai_adapter.py`, `test_pydantic_ai_adapter.py`, `test_conformance*.py`).
- [ ] **Step 5:** Commit `feat(adapters): modeled Tier-2 CrewAI + PydanticAI adapters (M10 10.6 #84)`.

### Task 2 (#213): OTel / NDJSON ingestion

**Files:** Create `src/agentwatch/ingest.py`; Modify `src/agentwatch/cli/main.py`; fixtures `tests/fixtures/ingest/*.json`; test `tests/test_ingest.py`.

**Interfaces:** `ingest_otel(payload: Any, *, source: str = "otel") -> list[AgentRecord]`; `ingest_ndjson(lines: Iterable[str]) -> tuple[list[AgentRecord], list[IngestProblem]]`; `run_ingest(paths, store, *, fmt, quarantine, redaction) -> IngestStats`. CLI `agentwatch ingest --format otel|ndjson <source> [--json]`.

- [ ] **Step 1:** Failing tests — a fixture OTel trace chains + validates; a secret is masked; unmappable input is quarantined with a reason; conflicting ids are namespaced by source.
- [ ] **Step 2:** RED.
- [ ] **Step 3:** Implement the transcoder + CLI, reusing `validate_record`, `redact`, `QuarantineLog`, `RecordStore`.
- [ ] **Step 4:** GREEN.
- [ ] **Step 5:** Commit `feat(ingest): OTel/NDJSON foreign-trace ingestion (M10 N2 #213)`.

### Task 3 (#214): Fake-harness emitters

**Files:** Create `tests/fake_harness.py`; test `tests/test_fake_harness.py`.

**Interfaces:** `emitters(platform) -> Iterator[dict]` for `claude-code`, `cursor`, `codex-cli`, `gemini-cli`, `mcp-proxy`; `realistic_stream(platform, *, count)`, `malformed_stream()`, `out_of_order_stream()`, `duplicate_stream()`, `clock_skew_stream()`.

- [ ] **Step 1:** Failing tests — each platform's stream normalizes through its adapter; out-of-order/dup/malformed streams drive `Daemon.handle_message` without crashing; deterministic (same seed ⇒ same bytes).
- [ ] **Step 2:** RED.
- [ ] **Step 3:** Implement emitters as test utilities (synthetic only).
- [ ] **Step 4:** GREEN.
- [ ] **Step 5:** Commit `test(harness): deterministic fake-harness emitters (M10 N3 #214)`.

### Task 4 (#215): Compatibility table + version-drift matrix

**Files:** Create `src/agentwatch/compatibility.py`, `scripts/generate_compatibility.py`, `.github/workflows/harness-drift.yml`, `tests/fixtures/harness-versions.json`; Modify adapters (add `TESTED_RANGES`), `docs/reference/compatibility.md` (generated marker block); test `tests/test_compatibility.py`, `tests/test_ci_workflow.py`.

**Interfaces:** `HarnessRange(min, max)`; `ranges() -> dict[str, HarnessRange]`; `render_table() -> str`; `fingerprint_fixture(path) -> str`; `detect_drift(baseline) -> list[str]`; `load_baseline()`; CLI/script writes the marker block.

- [ ] **Step 1:** Failing tests — the table is deterministic and lists every shipped adapter; a simulated shape change is detected by `detect_drift`; the generated block matches `compatibility.md`.
- [ ] **Step 2:** RED.
- [ ] **Step 3:** Implement metadata + generator + drift baseline + nightly workflow.
- [ ] **Step 4:** GREEN; run the generator and confirm no diff.
- [ ] **Step 5:** Commit `feat(compat): generated compatibility table + drift matrix (M10 N4 #215)`.

### Task 5 (#86/#133/#134): Docs + full verification

**Files:** `docs/reference/{compatibility,adapter-conformance,known-limitations,cli-reference,harness-matrix}.md`, `docs/design/harness-adapter-design.md`, WBS Part 6 + index, `docs/plans/README.md`, `CHANGELOG.md`.

- [ ] **Step 1:** Mark 10.6/10.N2–N4 complete; document Tier-2 provisional status, ingestion, emitters, drift job.
- [ ] **Step 2:** Full package gate (`--cov-fail-under=95`) + `ruff` + `mypy --strict` + repo guard.
- [ ] **Step 3:** Commit `docs(m10): complete phases 4–5 (#84 #213 #214 #215)`.
