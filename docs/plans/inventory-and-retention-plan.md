# M9 — Inventory + Retention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver WBS M9 — shadow-agent/MCP-server inventory (R9) and hardened retention + right-to-erasure tombstoning (R11) — plus the capture-fidelity fields those need (MCP attribution, prompt fingerprint, project, parent-session link).

**Architecture:** All state stays in the existing append-only hash-chained JSONL `RecordStore`. New optional record fields (`project`, `parent_session_id`) are additive on the 0.1.0 schema (pre-release window, per PRD 25 D-I). The Claude Code adapter populates them from hook events; a new `agentwatch.inventory` module derives per-agent / per-MCP-server readouts from stored records; retention/purge reuse the existing tombstone envelope so the chain always verifies.

**Tech Stack:** Python 3.10+ stdlib only (no new runtime deps), `argparse` CLI, `pytest` + `pytest-cov` (≥95%), `ruff`, `mypy --strict`.

**Spec:** `docs/wbs/v0.1.0/wbs-v0.1.0-part5-stack-inventory.md` (M9) · `docs/prd/25-capture-fidelity.md` (D1/D2/I3/I4) · `docs/prd/26-investigation.md` (H3/I5) · `docs/prd/15-data-model.md` · `docs/design/storage-design.md`. GitHub issues #72–#78, #177, #178, #200, #201, #202, #131, #132.

## Global Constraints

- Fail closed, never silent (PRD 17).
- Redaction before storage (DD-06); the trust boundary stays deterministic — no LLM in redaction, validation, or chain verification.
- Monitor-only: every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6).
- No new runtime dependency without a recorded decision (NFR-5).
- `schema_version` stays `0.1.0`; new record fields are additive and optional; JSON schema keeps `additionalProperties: false`.
- Coverage ≥ 95%, `ruff` zero violations, `mypy --strict` clean (NFR-11). Every task commits its own tests.
- Existing stored records (without the new fields) must continue to load and validate.

## Review Focus

| # | Failure mode the spec implies but no task's happy-path test covers | Owning test |
|---|---|---|
| 1 | Malformed / plugin-scoped MCP names (`mcp__x__`, `mcp__plugin_p_s__t`) crash or invent a server | Task 2 `test_split_mcp_tool_defensive` |
| 2 | Old records with none of the new fields stop validating (silent back-compat break) | Task 1 `test_legacy_record_without_new_fields_round_trips` |
| 3 | `cwd` missing, or one session spanning two cwds, mis-attributes project | Task 2 `test_project_missing_is_none` + Task 5 `test_project_filter_is_per_record` |
| 4 | Parent-session cycle makes replay loop forever | Task 6 `test_replay_guards_against_parent_cycle` |
| 5 | Purge of an unknown session corrupts the chain or reports success | Task 8 `test_purge_unknown_session_is_a_noop` |
| 6 | Absent CLAUDE.md writes an empty `prompt_version` instead of omitting it | Task 3 `test_fingerprint_absent_file_omits_field` |
| 7 | Retention/purge tombstoning leaves `verify()` red | Task 7 `test_apply_retention_keeps_chain_green` / Task 8 `test_purge_keeps_chain_green` |

---

### Task 1: Additive record fields (`project`, `parent_session_id`)

**Files:**
- Modify: `packages/python-sdk/src/agentwatch/records.py` (`AgentRecord`, `_RECORD_FIELDS`, `_validate_record_dict`)
- Modify: `schema/agent-record.schema.json`
- Test: `packages/python-sdk/tests/test_records.py`
- Fixtures: `packages/python-sdk/tests/fixtures/records/valid/` (one new fixture)

**Interfaces:**
- Consumes: nothing new.
- Produces: `AgentRecord.project: str | None = None`, `AgentRecord.parent_session_id: str | None = None`; both serialize via `to_dict()` and parse via `from_dict()`; unknown-key rejection unchanged.

- [x] **Step 1: Write the failing tests** in `tests/test_records.py`

```python
def test_new_optional_fields_round_trip():
    record = AgentRecord(..., project="/repo/a", parent_session_id="sess-parent")
    assert AgentRecord.from_dict(record.to_dict()) == record

def test_legacy_record_without_new_fields_round_trips():
    data = AgentRecord(...).to_dict()
    assert "project" not in data and "parent_session_id" not in data
    assert validate_record(data) == AgentRecord.from_dict(data)

def test_unknown_record_key_is_still_rejected():
    with pytest.raises(RecordValidationError):
        validate_record({**valid_record_dict(), "nope": 1})
```

