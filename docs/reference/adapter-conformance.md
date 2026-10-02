# Reference — Adapter Conformance

**BLUF:** An adapter is "supported" only when its conformance suite passes. No silent gaps.

Status: **draft**.

## Adapter contract

Each adapter declares: `harness` id, capability classes (pre/post tool-use, MCP events, session
boundaries), and `normalize(raw) -> Record[]`. Unsupported classes are declared as **documented gaps**.

## Conformance suite

- **Fixture replay:** native harness events → expected normalized records.
- **Gap assertions:** declared-unsupported classes must be rejected explicitly, never dropped silently.
- **Cross-harness correlation:** W3C Trace Context survives the adapter.

## Verification

Ecosystem tool **agentdrill** runs per-harness attack packs; a tool is compatible only when its pack passes
in CI. Release notes carry the compatibility table.
