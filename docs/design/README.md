# agentwatch — Design Documents

Subsystem designs and architecture for agentwatch. Design decisions are centralized in
[design-decisions.md](design-decisions.md) and formalized in [../adr/](../adr/).

| Document | Scope | Status |
|---|---|---|
| [design-decisions.md](design-decisions.md) | Central decision log (DD-01..DD-15) | accepted |
| [architecture-tour.md](architecture-tour.md) | The recording path end to end | draft |
| [observability.md](observability.md) | Emitted signals, attributes, backends, meta-observability | draft |
| [storage-design.md](storage-design.md) | Local-first store + hash chaining | draft |
| [harness-adapter-design.md](harness-adapter-design.md) | Adapter boundary (Claude Code first) | draft |
| [mcp-proxy-design.md](mcp-proxy-design.md) | MCP-client interposition proxy (stdio + HTTP/SSE) | accepted |
| [claude-code-hook-contract.md](claude-code-hook-contract.md) | Exact Claude Code hook + socket protocol | draft |
| [redaction-rules.md](redaction-rules.md) | Secret/PII classes, privacy modes, self-test | draft |
| [privacy-mode-transforms.md](privacy-mode-transforms.md) | Per-mode transform detail | draft |
| [privacy-data-handling.md](privacy-data-handling.md) | Privacy modes, data classes, retention, egress | draft |
| [threat-model.md](threat-model.md) | STRIDE threats + controls | draft |
| [threat-test-traceability.md](threat-test-traceability.md) | Threat → control → test | draft |
| [otel-mapping.md](otel-mapping.md) | OTel GenAI attribute mapping / conformance | draft |
| [performance-budget.md](performance-budget.md) | Per-step budget; throughput; storage growth | draft |
| [sizing.md](sizing.md) | Record volumes and storage growth | draft |
| [data-dictionary.md](data-dictionary.md) | Analytics Postgres schema (v0.2.0+) | draft |
| [ui-accessibility.md](ui-accessibility.md) | Operator UI accessibility baseline | draft |
| [ui-interaction-observability.md](ui-interaction-observability.md) | Local-only UI interaction signals | draft |
| [aat-mapping.md](aat-mapping.md) | IETF Agent Audit Trail mapping, pinning, lossless-or-explicit (v0.2.0) | proposed |
| [agent-identity.md](agent-identity.md) | Agent identity + delegation capture and hashing (v0.2.0) | proposed |
| [streaming-views.md](streaming-views.md) | Streaming views vs store truth; reconciliation (v0.2.0) | proposed |
| [derived-postgres.md](derived-postgres.md) | Derived, rebuildable Postgres index + tenancy (v0.2.0) | proposed |
| [sdk-lifecycle.md](sdk-lifecycle.md) | OTel-shaped provider/lifecycle + security-relevant sampler (v0.2.0) | proposed |
| [cross-harness-testing.md](cross-harness-testing.md) | Payload corpus, replay runner, fidelity tiers (v0.2.0) | proposed |
| [detector-evaluation.md](detector-evaluation.md) | Detector eval harness, public corpus, registry interop (v0.2.0) | proposed |

> The **record format contract** is normative reference: [`../reference/record-format-spec.md`](../reference/record-format-spec.md).
> The former `record-format-design.md` was merged into it.
