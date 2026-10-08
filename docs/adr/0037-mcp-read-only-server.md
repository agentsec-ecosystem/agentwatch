# ADR-0037 — MCP read-only server threat model

- **Status:** accepted (2026-10-07, v0.2.0 M30) — implemented
- **Context:** see [PRD 55](../prd/55-agent-interfaces-and-policy-from-history.md) §AGI-1 and
  [design/agent-interfaces.md](../design/agent-interfaces.md). Observability vendors ship MCP+CLI surfaces
  "for agents"; agentwatch holds the record of what agents did but exposed no agent-usable interface. Giving
  an agent read access to its own history is itself a trust surface (OWASP ASI01/ASI06), and record content
  is foreign data that may be injection-shaped (see [ADR-0024](0024-foreign-data-threat-posture.md)).
- **Decision:** `agentwatch mcp-serve` serves a **small, read-only** tool set over local stdio —
  `sessions`, `search`, `replay`, `impact`, `blame`, `coverage`, `cost`, `oversight`, `provenance`,
  `inventory` — under these controls:
  - **Read-only by construction.** The exposed set is fixed and enumerated by a test; every tool advertises
    `readOnlyHint`; there is no mutating tool (no store/config/hook write path).
  - **Untrusted labeling + citations.** Every response is labeled `untrusted-data` with record-id citations;
    the client must treat record content as data, never instructions. Redaction already happened before
    storage, and metadata-only captures carry no raw content to inject.
  - **Injection fuzz.** Injection-shaped record content cannot change tool behavior (a fuzz test asserts the
    label/behavior holds and only the store-access record is appended).
  - **Bounded + rate-limited.** Result sizes are capped and tool calls are rate-limited.
  - **Audited reads.** Every query is appended as a metadata-only `store-access` record (S21), reusing the
    store-access vocabulary; the records carry a tool name, a session scope, and a count — no payload.
  - **Off by default.** The server is opt-in (`--enable`, consent-first); disabling it leaves the store
    byte-identical to a run without it.
- **Consequences:** Agents can query the record safely without an enforcement or mutation surface. If the
  server is ever rejected, AGI-2 (the skill + versioned CLI JSON contract) still ships alone. No free-form
  query language is exposed beyond the existing filter grammar.
