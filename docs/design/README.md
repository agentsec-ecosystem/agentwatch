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

> The **record format contract** is normative reference: [`../reference/record-format-spec.md`](../reference/record-format-spec.md).
> The former `record-format-design.md` was merged into it.
