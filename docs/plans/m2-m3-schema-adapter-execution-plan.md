# agentwatch M2+M3 — Schema & Adapter Execution Plan

**Spec:** [WBS Part 2 — M2/M3](../wbs/v0.1.0/wbs-v0.1.0-part2-schema-adapter.md) ·
[record-format spec](../reference/record-format-spec.md) · [PRD 15](../prd/15-data-model.md) ·
[`schema/`](../../schema/) · [Claude Code hook contract](../design/claude-code-hook-contract.md) ·
[adapter conformance](../reference/adapter-conformance.md) · [PRD 17 — F2](../prd/17-error-handling.md) ·
issues #16–#21, #117, #118 (M2) and #22–#30, #119, #120 (M3).

**Context:** M0/M1 are done. The published schemas `schema/agent-record.schema.json` and
`schema/security-event.schema.json` exist, but there is **no Python record model or validator**
anywhere in the tree. The instrumentation SDK (`spans.py`, `tracer.py`, `langgraph.py`) was ported in
M0, so M3's "port/adapt SDK" items are verification, not new construction; M3's new work is the
Claude Code hook, the daemon, normalization, and conformance.

## Decisions (rulings taken at planning time)

- **D1 — Record home:** the record + security-event model and validators live in
  `packages/python-sdk/src/agentwatch/records.py`. *Why:* it is the shared vocabulary every service
  consumes; the SDK is the core distribution. *Cost if wrong:* move the module + imports.
- **D2 — Dependency-free validation:** `validate_record`/`validate_event` are hand-written and reject
  unknown fields/wrong types/bad enums/unknown versions (F8) with no runtime dependency. A **dev-only**
  `jsonschema` test proves our `to_dict()` output conforms to the published `schema/*.json` (guards drift).
- **D3 — Adapter/hook/daemon home:** `agentwatch.adapters.claude_code` (`normalize`), `agentwatch.hook`
  (`agentwatch-hook` console script), `agentwatch.daemon` (`agentwatch-daemon`).
- **D4 — Socket:** Unix domain socket at `$AGENTWATCH_SOCKET`, else `$XDG_RUNTIME_DIR/agentwatch.sock`,
  else `/tmp/agentwatch.sock`; newline-delimited JSON, one message per hook event.
- **D5 — Daemon sink (M3):** append normalized records as JSONL to `<store.path>/records.jsonl`. The
  hash-chained store is M4 (R11).
- **D6 — `hook-error` convention:** a hook that cannot be delivered produces a record with
  `outcome="error"` and `tool.name="hook-error"` (F2), documented in the record-format spec. *Why:* the
  schema has no dedicated hook-error field and needs none. *Cost if wrong:* a schema field is added later.
- **D7 — Hook is fire-and-forget:** the hook process always exits 0 and never blocks the agent; on a
  socket error the daemon records `hook-error` when it later sees the paired event or a health probe.

## Global Constraints

- **Exit gate:** `make lint` (ruff zero), `make typecheck` (`mypy --strict`), `make test` (green,
  coverage ≥95%), plus the repo guard and the docs link-check.
- **Fail closed / reject, never coerce** (F8): invalid records/events raise, they are not silently fixed.
- No new runtime dependency.
- Commits conventional + signed off (`git commit -s`).

## Interfaces / shared surfaces

- Task 1 defines `agentwatch.records` (`AgentRecord`, `SecurityEvent`, enums, version constants); Task 2
  adds `validate_record`/`validate_event`; Tasks 3, 5–10 consume them.
- Task 6 defines `agentwatch.adapters.claude_code.normalize`; Tasks 7–9 (hook/daemon/F2) consume it via the daemon.
- Task 4 and Task 11 both edit the docs; Task 11 owns the final WBS/CHANGELOG status.

---

## Task 1 — Record + security-event models (M2 2.1/2.2 / #16, #17)

**Deliverable:** `agentwatch/records.py` with typed, round-trippable models matching `schema/`.

**Steps**

1. **RED:** `packages/python-sdk/tests/test_records.py`: build an `AgentRecord` with identity/tool/outcome,
   assert `to_dict()` shape, assert `AgentRecord.from_dict(r.to_dict()) == r`, assert `SecurityEvent`
   round-trips, assert enum members (`Outcome.ok/error/denied`, `StepType.reason/act/observe/verify`,
   `SecurityEventType.denied/policy-fired/secret-detected/revoked/halted`), and version constants
   `SCHEMA_VERSION == "0.1.0"`, `EVENT_VERSION == "0.1.0"`.
2. Run; fail (module missing).
3. **GREEN:** implement `records.py`: enums, frozen dataclasses `AgentIdentity`, `ToolCall`,
   `SecurityEvent`, `AgentRecord`; `to_dict`/`from_dict`; UTC ISO-8601 datetime handling.
