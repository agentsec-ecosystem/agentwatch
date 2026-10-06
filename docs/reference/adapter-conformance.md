# Reference — Adapter Conformance

**BLUF:** An adapter is "supported" only when its conformance suite passes. No silent gaps.

Status: **implemented** for Claude Code (v0.1.0 M3).

## Adapter contract

Each adapter declares: `harness` id, capability classes (pre/post tool-use, MCP events, session
boundaries), and `normalize(message) -> list[AgentRecord]`. Unsupported classes are declared as
**documented gaps**.

## Conformance suite

A shared, reusable runner (`agentwatch.conformance`, M5 O1 #216) holds every
registered adapter to the same bar, blocking in CI (`assert_registered_conform`):

- **Fixture replay:** native harness events → expected normalized records.
- **Gap assertions:** declared-unsupported classes must be rejected explicitly, never dropped silently.
- **Record validation:** every normalized output is validated (`validate_record`, reject-never-coerce).
- **Dedup/idempotency:** normalizing the same event twice is deterministic.
- **Cross-harness correlation:** W3C Trace Context survives the adapter.

Each adapter registers an `AdapterSpec` (name, `normalize`, capabilities, documented
gaps, error class, fixtures dir). A shipped adapter with no registration fails CI;
a deliberately-broken sample adapter is asserted to fail the runner
(`tests/test_conformance_runner.py`).

Every registered adapter must also ship a **populated pack**: `conformance.assert_packs_populated()` fails
CI when a harness has no fixtures or a case lacks `message`/`expected`
(`tests/test_conformance_packs.py`, M10 #85).

## Claude Code (v0.1.0)

- Fixtures: `packages/python-sdk/tests/fixtures/claude-code/*.json` (`message` + `expected` records),
  including `post_failure.json` for a failed `PostToolUseFailure` tool call (`outcome="error"`).
- Tests: `packages/python-sdk/tests/test_conformance.py` (fixture replay, gap-vs-capability disjointness,
  unsupported-capability rejection).
- Capability classes: `pre-tool-use`, `post-tool-use`, `post-tool-use-failure`.
- Declared gaps: `session-boundaries`, `mcp-server-events` (each is rejected explicitly when presented as
  a hook phase — see `test_conformance.py::test_each_declared_gap_is_rejected_explicitly`).
- Adapter: `agentwatch.adapters.claude_code`.

## Verification

Ecosystem tool **agentdrill** runs per-harness attack packs; a tool is compatible only when its pack passes
in CI. Release notes carry the compatibility table.

## Provisional adapters (M10, modeled)

Codex CLI and Gemini CLI ship **provisional (modeled)** adapters — no native event surface is
documented in-repo yet, so the fixtures are synthesized from an assumed shape and must be replaced by real
captures (M14/N4). Each is registered and passes the shared runner; capabilities and the `mcp-server-events`
gap are declared the same way as Claude Code.

| Harness | Module | Fixtures |
|---|---|---|
| Codex CLI | `agentwatch.adapters.codex_cli` | `tests/fixtures/codex-cli/*.json` |
| Gemini CLI | `agentwatch.adapters.gemini_cli` | `tests/fixtures/gemini-cli/*.json` |

## Cursor native hooks (v0.2.0 M25, CUR-2)

`agentwatch.adapters.cursor` normalizes Cursor's native `hooks.json` events. The pack
(`tests/fixtures/cursor/*.json`) covers the full loop: session boundaries, pre/post tool use (+failure),
shell, MCP, `beforeReadFile`, file edits, subagent start/stop, prompt submission, compaction,
`afterAgentThought`/`afterAgentResponse`, Tab hooks, and `workspaceOpen`. The declared gap is
`cloud-agent-hook-events` (cloud agents lack sessionStart/sessionEnd/MCP/Tab/workspace hooks), rejected
explicitly. Blocking `before*` events are recorded as observations and never answered (monitor-only, R2).
Field names follow the published contract, and the audit corpus (25.CUR-1) is version-tagged and
secret-scanned under `tests/testkit/` (`PROVENANCE.md`), so the fidelity tier is `fixture-verified`.

## Tier-2 framework adapters (M10 10.6, modeled)

CrewAI and PydanticAI ship **provisional (modeled)** record adapters — the native event surface is assumed,
so the fixtures are synthesized-from-shape and must be replaced by real captures (M14/N4). Both register in
the shared runner and pass every check. (The in-process PydanticAI instrumentation wrapper is separate and
lives in `agentwatch.pydantic`.)

| Harness | Module | Fixtures | Capabilities | Gaps |
|---|---|---|---|---|
| CrewAI | `agentwatch.adapters.crewai` | `tests/fixtures/crewai/*.json` | `agent_start`, `agent_end`, `task_start`, `task_end`, `tool_usage` | `mcp-server-events`, `crew-memory`, `delegation` |
| PydanticAI | `agentwatch.adapters.pydantic_ai` | `tests/fixtures/pydantic-ai/*.json` | `agent_run_start`, `agent_run_end`, `tool_call`, `tool_result` | `mcp-server-events`, `stream-events` |

## MCP interposition proxy (M10 N1)

The proxy adapter records MCP `tools/call`, `resources/read`, and `prompts/get` request/response frames relayed
from an MCP server; each record carries `tool.server` attribution and the request/response pair shares a `span_id`
derived from the JSON-RPC id. A resource link in a tool result is recorded as a `resources/link` observation. The
resource URI / prompt name is metadata in `tool.arguments` (`search --mcp-resource` finds resource reads).

- Fixtures: `packages/python-sdk/tests/fixtures/mcp-proxy/*.json` (`tools-call-request.json`,
  `tools-call-response.json`, `resources-read-request.json`, `resources-read-response.json`,
  `prompts-get-request.json`, `prompts-get-response.json`).
- Adapter: `agentwatch.adapters.mcp_proxy`.
- Capability classes: `mcp-tools`, `mcp-resources`, `mcp-prompts`.
- Declared gaps: `mcp-sampling` — relayed by the proxy but not recorded;
  each is rejected explicitly when presented to `normalize`.
