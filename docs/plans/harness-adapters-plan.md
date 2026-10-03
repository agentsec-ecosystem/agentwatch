# Harness Adapters Implementation Plan

**Goal:** Deliver M10 Phase 2 — native Cursor, Codex CLI, and Gemini CLI adapters that pass the shared conformance runner, with per-harness fixture packs.

**Architecture:** Each harness gets a small module under `agentwatch.adapters` implementing the published plugin contract (`HARNESS_ID`, `CAPABILITIES`, `DOCUMENTED_GAPS`, `normalize`, error class) plus a fixture pack. **Event shapes are modeled/provisional** (no native surface is documented in-repo yet); fixtures are synthesized-from-shape and must be replaced by real captures (M14 field tests / N4 version matrix). A shared `agentwatch.adapters.modeled` helper keeps the three adapters thin.

**Tech Stack:** Python 3.10+ stdlib only; `pytest`; `ruff`; `mypy --strict`.

**Spec:** `docs/wbs/v0.1.0/wbs-v0.1.0-part6-expansion.md` (M10) · `docs/reference/adapter-api.md` · `docs/reference/adapter-conformance.md` · `docs/prd/05-features.md` (R10). Issues #80, #81, #82.

> **Ruling (spec conflict):** PRD 09/11, `compatibility.md`, and `known-limitations.md` place Cursor in v0.1.x and Codex/Gemini later; the WBS/milestone place them in v0.1.0 M10. Per the human partner's decision, M10 implements them now from **modeled** shapes, documented as **provisional** — not full-fidelity support. Cost if wrong: fixture/shape rework when real harness events are captured.

## Global Constraints

- Fail closed, never silent; redaction before storage (DD-06); deterministic trust boundary.
- Every adapter declares disjoint `CAPABILITIES`/`DOCUMENTED_GAPS`; conformance blocks CI.
- Records must validate; `normalize` must not mutate its input and must be idempotent.
- Coverage ≥ 95%, `ruff` zero, `mypy --strict` clean.

## Review Focus

| # | Failure mode | Owning test |
|---|---|---|
| 1 | A malformed/unknown native phase is dropped instead of rejected | conformance gap/unknown rejection per adapter |
| 2 | An after-event does not record the outcome/end time | per-adapter error fixture |
| 3 | `normalize` mutates its input | conformance `normalize mutated its input` |
| 4 | A secret in a native field reaches the record | per-adapter secret-detected test |
| 5 | A "supported" harness has no fixture pack | `test_conformance_packs.py` |

---

### Task 1: Shared modeled-adapter helper + Cursor adapter

**Files:**
- Create: `packages/python-sdk/src/agentwatch/adapters/modeled.py`, `.../adapters/cursor.py`
- Modify: `packages/python-sdk/src/agentwatch/adapters/__init__.py`
- Test: `packages/python-sdk/tests/test_cursor_adapter.py`
- Fixtures: `packages/python-sdk/tests/fixtures/cursor/before_shell.json`, `after_edit_error.json`

**Interfaces:**
- Produces: `modeled.record_from_event(harness, *, session_id, tool_name, step_type, outcome, event, server=None, redaction=None, ended=False) -> AgentRecord` (shared: time/redaction/project/span/security-event). `cursor.HARNESS_ID = "cursor"`, `CAPABILITIES = {beforeShellExecution, afterShellExecution, beforeFileEdit, afterFileEdit}`, `DOCUMENTED_GAPS = ("mcp-server-events",)`, `CursorAdapterError`, `normalize(message)`.

- [x] **Step 1: Write failing tests** — `normalize` maps before→`act`, after→`observe` with ended/duration, error→`outcome=error`; unknown phase raises `CursorAdapterError`; a secret fires `secret-detected`; input not mutated.
- [x] **Step 2: Run to verify it fails** — `pytest tests/test_cursor_adapter.py -v` → FAIL (module missing).
- [x] **Step 3: Implement** `modeled.py` + `cursor.py` + fixtures; export `cursor` from `adapters/__init__.py`.
- [x] **Step 4: Run to verify it passes** — `pytest tests/test_cursor_adapter.py -v`.
- [x] **Step 5: Commit** — `git commit -s -m "feat(adapters): modeled Cursor adapter (M10 #80)"`

### Task 2: Codex CLI adapter

**Files:** Create `.../adapters/codex_cli.py`; Modify `adapters/__init__.py`; Test `tests/test_codex_cli_adapter.py`; Fixtures `tests/fixtures/codex-cli/exec_begin.json`, `exec_end_error.json`, `patch_apply.json`.

**Interfaces:** `HARNESS_ID="codex-cli"`, `CAPABILITIES={exec_begin, exec_end, patch_apply}`, `DOCUMENTED_GAPS=("mcp-server-events",)`; `exec_begin`→act, `exec_end`→observe (error on `error`/nonzero `exit_code`), `patch_apply`→act with outcome from `success`.

- [x] Steps mirror Task 1 (write failing tests → RED → implement → GREEN → commit `feat(adapters): modeled Codex CLI adapter (M10 #81)`).

### Task 3: Gemini CLI adapter

**Files:** Create `.../adapters/gemini_cli.py`; Modify `adapters/__init__.py`; Test `tests/test_gemini_cli_adapter.py`; Fixtures `tests/fixtures/gemini-cli/tool_call.json`, `tool_result.json`, `session_start.json`.

**Interfaces:** `HARNESS_ID="gemini-cli"`, `CAPABILITIES={tool_call, tool_result, session_start, session_end}`, `DOCUMENTED_GAPS=("mcp-server-events",)`; `tool_call`→act, `tool_result`→observe (error on `is_error`), `session_*`→boundary records (no step type).

- [x] Steps mirror Task 1 → commit `feat(adapters): modeled Gemini CLI adapter (M10 #82)`.

### Task 4: Register all three + docs/WBS/CHANGELOG

**Files:** Modify `tests/conformance_registry.py`, `tests/test_conformance.py` (shipped-adapter coverage), `docs/design/harness-adapter-design.md`, `docs/reference/adapter-conformance.md`, `docs/reference/compatibility.md`, `docs/reference/known-limitations.md`, `docs/wbs/v0.1.0/wbs-v0.1.0-part6-expansion.md`, `docs/wbs/v0.1.0/wbs-v0.1.0-index.md`, `CHANGELOG.md`.

- [ ] **Step 1: Register** the three adapters in `conformance_registry.py`; extend the "all shipped adapters registered" test.
- [ ] **Step 2: Docs** — mark each adapter **provisional (modeled)**, note the shape-replacement follow-up (M14/N4), update the compatibility table and known limitations, WBS, CHANGELOG.
- [ ] **Step 3: Verify** — `make test` (coverage ≥ 95% + guard).
- [ ] **Step 4: Commit** — `git commit -s -m "docs(m10): register modeled adapters + mark provisional (M10 #80-#82)"`

---

## Execution notes

- `make test` gates each task; conformance runs every registered adapter (Claude Code + the three new ones).
- Close #80/#81/#82 as their tasks land; milestone 11 stays open for Phases 3–5.
- When real harness events are captured (M14/N4), replace the modeled fixtures and tighten `CAPABILITIES`; the conformance runner will flag shape drift.
