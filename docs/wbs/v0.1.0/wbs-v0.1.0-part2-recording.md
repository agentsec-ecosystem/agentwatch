# WBS v0.1.0 — Part 2: Recording (M2–M3)

**BLUF:** **Port the instrumentation SDK first**, then capture Claude Code tool calls (adapter + daemon) and
persist them safely (local hash-chained store + redaction). Two milestones.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **design docs updated** · port tasks complete.

---

## Milestone M2 — Claude Code adapter + daemon

**Goal:** **port** the shipped instrumentation SDK (spans, LangGraph, OTLP, metadata), then add the Claude
Code hook adapter + local daemon so one session records end-to-end with zero code changes (R2, R3).

**Requirements / PRDs:** R2, R3; [Claude Code hook contract](../../design/claude-code-hook-contract.md),
[harness-adapter design](../../design/harness-adapter-design.md),
[adapter conformance](../../reference/adapter-conformance.md), PRD 17 (F2).

**Work items (port first)**

| # | Task | Deliverable | Acceptance |
|---|---|---|---|
| 2.1 | **Port** instrumentation SDK core from `agent-exec-trace` (span helpers, `AgentTracer`) | `agentwatch` SDK module | ported SDK tests pass |
| 2.2 | **Port** LangGraph adapter (`TracedGraph`) | adapter module | node-level spans declared |
| 2.3 | **Port** OTLP/span emission + version/workload metadata | emission path | metadata carried |
| 2.4 | Add **Claude Code hook script** (`pre`/`post`) | `agentwatch-hook` | runs, returns 0, forwards event |
| 2.5 | Add **UDS protocol** (`$XDG_RUNTIME_DIR/agentwatch.sock`, NDJSON) + daemon | daemon | hook ↔ daemon round-trip |
| 2.6 | `normalize(claude_code_event) -> Record[]` | adapter mapping | Pre→intent, Post→outcome |
| 2.7 | Hook-error handling (F2) | `hook-error` record | miss never dropped |
| 2.8 | Conformance fixtures + documented gaps (R3) | fixtures + gaps | fixtures replay green |
| 2.9 | **Update design docs** | hook contract, adapter design/conformance, compatibility | docs match implementation |

**Tests required:** conformance fixture replay; socket perms; F2 hook-error; ported-SDK tests; hook never
blocks the agent.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] One Claude Code session emits records end-to-end, zero code changes (R2)
- [ ] Ported SDK + LangGraph adapter tests green; conformance fixtures green (R3)

**Design docs to update:** [claude-code-hook-contract.md](../../design/claude-code-hook-contract.md),
[harness-adapter-design.md](../../design/harness-adapter-design.md),
[adapter-conformance.md](../../reference/adapter-conformance.md), [compatibility.md](../../reference/compatibility.md),
[known-limitations.md](../../reference/known-limitations.md), [CHANGELOG](../../../CHANGELOG.md).

---

## Milestone M3 — Local store + redaction

**Goal:** **port the shipped privacy modes/redaction**, then add the local hash-chained store and the
secret/PII classes; records are local, redacted, tamper-evident, bounded (R6, R7, R11 early).

**Requirements / PRDs:** R6, R7; [PRD 15](../../prd/15-data-model.md),
[storage design](../../design/storage-design.md), [redaction rules](../../design/redaction-rules.md),
[privacy-mode transforms](../../design/privacy-mode-transforms.md), PRD 17 (F3/F4).

**Work items (port first)**

| # | Task | Deliverable | Acceptance |
|---|---|---|---|
| 3.1 | **Port** privacy modes / redaction from `agent-exec-trace` SDK | redaction module | 4 modes behave as shipped |
| 3.2 | Add secret/PII classes + `<REDACTED:kind>` + `secret-detected` event (R5) | rules engine | attack-pack fixtures pass |
| 3.3 | Add **JSONL store** (append-only, DD-08) | store module | persist + reload |
| 3.4 | Add **hash chain** + `verify-store` (DD-07) | chain module | any edit detected |
| 3.5 | Add retention (`retention_days`, `max_size_mb`) | retention | purge tombstones, never silent |
| 3.6 | Redaction self-test (blocks export, DD-09) | self-test | 0 leaks or export blocked |
| 3.7 | Fault behavior — store-full (F3) fail-closed; chain-break (F4) surfaced | fault paths | F3/F4 tests green |
| 3.8 | **Update design docs** | storage, redaction, privacy, PRD 15 | docs match behavior |

**Tests required:** chain integrity + `verify-store`; F3 store-full; F4 corrupt chain; redaction attack pack
(0 leaks); per-mode transform table; retention tombstoning.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] `verify-store` clean after a session; any edit detected
- [ ] Redaction attack pack finds **0 leaks** (R7); `secret-detected` emitted
- [ ] Store-full fails closed (F3); corrupt chain surfaced (F4); no network (R6)

**Design docs to update:** [storage-design.md](../../design/storage-design.md),
[redaction-rules.md](../../design/redaction-rules.md), [privacy-mode-transforms.md](../../design/privacy-mode-transforms.md),
[privacy-data-handling.md](../../design/privacy-data-handling.md), [PRD 15](../../prd/15-data-model.md),
[PRD 17](../../prd/17-error-handling.md), [CHANGELOG](../../../CHANGELOG.md).

---

Part 2 green ⇒ proceed to [Part 3 (M4–M5)](wbs-v0.1.0-part3-export-release.md).