4. Re-run; full sdk suite.
5. Commit: `feat(records): record and security-event models (M2)`.

**Expected:** new tests pass; `to_dict()` omits unset optionals and matches the schema field names.

---

## Task 2 — Validation + version handling (M2 2.3/2.4 / #18, #19)

**Deliverable:** `validate_record(data)`, `validate_event(data)`, `RecordValidationError`; unknown
versions rejected clearly; invalid input rejected, not coerced (F8).

**Steps**

1. **RED:** add to `test_records.py`:
   - valid dict → model;
   - missing required (`session_id`, `agent.identity`, `tool.name`, `outcome`, `started_at`) rejected;
   - unknown top-level / nested key rejected (`additionalProperties: false`);
   - wrong types rejected *without coercion* (`duration_ms="5s"`, `tokens=1.5`, `started_at` int);
   - bad enum rejected (`outcome="maybe"`, event `type="exploded"`, `privacy_mode="nope"`);
   - unknown `schema_version`/`event_version` rejected with the version in the message;
   - nullable fields accept both `null` and omission; `security_event` validated recursively.
2. Run; fail.
3. **GREEN:** implement strict validators (type checks, required, enums, unknown keys, ISO-8601 UTC,
   bool-is-not-int) and a `_require_version` helper.
4. Re-run; full suite + coverage.
5. Commit: `feat(records): strict validators and version handling (M2)`.

**Expected:** every invalid case raises `RecordValidationError`; version errors name the version.

---

## Task 3 — Fixtures + schema contract tests (M2 2.5/2.T / #20, #117)

**Deliverable:** valid + invalid record/event fixtures used by tests and later conformance; a
`jsonschema` contract test proving model output matches `schema/*.json`.

**Steps**

1. Add `packages/python-sdk/tests/fixtures/records/{valid,invalid}/*.json` (a handful each) and
   `.../events/{valid,invalid}/*.json`.
2. **RED/GREEN:** add tests that (a) every valid fixture validates, (b) every invalid fixture raises,
   (c) each `to_dict()` output passes `jsonschema.validate` against the published schema files (dev
   extra `jsonschema`).
3. Add `jsonschema` to the SDK `dev` extra (test-first: assert it in `test_packaging_metadata.py`).
4. Re-run; full suite + coverage.
5. Commit: `test(records): fixtures and schema contract tests (M2)`.

**Expected:** fixtures drive parametrized tests; contract test green against both schema files.

---

## Task 4 — M2 docs (M2 2.6/2.D / #21, #118)

**Deliverable:** record-format spec, data dictionary, `schema/README.md`, CHANGELOG, WBS describe the
shipped model + validator.

**Steps**

1. Update `docs/reference/record-format-spec.md` (status, `validate_record`/`validate_event`, version rule).
2. Update `docs/design/data-dictionary.md` and `schema/README.md` to point at `agentwatch.records`.
3. Update `CHANGELOG.md` and WBS Part 2 M2 status; link this plan.
4. Run the docs link-check test.
5. Commit: `docs(m2): document the record and security-event model (M2)`.

**Expected:** link-check green; docs reference real module paths.

---

## Task 5 — Verify/adapt ported SDK core (M3 3.1–3.3 / #22–#24)

**Deliverable:** confirmation that the M0-ported SDK spans, LangGraph adapter, and OTLP/metadata tests
pass and satisfy 3.1–3.3; any small adapt/typing fixes committed with tests.

**Steps**

1. Run `pytest packages/python-sdk -k "tracer or spans or langgraph or otlp"` and read the output.
2. If any ported behavior is missing a test named in the WBS, add it (RED→GREEN) rather than changing code.
3. Update WBS/issue notes for 3.1–3.3 to record that the port satisfies them.
4. Commit: `test(sdk): verify ported spans/LangGraph/OTLP coverage (M3)`.

**Expected:** ported suite green; the three work items are evidenced by named tests.

---

## Task 6 — Claude Code normalize adapter (M3 3.6 / #27)

**Deliverable:** `agentwatch.adapters.claude_code.normalize(raw) -> list[AgentRecord]`; Pre→intent,
Post→outcome; documented gaps.

**Steps**

1. **RED:** `packages/python-sdk/tests/test_claude_code_adapter.py`: a Pre event → one record
   (`step_type="act"`, no `ended_at`); a Post event → outcome record (`outcome="ok"`, `ended_at`/`duration_ms`);
   an error response → `outcome="error"`; `session_id`/`harness="claude-code"` carried; records pass
   `validate_record`; `trace_id/span_id` propagation across Pre→Post for the same tool call.
