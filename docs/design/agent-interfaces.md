# Design — Agent Interfaces

**BLUF:** How agentwatch exposes the record to agents **safely**: a read-only MCP server (`agentwatch mcp-serve`), a
shipped investigation skill, and a versioned CLI JSON contract. Records are already redacted and (by default) contain no
content; responses are labeled untrusted with record citations; every query is itself recorded as `store-access`.

**Status:** proposed (2026-10-05, v0.2.0-expanded) · **Milestone:** M28 · Sources:
[PRD 55](../prd/55-agent-interfaces-and-policy-from-history.md), [threat-model.md](threat-model.md),
[record-format-spec.md](../reference/record-format-spec.md), ADR-0024 (untrusted data).

## Tools (read-only)

`sessions`, `search`, `replay`, `impact`, `blame`, `coverage`, `cost`, `oversight`, `provenance`, `inventory --diff`.
Each returns structured results with record IDs. **No tool mutates** store/config/hooks (a test enumerates tools and
asserts the set is exactly the read-only set).

## Threat posture (ADR-0037)

Giving an agent read access to its own history is a trust surface (OWASP ASI01/ASI06). Controls:

- Local stdio only; opt-in per project; off by default; consent-first install; byte-identical removal.
- Responses carry an **untrusted-data** label and cite record IDs; the client is responsible for treating record content
  as data, never instructions.
- Fuzz corpus of injection-shaped record content must not change tool behavior.
- Bounded result sizes + rate limit; no free-form query language beyond the existing filter grammar.
- Every query appended as `store-access` (S21).

## Skill + JSON contract (AGI-2)

A shipped skill teaches coding agents the investigation workflow (search → replay → impact → evidence) using the CLI
JSON contract; the contract is versioned in `schema/` with the same changelog-enforced stewardship as the record schema.
The HTTP contract is PRD 46 API-1; this covers the CLI.

## Testing

- Tool enumeration = read-only set; no mutation path exists (FT-AGI-1).
- Injection fuzz holds; `store-access` recorded per query.
- Scripted agent reaches documented answers on the demo store; uninstall restores byte-identically.

## Decision

ADR-0037 — MCP read-only server threat model. If the review rejects the server, ship AGI-2 (skill + JSON) alone.