- [x] **Step 2: Run to verify it fails** — `cd packages/python-sdk && pytest tests/test_records.py -k "new_optional_fields or legacy_record_without" -v` → FAIL (`unexpected keyword argument 'project'`).
- [x] **Step 3: Implement** — add the two fields to `AgentRecord` (after `harness`), include them in `to_dict()`'s `_drop_none` block, read them in `from_dict()`, add both to `_RECORD_FIELDS`, and `_check_str(..., nullable=True)` for each in `_validate_record_dict`. Add matching optional `"project"` / `"parent_session_id"` `{ "type": ["string","null"] }` properties in the JSON schema. Add one valid fixture record carrying both.
- [x] **Step 4: Run to verify it passes** — same command → PASS; then `pytest tests/test_schema_contract.py tests/test_records.py -v`.
- [x] **Step 5: Commit** — `git commit -s -m "feat(records): add optional project + parent_session_id (M9)"`

---

### Task 2: Adapter populates MCP server, project, prompt_version, parent session

**Files:**
- Modify: `packages/python-sdk/src/agentwatch/adapters/claude_code.py`
- Test: `packages/python-sdk/tests/test_claude_code_adapter.py`, `tests/test_conformance.py`
- Fixtures: `tests/fixtures/claude-code/mcp_tool.json`, `tests/fixtures/claude-code/resume_session.json`

**Interfaces:**
- Produces: `split_mcp_tool(name: str) -> tuple[str | None, str]` (returns `(server, tool_name)`); `normalize()` sets `ToolCall.server` for `mcp__…` names, `AgentRecord.project` from `event["cwd"]`, `agent.prompt_version` from `event["prompt_version"]`, and `AgentRecord.parent_session_id` on `session-start` when `source`/`reason` is `resume`/`fork` (from `event["parent_session_id"]` / `event["source_session_id"]`).
- Consumes: Task 1 fields.

- [x] **Step 1: Write the failing tests**

```python
def test_split_mcp_tool_extracts_server():
    assert claude_code.split_mcp_tool("mcp__github__create_issue") == ("github", "create_issue")

def test_split_mcp_tool_defensive():
    assert claude_code.split_mcp_tool("mcp__x__") == (None, "mcp__x__")
    assert claude_code.split_mcp_tool("npm__bad__name") == (None, "npm__bad__name")

def test_normalize_tags_server_and_project():
    records = claude_code.normalize(_mcp_message(cwd="/repo/a"))
    assert records[0].tool.server == "github"
    assert records[0].project == "/repo/a"

def test_resume_session_links_parent():
    records = claude_code.normalize(_session_start(source="resume", parent="sess-1"))
    assert records[0].parent_session_id == "sess-1"
```

- [x] **Step 2: Run to verify it fails** — `pytest tests/test_claude_code_adapter.py -k "mcp or project or resume" -v` → FAIL.
- [x] **Step 3: Implement** — add `split_mcp_tool`; use it when building `ToolCall` in the `pre`/`post`/`denied` paths; set `project=event.get("cwd")`, `parent_session_id=event.get("parent_session_id")` (only when `source`/`reason` ∈ {resume, fork}); extend `identity_from`/`identity_for` to carry `prompt_version` from an explicit agent mapping. Add the two conformance fixtures.
- [x] **Step 4: Run to verify it passes** — `pytest tests/test_claude_code_adapter.py tests/test_conformance.py -v`.
- [x] **Step 5: Commit** — `git commit -s -m "feat(adapter): tag MCP server, project, prompt_version, parent session (M9)"`

---

### Task 3: Hook prompt-version fingerprint (CLAUDE.md digest)

**Files:**
- Modify: `packages/python-sdk/src/agentwatch/hook.py`
- Test: `packages/python-sdk/tests/test_hook.py`

**Interfaces:**
- Produces: `prompt_fingerprint(project_dir: str | None) -> str | None` — sha256 over `CLAUDE.md` + `.claude/rules/*.md` in sorted path order, hex `[:16]`; returns `None` when there is no `CLAUDE.md`. `main()` injects `event["prompt_version"]` when the digest exists, for tool/prompt phases.
- Consumes: Task 2 reads `event["prompt_version"]`.

- [ ] **Step 1: Write the failing tests**

```python
def test_fingerprint_is_stable_and_16_hex(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("rules", encoding="utf-8")
    first = hook.prompt_fingerprint(str(tmp_path))
    assert first == hook.prompt_fingerprint(str(tmp_path)) and re.fullmatch(r"[0-9a-f]{16}", first)

def test_fingerprint_absent_file_omits_field(tmp_path):
    assert hook.prompt_fingerprint(str(tmp_path)) is None

def test_fingerprint_multi_file_order_is_path_sorted(tmp_path):
    # .claude/rules/b.md + a.md -> same digest regardless of creation order
```