2. Run; fail.
3. **GREEN:** implement `adapters/claude_code.py` + `adapters/__init__.py` (adapter id/capabilities +
   documented gaps per `adapter-conformance.md`); apply redaction hooks where content is captured.
4. Re-run; full suite + coverage.
5. Commit: `feat(adapters): claude-code Pre/Post normalizer (M3)`.

**Expected:** Pre→intent, Post→outcome; same-call correlation via shared span id; all records valid.

---

## Task 7 — Hook script + UDS client (M3 3.4 / #25)

**Deliverable:** `agentwatch-hook pre|post` console script that reads the event and forwards one
newline-delimited JSON message to the daemon; always exits 0.

**Steps**

1. **RED:** `packages/python-sdk/tests/test_hook.py`: with a stub UDS server, `main(["pre"])` sending a
   JSON event over stdin writes the framed message; a socket failure still exits 0; malformed stdin
   exits 0 (and reports a hook-error via the daemon path).
2. Run; fail.
3. **GREEN:** implement `agentwatch/hook.py` + `[project.scripts] agentwatch-hook = "agentwatch.hook:main"`.
4. Re-run; full suite.
5. Commit: `feat(hook): claude-code hook UDS client (M3)`.

**Expected:** hook never blocks (exit 0 on all paths); message framing covered by tests.

---

## Task 8 — Daemon + UDS server round-trip (M3 3.5 / #26)

**Deliverable:** `agentwatch-daemon` (or `agentwatch daemon run`) serving the UDS, normalizing, and
appending to `<store.path>/records.jsonl`.

**Steps**

1. **RED:** `packages/python-sdk/tests/test_daemon.py`: start the server on a temp socket, send a Pre
   then a Post frame, assert two valid records appended to `records.jsonl` and the session id preserved;
   assert socket file perms are owner-only (0600); assert the server survives a malformed line.
2. Run; fail.
3. **GREEN:** implement `agentwatch/daemon.py` (newline JSON framing, per-line error isolation, JSONL sink).
4. Re-run; full suite + coverage.
5. Commit: `feat(daemon): UDS daemon normalizing hooks to JSONL (M3)`.

**Expected:** hook↔daemon round-trip green; malformed input never kills the daemon.

---

## Task 9 — Hook-error handling F2 (M3 3.7 / #28)

**Deliverable:** a missed hook event is recorded (never dropped) as a `hook-error` record.

**Steps**

1. **RED:** add to `test_daemon.py`/`test_hook.py`: a Post frame arriving without a matching Pre after
   the inactivity window, or an explicit hook-error frame, appends a record with `outcome="error"` and
   `tool.name="hook-error"`; assert it validates.
2. Run; fail.
3. **GREEN:** implement the F2 path (explicit `hook-error` phase from the hook on failure + daemon
   synthesis for an unmatched Post).
4. Re-run; full suite.
5. Commit: `feat(daemon): record hook-error instead of dropping (M3, F2)`.

**Expected:** F2 test green; no path drops an event silently.

---

## Task 10 — Conformance fixtures + documented gaps (M3 3.8 / #29)

**Deliverable:** fixture replay (native events → expected records) plus explicit gap assertions.

**Steps**

1. Add `packages/python-sdk/tests/fixtures/claude-code/` native-event samples + expected records.
2. **RED/GREEN:** parametrized conformance test replaying each fixture through `normalize` and comparing
   to the expected records; a gap test asserting unsupported capability classes are declared and rejected,
   not dropped.
3. Re-run; full suite + coverage.
4. Commit: `test(adapters): claude-code conformance fixtures and gaps (M3)`.

**Expected:** fixtures replay green; gaps asserted explicitly.

---

## Task 11 — M3 docs (M3 3.9/3.D / #30, #120)

**Deliverable:** hook contract, adapter design/conformance, compatibility, README/CHANGELOG, WBS.

**Steps**

1. Update `docs/design/claude-code-hook-contract.md` and `harness-adapter-design.md` to final shapes.
2. Update `docs/reference/adapter-conformance.md` and `compatibility.md`.
3. Update `README.md` quickstart (`init`/`sessions`/`replay` status), `CHANGELOG.md`, and WBS Part 2 M3 status.
4. Run the docs link-check test and the full suite.
5. Commit: `docs(m3): document the claude-code adapter, hook, and daemon (M3)`.

**Expected:** docs match the implementation; link-check green; M2+M3 marked implemented.

---

## Rulings (recorded here so they survive compaction)

- **D1** records in the SDK · **D2** dependency-free validation + dev-only jsonschema contract ·
  **D3** adapter/hook/daemon in the SDK · **D4** UDS path/framing · **D5** M3 JSONL sink ·
  **D6** hook-error convention · **D7** fire-and-forget hook.
