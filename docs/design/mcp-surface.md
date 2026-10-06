# Design — MCP Tool-Surface Drift

**BLUF:** agentwatch records, once per session and MCP server, the tool surface
that server presented, and emits a `tool-surface-changed` security event when it
moves between sessions. It is the sixth security-event type and the first added
since the original five, so it went through the published schema stewardship
process. It is **observation only** — a surface change is not a malware verdict.

**Status:** published (v0.1.0) · **Milestone:** M20 S4 · Sources:
[PRD 36](../prd/36-standards-and-interop.md), [PRD 14](../prd/14-non-goals.md),
[security-event schema](../../schema/security-event.schema.json).

## Why a record can prove a rug-pull

A rug-pull is an MCP server presenting a trusted tool surface and later changing
it. agentwatch already attributes `mcp__<server>__<tool>` into
`tool.server`/`tool.name`; the missing piece was the time dimension. Comparing
the observed surface across sessions makes the change an after-the-fact fact,
provable from the local store alone.

## Records

- **`mcp-surface` carrier** (one per server per session, metadata only):
  `{"server", "observed": [...], "enumerated": [...], "digest"}`.
- **`tool-surface-changed`** security event:
  `evidence={"server", "added", "removed", "prev_digest", "digest"}`.

`observed` is the set of tool names actually used in the session. `enumerated`
is the set from `tools/list` when the MCP interposition adapter (N1) supplies it.
They are **distinct fields, never merged** — an observed surface under-reports,
and saying so plainly is better than pretending to enumerate.

## Digest and first-sighting rule

`digest = sha256(sorted(observed))[:16]`. A server seen for the first time has no
`prev_digest`, so it emits **no** change event. A change compares consecutive
sessions per server.

## Stewardship

Adding an event type is a schema change, so it follows W5's published process:
the enum in `schema/security-event.schema.json` and `records.SecurityEventType`
move together, the contract test in `tests/test_records.py` pins the vocabulary,
and the mapping is published in [ocsf-mapping.md](ocsf-mapping.md).

## Wording

The event says "surface changed". It does not score trust, block a server, or
call it malicious (PRD 14/36 S4 risk). Consumers such as agentpolicy decide.

## v0.2.0 — protocol revision and full surface

The MCP spec revised to **2026-07-28** ([PRD 42](../prd/42-harness-fidelity-and-realtime.md) MCP-1..6,
[ADR-0023](../adr/0023-mcp-2026-07-28-posture.md)): sessions removed from Streamable HTTP (the proxy gets simpler
and stateless), **Roots/Sampling/Logging deprecated** (SEP-2577), **MRTR** reworks server-initiated requests,
**Tasks** added, **HTTP+SSE deprecated**.

The proxy migrates to **Streamable HTTP** and records the previously-relayed surfaces — `resources/read` (incl.
resource links in tool results), `prompts/get`, **elicitation** (linked to approval provenance S14), and **tasks**
lifecycle — with the same redaction/chain/attribution pipeline. A `resources/read` record and each `resources/link`
observation keep the resource URI in `tool.arguments['uri']`; a `prompts/get` record keeps the prompt name in
`tool.arguments['name']` — all metadata (never the body unless captured). `search --mcp-resource <uri>` finds every
resource access. **Elicitation** is recorded and its answer linked to approval provenance (S14): `accept`→`user`,
`decline`→`denied`, otherwise honest `unknown`. **Tasks** (SEP-2663) are recorded with the task id as metadata;
Roots/Sampling/Logging are **closed-by-spec** (SEP-2577). The streamable transport is **stateless**: because
2026-07-28 removed sessions, the proxy neither requires, forwards, nor emits `Mcp-Session-Id` in either direction,
and `MCP-Protocol-Version` is relayed unchanged. The pre-2026 HTTP/SSE relay is kept for legacy servers
(`agentwatch mcp-proxy --http --transport http-sse`) and is **deprecated-in-spec**. `sampling`/`roots`/`logging` are
marked **closed-by-spec** in `known-limitations.md` (retired by the standard, not by us). Conformance fixtures are
versioned per protocol revision (2025-06-18 / 2025-11-25 / 2026-07-28); `agentwatch.mcp_protocol` is the single
source for the revision→surface matrix, the proxy's tested range tracks the newest revision (protocol drift fails
CI), and the compatibility table carries a **Protocol** column. An unknown method is quarantined and surfaced as
harness-drift (S19).
