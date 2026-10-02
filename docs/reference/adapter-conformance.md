# Reference — Adapter Conformance

**BLUF:** An adapter is "supported" only when its conformance suite passes. No silent gaps.

Status: **implemented** for Claude Code (v0.1.0 M3).

## Adapter contract

Each adapter declares: `harness` id, capability classes (pre/post tool-use, MCP events, session
boundaries), and `normalize(message) -> list[AgentRecord]`. Unsupported classes are declared as
**documented gaps**.

## Conformance suite

- **Fixture replay:** native harness events → expected normalized records.
- **Gap assertions:** declared-unsupported classes must be rejected explicitly, never dropped silently.
- **Cross-harness correlation:** W3C Trace Context survives the adapter.

## Claude Code (v0.1.0)

- Fixtures: `packages/python-sdk/tests/fixtures/claude-code/*.json` (`message` + `expected` records).
- Tests: `packages/python-sdk/tests/test_conformance.py` (fixture replay, gap-vs-capability disjointness,
  unsupported-capability rejection).
- Declared gaps: `session-boundaries`, `mcp-server-events` (each is rejected explicitly when presented as
  a hook phase — see `test_conformance.py::test_each_declared_gap_is_rejected_explicitly`).
- Adapter: `agentwatch.adapters.claude_code`.

## Verification

Ecosystem tool **agentdrill** runs per-harness attack packs; a tool is compatible only when its pack passes
in CI. Release notes carry the compatibility table.
