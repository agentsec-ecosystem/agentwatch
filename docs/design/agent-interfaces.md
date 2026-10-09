# Design — Agent Interfaces

**BLUF:** How agentwatch exposes the record to agents **safely**: a read-only MCP server (`agentwatch mcp-serve`), a
shipped investigation skill, and a versioned CLI JSON contract. Records are already redacted and (by default) contain no
content; responses are labeled untrusted with record citations; every query is itself recorded as `store-access`.

**Status:** implemented (v0.2.0 M30 AGI-1, 2026-10-07) · **Milestone:** M28 · Sources:
[PRD 55](../prd/55-agent-interfaces-and-policy-from-history.md), [threat-model.md](threat-model.md),
[record-format-spec.md](../reference/record-format-spec.md), ADR-0024 (untrusted data), ADR-0037 (MCP
read-only server threat model).

> **Implemented (M30 AGI-1).** `agentwatch.mcp_server` serves the read-only tool set over local stdio via
> `agentwatch mcp-serve --enable` (off by default). The exposed set is fixed and test-enumerated, responses
> are labeled `untrusted-data` with record citations, results are bounded and rate-limited, and every query
> is appended as a metadata-only `store-access` record. Proving test:
> `packages/python-sdk/tests/test_mcp_server.py`.

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

> **Implemented (M30 AGI-2, 2026-10-07).** The skill ships at
> [`docs/skills/investigation/SKILL.md`](../skills/investigation/SKILL.md). The CLI JSON contract is versioned at
> [`schema/cli/v0.1.0/`](../../schema/cli/v0.1.0/) with its own [`CHANGELOG.md`](../../schema/cli/CHANGELOG.md),
> guarded by `agentwatch.cli_schema` (a read command without a schema, a schema for an unregistered command, or a
> changelog that does not name the current version all fail). A scripted agent reaches documented answers on the
> demo store (proving test: `packages/python-sdk/tests/test_agent_interfaces.py`).

## Testing

- Tool enumeration = read-only set; no mutation path exists (FT-AGI-1).
- Injection fuzz holds; `store-access` recorded per query.
- Scripted agent reaches documented answers on the demo store; uninstall restores byte-identically.

## Decision

ADR-0037 — MCP read-only server threat model. If the review rejects the server, ship AGI-2 (skill + JSON) alone.