- [ ] **Step 2: Run to verify it fails** — `pytest tests/test_hook.py -k fingerprint -v` → FAIL.
- [ ] **Step 3: Implement** — stream-hash each file (`hashlib.sha256`, read in chunks) in sorted order; inject the digest into the forwarded `event` only when present (never an empty string).
- [ ] **Step 4: Run to verify it passes** — `pytest tests/test_hook.py -v`.
- [ ] **Step 5: Commit** — `git commit -s -m "feat(hook): record CLAUDE.md prompt fingerprint (M9 #178)"`

---

### Task 4: `agentwatch.inventory` + `agentwatch inventory` CLI (R9)

**Files:**
- Create: `packages/python-sdk/src/agentwatch/inventory.py`
- Modify: `packages/python-sdk/src/agentwatch/cli/main.py`
- Test: `packages/python-sdk/tests/test_inventory.py`

**Interfaces:**
- Produces: `build_inventory(store: RecordStore, *, session_id: str | None = None, project: str | None = None) -> Inventory`; frozen dataclasses `AgentSummary(identity, name, version, project, sessions, records, last_seen)`, `ServerSummary(server, tools, calls, last_seen, sessions)`, `Inventory(agents, servers)`; `render_inventory(inv) -> str`; `inventory_to_json(inv) -> dict`. CLI: `agentwatch inventory [--session-id ID] [--project PATH] [--json]`.
- Consumes: Task 1/2 fields.

- [ ] **Step 1: Write the failing tests**

```python
def test_inventory_lists_agents_and_servers(tmp_path):
    store = RecordStore(tmp_path / "records.jsonl")
    # append 2 records: agent=research_crew tool=mcp__github__create_issue, agent=support_bot tool=Bash
    inv = build_inventory(store)
    assert {a.identity for a in inv.agents} == {"research_crew", "support_bot"}
    assert [s.server for s in inv.servers] == ["github"]

def test_inventory_aggregates_calls_and_sessions(...): ...
def test_inventory_session_filter(...): ...
def test_inventory_project_filter(...): ...
```

- [ ] **Step 2: Run to verify it fails** — `pytest tests/test_inventory.py -v` → FAIL (module missing).
- [ ] **Step 3: Implement** — aggregate over `store.records()`; ignore tombstoned entries; server summary keyed on `record.tool.server`; sort deterministically; register the `inventory` subcommand + `_run_inventory` handler.
- [ ] **Step 4: Run to verify it passes** — `pytest tests/test_inventory.py tests/test_cli.py -v`.
- [ ] **Step 5: Commit** — `git commit -s -m "feat(cli): agentwatch inventory for agents + MCP servers (M9 #72-#75,#177)"`

---

### Task 5: Per-project filtering (`sessions`, `search`, `tail`)

**Files:**
- Modify: `packages/python-sdk/src/agentwatch/view.py`, `query.py`, `tail.py`, `cli/main.py`
- Test: `packages/python-sdk/tests/test_project_filter.py`

**Interfaces:**
- Produces: `list_sessions(store, *, project=None) -> list[str]`; `search(..., project=None)`; `tail`/`Tail` accept `project`; CLI `--project PATH` on `sessions`, `search`, `tail`. Exact-match on the normalized record `project`.
- Consumes: Task 1 `project` field.

- [ ] **Step 1: Write the failing tests**

```python
def test_project_filter_selects_one_project(...): ...   # two-project fixture
def test_project_filter_is_per_record_not_per_session(...): ...  # session spans two cwds
def test_project_filter_missing_cwd_is_unknown(...): ...
```

- [ ] **Step 2: Run to verify it fails** — `pytest tests/test_project_filter.py -v` → FAIL.
- [ ] **Step 3: Implement** — thread `project` through the three readers and the CLI parsers.
- [ ] **Step 4: Run to verify it passes** — `pytest tests/test_project_filter.py tests/test_view_explain.py tests/test_search_diff_alerts.py tests/test_tail.py -v`.
- [ ] **Step 5: Commit** — `git commit -s -m "feat(cli): --project filter for sessions/search/tail (M9 #201)"`

---

### Task 6: Replay follows the parent-session chain

**Files:**
- Modify: `packages/python-sdk/src/agentwatch/replay.py`, `cli/main.py`
- Test: `packages/python-sdk/tests/test_session_correlation.py`

**Interfaces:**
- Produces: `replay_session(store, session_id, *, follow_parents=True) -> list[AgentRecord]` — walks `parent_session_id` from resume/fork boundary records, oldest-first, and returns the merged timeline; guarded against cycles (visited set).
- Consumes: Task 2 `parent_session_id`.

- [ ] **Step 1: Write the failing tests**

```python
def test_replay_follows_parent_into_one_timeline(...): ...
def test_replay_guards_against_parent_cycle(...): ...  # terminates; no infinite loop
```

