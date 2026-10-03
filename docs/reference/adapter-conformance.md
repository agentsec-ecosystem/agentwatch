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

Cursor, Codex CLI, and Gemini CLI ship **provisional (modeled)** adapters — no native event surface is
documented in-repo yet, so the fixtures are synthesized from an assumed shape and must be replaced by real
captures (M14/N4). Each is registered and passes the shared runner; capabilities and the `mcp-server-events`
gap are declared the same way as Claude Code.

| Harness | Module | Fixtures |
|---|---|---|
| Cursor | `agentwatch.adapters.cursor` | `tests/fixtures/cursor/*.json` |
| Codex CLI | `agentwatch.adapters.codex_cli` | `tests/fixtures/codex-cli/*.json` |
| Gemini CLI | `agentwatch.adapters.gemini_cli` | `tests/fixtures/gemini-cli/*.json` |
