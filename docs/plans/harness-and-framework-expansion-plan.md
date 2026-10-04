# Harness & Framework Expansion Implementation Plan

**Goal:** Deliver WBS M10 (R10) — expand beyond Claude Code + LangGraph: a published adapter plugin contract, native Cursor/Codex/Gemini adapters, a generic MCP-client proxy, Tier-2 framework adapters, and the supporting ingestion/fixtures/matrix tooling.

**Architecture:** Build on the shipped adapter + conformance infrastructure. `agentwatch.conformance` (an `AdapterSpec` + registry + `run`) is already the plugin contract; M10 publishes it (store format, daemon protocol, adapter API), registers new adapters against it, and adds a proxy/ingestion path for harnesses without native hooks.

**Tech Stack:** Python 3.10+ stdlib only; `argparse`; `pytest` + `pytest-cov` (≥95%); `ruff`; `mypy --strict`.

**Spec:** `docs/wbs/v0.1.0/wbs-v0.1.0-part6-expansion.md` (M10) · `docs/prd/23-event-interchange.md` (J1) · `docs/prd/27-harness-expansion.md` (N1–N4) · `docs/design/harness-adapter-design.md` · `docs/reference/adapter-conformance.md` · `docs/reference/compatibility.md`. Issues #79–#86, #203, #212–#215, #133, #134.

## Global Constraints

- Fail closed, never silent (PRD 17); redaction before storage (DD-06); the trust boundary stays deterministic.
- Monitor-only: every hook exits 0 (R2); local-first, no egress without explicit opt-in (R6).
- No new runtime dependency without a recorded decision (NFR-5).
- Additive record/schema changes only; `schema_version` stays `0.1.0`.
- Every adapter declares `CAPABILITIES` and `DOCUMENTED_GAPS` disjointly; conformance blocks CI.
- Coverage ≥ 95%, `ruff` zero, `mypy --strict` clean (NFR-11).

## Review Focus

| # | Failure mode | Owning test |
|---|---|---|
| 1 | Community adapter mutates its input message | conformance runner `normalize mutated its input` (existing) + community pack |
| 2 | A declared gap is silently dropped instead of rejected | community adapter gap-rejection check |
| 3 | Store envelope drifts from the published spec | `tests/test_protocol_contract.py` |
| 4 | Daemon frame shape drifts from the published protocol | `tests/test_protocol_contract.py` |
| 5 | A harness with no fixtures is silently "supported" | conformance `fixtures-populated` check |

---

## Sub-plan decomposition (execution order)

Each phase produces working, testable software and gets its own detailed plan when reached.

| Phase | Scope | Issues | Status |
|---|---|---|---|
| **1** | **Adapter plugin contract + published plumbing** | #79, #203, #85 | **detailed below** |
| 2 | Native harness adapters (Cursor, Codex CLI, Gemini CLI) + per-harness packs | #80, #81, #82, #85 | plan later |
| 3 | MCP-client interposition proxy (`init --mcp-proxy`) | #83, #212 | plan later |
| 4 | Tier-2 framework adapters (CrewAI, PydanticAI) | #84 | plan later |
| 5 | Ingestion/fixtures/matrix + docs | #213, #214, #215, #86, #134, #133 | plan later |

---

## Phase 1 — Adapter plugin contract + published plumbing

