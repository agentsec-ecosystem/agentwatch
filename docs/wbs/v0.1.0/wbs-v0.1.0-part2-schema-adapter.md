# WBS v0.1.0 — Part 2: Schema & Adapter (M2–M3)

**BLUF:** Adapt the ported schema and extend it with the security-event schema, then port the instrumentation
SDK and add the Claude Code adapter + daemon. Two milestones.

> **Standard exit criteria apply to every milestone:** all tests pass · coverage ≥ 95% · lint strict clean
> (`ruff` zero, `mypy --strict`) · **design docs updated** · port tasks complete.

---

## Milestone M2 — Record + security-event schema

**Status:** ✅ **implemented** — execution plan:
[m2-m3-schema-adapter-execution-plan.md](../../plans/m2-m3-schema-adapter-execution-plan.md);
issues #16–#21, #117, #118. `agentwatch.records` + strict validators; fixtures and schema contract tests.

**Goal:** adapt the **ported** record/trace schema into the normative agentwatch record model, and add the
security-event schema.

**Requirements / PRDs:** R1, R5, [PRD 15](../../prd/15-data-model.md),
[record-format spec](../../reference/record-format-spec.md), [`schema/`](../../../schema/).

**Work items (port first)**

| # | Task | Deliverable | Acceptance | Issue | Issue |
|---|---|---|---|---|---|
| 2.1 | **Port/adapt** record/trace schema + span models (from M0 tree) | record model | matches [`agent-record.schema.json`](../../../schema/agent-record.schema.json) | #16 |
| 2.2 | Add **security-event schema** (new) | event model | enum: `denied`…`halted` | #17 |
| 2.3 | Validation entry point | `validate_record()`/`validate_event()` | invalid rejected, not coerced (F8) | #18 |
| 2.4 | Version handling | `schema_version`/`event_version` checks | unknown version rejected clearly | #19 |
| 2.5 | Fixtures | valid + invalid records/events | used by tests + conformance | #20 |
| 2.6 | **Update design docs** | record-format spec, data-dictionary | docs match models | #21 |
| 2.T | Add/expand test cases for this milestone (unit + integration + fault-injection) | tests | all new paths covered; coverage ≥ 95% | #117 |
| 2.D | Create/update the design + reference docs for this milestone | docs | docs updated and linked from the WBS | #118 |

**Tests required:** JSON round-trip; invalid rejected (F8); event enum + version enforcement.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] Record + event schemas validate; round-trip green
- [ ] Invalid records rejected (F8); schema version enforced

**Design docs to update:** [record-format-spec.md](../../reference/record-format-spec.md),
[data-dictionary.md](../../design/data-dictionary.md), [PRD 15](../../prd/15-data-model.md),
[`schema/README.md`](../../../schema/README.md), [CHANGELOG](../../../CHANGELOG.md).

---

## Milestone M3 — Claude Code adapter + daemon

**Status:** 🚧 in progress — execution plan:
[m2-m3-schema-adapter-execution-plan.md](../../plans/m2-m3-schema-adapter-execution-plan.md).

**3.1–3.3 status:** satisfied by the M0 port (SDK spans, `AgentTracer`, LangGraph adapter, OTLP emission +
version/workload metadata). Evidence: `test_spans.py` (13), `test_tracer.py` (6), `test_langgraph.py` (24),
`test_otlp.py` (4), plus metadata assertions in `test_instrument.py` / `test_context.py`.

**Goal:** port the **ported** instrumentation SDK (spans, LangGraph, OTLP) and add the Claude Code hook
adapter + local daemon, so one session records end-to-end with zero code changes (R2, R3).

**Requirements / PRDs:** R2, R3; [Claude Code hook contract](../../design/claude-code-hook-contract.md),
[harness-adapter design](../../design/harness-adapter-design.md),
[adapter conformance](../../reference/adapter-conformance.md), PRD 17 (F2).

**Work items (port first)**

| # | Task | Deliverable | Acceptance | Issue | Issue |
|---|---|---|---|---|---|
| 3.1 | **Port/adapt** instrumentation SDK core (spans, `AgentTracer`) | SDK module | ported tests pass | #22 |
| 3.2 | **Port/adapt** LangGraph adapter (`TracedGraph`) | adapter | node-level spans | #23 |
| 3.3 | **Port/adapt** OTLP/span emission + version/workload metadata | emission | metadata carried | #24 |
| 3.4 | Add **Claude Code hook script** (`pre`/`post`) | `agentwatch-hook` | returns 0, forwards event | #25 |
| 3.5 | Add **UDS protocol + daemon** | daemon | hook ↔ daemon round-trip | #26 |
| 3.6 | `normalize(claude_code_event) -> Record[]` | adapter mapping | Pre→intent, Post→outcome | #27 |
| 3.7 | Hook-error handling (F2) | `hook-error` record | miss never dropped | #28 |
| 3.8 | Conformance fixtures + documented gaps (R3) | fixtures + gaps | fixtures replay green | #29 |
| 3.9 | **Update design docs** | hook contract, adapter design/conformance, compatibility | docs match implementation | #30 |
| 3.T | Add/expand test cases for this milestone (unit + integration + fault-injection) | tests | all new paths covered; coverage ≥ 95% | #119 |
| 3.D | Create/update the design + reference docs for this milestone | docs | docs updated and linked from the WBS | #120 |

**Tests required:** conformance fixture replay; socket perms; F2; ported-SDK tests; hook never blocks agent.

**Exit criteria**

- [ ] All tests pass · coverage ≥ 95% · lint strict clean · design docs updated · port tasks complete
- [ ] One Claude Code session records end-to-end, zero code changes (R2)
- [ ] Ported SDK + LangGraph tests green; conformance fixtures green (R3)

**Design docs to update:** [claude-code-hook-contract.md](../../design/claude-code-hook-contract.md),
[harness-adapter-design.md](../../design/harness-adapter-design.md),
[adapter-conformance.md](../../reference/adapter-conformance.md), [compatibility.md](../../reference/compatibility.md),
[CHANGELOG](../../../CHANGELOG.md).

---

Part 2 green ⇒ proceed to [Part 3 (M4–M5)](wbs-v0.1.0-part3-store-export.md).