- [ ] **Step 2: Run to verify it fails** — `pytest tests/test_session_correlation.py -v` → FAIL.
- [ ] **Step 3: Implement** — collect the chain via a visited set; concatenate each session's `replay_session` ordering.
- [ ] **Step 4: Run to verify it passes** — `pytest tests/test_session_correlation.py tests/test_replay.py -v`.
- [ ] **Step 5: Commit** — `git commit -s -m "feat(replay): follow parent-session chain for resumed/forked runs (M9 #200)"`

---

### Task 7: Retention hardening + `agentwatch retention apply`

**Files:**
- Modify: `packages/python-sdk/src/agentwatch/cli/main.py`
- Test: `packages/python-sdk/tests/test_retention_cli.py`

**Interfaces:**
- Produces: `agentwatch retention apply [--json]` → prints purged/kept and the resulting `verify()` status; exit 1 if the chain is not green. Uses `cfg.store.retention_days`.
- Consumes: existing `RecordStore.apply_retention`.

- [ ] **Step 1: Write the failing tests**

```python
def test_retention_apply_tombstones_and_reports(tmp_path, capsys): ...
def test_apply_retention_keeps_chain_green(tmp_path): ...
def test_retention_apply_json_shape(...): ...
```

- [ ] **Step 2: Run to verify it fails** — `pytest tests/test_retention_cli.py -v` → FAIL.
- [ ] **Step 3: Implement** — subparser + handler; reuse `apply_retention`; assert `store.verify().ok` after the pass.
- [ ] **Step 4: Run to verify it passes** — `pytest tests/test_retention_cli.py -v`.
- [ ] **Step 5: Commit** — `git commit -s -m "feat(cli): agentwatch retention apply + chain check (M9 #76,#77)"`

---

### Task 8: Session purge (right to erasure)

**Files:**
- Modify: `packages/python-sdk/src/agentwatch/store.py`, `cli/main.py`
- Test: `packages/python-sdk/tests/test_purge.py`

**Interfaces:**
- Produces: `RecordStore.purge_session(session_id: str, *, now: datetime | None = None) -> PurgeReport` (`PurgeReport(purged: int, found: bool, marker_seq: int | None)`), tombstoning only that session's live entries and appending one live `purge` marker record (`tool.name="session-purge"`, `arguments={"session_id", "reason"?}`, `security_event` omitted). CLI: `agentwatch purge <session-id> [--yes] [--reason TEXT]`; exit 1 when the session is not found.
- Consumes: existing tombstone envelope.

- [ ] **Step 1: Write the failing tests**

```python
def test_purge_tombstones_only_that_session(...): ...
def test_purge_keeps_chain_green(...): ...
def test_purge_writes_a_marker_record(...): ...
def test_purge_unknown_session_is_a_noop(tmp_path): ...
```

- [ ] **Step 2: Run to verify it fails** — `pytest tests/test_purge.py -v` → FAIL.
- [ ] **Step 3: Implement** — select live entries for the session, rewrite as tombstones (same pattern as `apply_retention`), then append the marker; `verify()` must be green.
- [ ] **Step 4: Run to verify it passes** — `pytest tests/test_purge.py tests/test_store.py -v`.
- [ ] **Step 5: Commit** — `git commit -s -m "feat(store): session purge with tombstone + marker (M9 #202,#77)"`

---

### Task 9: Docs, WBS, CHANGELOG

**Files:**
- Modify: `docs/design/storage-design.md`, `docs/prd/15-data-model.md`, `docs/prd/25-capture-fidelity.md`, `docs/reference/cli-reference.md`, `CHANGELOG.md`, `docs/wbs/v0.1.0/wbs-v0.1.0-part5-stack-inventory.md`, `docs/wbs/v0.1.0/wbs-v0.1.0-index.md`
- Test: repo guard `python3 -m pytest tests` (link-check)

**Interfaces:** none (documentation).

- [ ] **Step 1: Update docs** — inventory CLI + new record fields + retention/purge behavior; mark M9 work items done in Part 5/index; CHANGELOG entries.
- [ ] **Step 2: Verify** — `python3 -m pytest tests -q` from repo root (link-check green).
- [ ] **Step 3: Commit** — `git commit -s -m "docs(m9): inventory, capture fidelity, retention/purge (M9 #78,#132)"`

---

## Execution notes

- `make test` (pytest + coverage ≥95% + repo guard) is the gate before closing issues; run it once at the end of each task group, not only per-file.
- Close the GitHub issues as their tasks land (#72–#75/#177 with Task 4; #178 Task 3; #200 Task 6; #201 Task 5; #76/#77 Tasks 7–8; #202 Task 8; #78/#132/#131 Task 9), then close milestone 10 ("0.1.0 — M9 Inventory + retention").