**Phase goal:** Publish the store-format, daemon-protocol, and adapter-api contracts (#203/J1), prove a sample out-of-tree adapter meets conformance (#79), and confirm per-harness conformance packs run in CI (#85).

### Task 1: Publish store-format + daemon-protocol specs with contract tests

**Files:**
- Create: `docs/reference/store-format.md`, `docs/reference/daemon-protocol.md`
- Test: `packages/python-sdk/tests/test_protocol_contract.py`

**Interfaces:**
- Produces: the two published specs (`v0.1.0`, experimental, additive-minor commitment).
- Consumes: `RecordStore` envelope/verify, `hook.build_message`, `daemon` frames.

- [x] **Step 1: Write the failing contract tests**

```python
def test_store_envelope_matches_the_published_contract(tmp_path):
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record())
    first = json.loads(store.path.read_text().splitlines()[0])
    assert first == {"format": 1}                      # documented format marker
    env = json.loads(store.path.read_text().splitlines()[1])
    assert set(env) == {"seq", "prev_hash", "hash", "record"}   # documented envelope

def test_tombstone_envelope_matches_the_published_contract(tmp_path): ...

def test_daemon_frame_shapes_match_the_published_protocol():
    assert hook.build_message("pre", {"session_id": "s"}) == {
        "phase": "pre", "harness": "claude-code", "event": {"session_id": "s"}}
    assert hook.build_message("hook-error", {"reason": "x"})["phase"] == "hook-error"
```

- [x] **Step 2: Run to verify it fails** — `pytest tests/test_protocol_contract.py -v` → FAIL (module missing).
- [x] **Step 3: Implement** — write the two reference docs describing exactly the shapes the tests pin (format marker, envelope keys, `sha256(prev_hash + canonical_json(record))`, tombstone fields, daemon framing/phases, compatibility commitment). No code change unless a test reveals drift.
- [x] **Step 4: Run to verify it passes** — `pytest tests/test_protocol_contract.py -v`; repo guard link-check.
- [x] **Step 5: Commit** — `git commit -s -m "docs(protocol): publish store format + daemon protocol (M10 #203)"`

### Task 2: Sample community adapter + adapter API reference

**Files:**
- Create: `docs/reference/adapter-api.md`
- Create: `packages/python-sdk/tests/community/sample_adapter.py`, `packages/python-sdk/tests/community/fixtures/sample_tool.json`
- Test: `packages/python-sdk/tests/test_community_adapter.py`

**Interfaces:**
- Produces: documentation of the plugin contract (`AdapterSpec` fields, `normalize(message) -> list[AgentRecord]`, capabilities/gaps, error class, fixtures dir, registration, conformance invocation, version commitment).
- Consumes: `agentwatch.conformance` (public: `AdapterSpec`, `register`, `run`, `ConformanceError`).

- [x] **Step 1: Write the failing test** — a sample adapter defined with only the public contract must pass `conformance.run`, and a mutated copy must fail.

```python
def test_sample_community_adapter_conforms():
    spec = sample_adapter.spec()
    report = conformance.run(spec)
    assert report.ok, report.summary()

def test_broken_adapter_is_rejected():
    spec = sample_adapter.broken_spec()      # claims a gap it does not reject
    assert not conformance.run(spec).ok
```

- [x] **Step 2: Run to verify it fails** — `pytest tests/test_community_adapter.py -v` → FAIL (module missing).
- [x] **Step 3: Implement** — `sample_adapter.py` implements a tiny harness (e.g. `sample-tool-use` phase) with `HARNESS_ID`/`CAPABILITIES`/`DOCUMENTED_GAPS`/`normalize` + a matching fixture + `spec()`/`broken_spec()`; `adapter-api.md` documents the contract and the compatibility commitment.
- [x] **Step 4: Run to verify it passes** — `pytest tests/test_community_adapter.py tests/test_conformance.py tests/test_conformance_runner.py -v`.
- [x] **Step 5: Commit** — `git commit -s -m "test(conformance): sample community adapter proves the plugin contract (M10 #79,#203)"`

> Ruling: the sample adapter lives at `tests/community_adapter.py` (not `tests/community/`) to match the existing `tests/conformance_registry.py` import pattern; fixtures live at `tests/fixtures/community/`. Cost if wrong: one file move.

### Task 3: Per-harness conformance pack manifest

**Files:**
- Create: `packages/python-sdk/tests/test_conformance_packs.py`
- Modify: `docs/reference/adapter-conformance.md`

**Interfaces:**
- Produces: a CI check that every registered adapter ships a non-empty, well-formed conformance pack (fixtures dir, `message`+`expected`), so "supported" cannot be claimed without one.

- [x] **Step 1: Write the failing test**

```python
@pytest.mark.parametrize("spec", conformance.registered(), ids=lambda s: s.name)
def test_each_registered_adapter_has_a_populated_conformance_pack(spec):
    paths = sorted(spec.fixtures_dir.glob("*.json"))
    assert paths, f"{spec.name} has no conformance fixtures"
    for path in paths:
        fixture = json.loads(path.read_text())
        assert set(fixture) >= {"message", "expected"}
```

- [x] **Step 2: Run to verify it fails** — `pytest tests/test_conformance_packs.py -v` → FAIL (module missing).
- [x] **Step 3: Implement** — the test + a paragraph in `adapter-conformance.md` naming the pack definition.
- [x] **Step 4: Run to verify it passes** — `pytest tests/test_conformance_packs.py -v`.
- [x] **Step 5: Commit** — `git commit -s -m "test(conformance): per-harness pack manifest check (M10 #85)"`

### Task 4: Phase docs + WBS + CHANGELOG

**Files:** `docs/reference/README.md` (if it indexes references), `docs/wbs/v0.1.0/wbs-v0.1.0-part6-expansion.md`, `docs/wbs/v0.1.0/wbs-v0.1.0-index.md`, `CHANGELOG.md`

- [x] **Step 1: Update** M10 progress (Phase 1 done), link the new reference docs, add CHANGELOG entries.
- [x] **Step 2: Verify** — repo guard `python3 -m pytest tests -q` (link-check).
- [x] **Step 3: Commit** — `git commit -s -m "docs(m10): adapter contract + plumbing specs (M10 #79,#203,#85)"`

---

## Execution notes

- `make test` (all packages + coverage ≥ 95% + repo guard) gates each phase.
- Close each issue as its task lands (#203 with Task 1; #79 with Task 2; #85 with Task 3; #133/#134 partially, with Phase 5), then close milestone 11 ("0.1.0 — M10 Harness + framework expansion") when all phases land.
- Phases 2–5 each get their own plan file (same `docs/plans/` location, purpose-named) before implementation.
