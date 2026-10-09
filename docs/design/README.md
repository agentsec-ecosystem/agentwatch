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
| [authorization-provenance-v2.md](authorization-provenance-v2.md) | Authorization source taxonomy v2, permission mode, `oversight` (v0.2.0-expanded) | proposed |
| [recorder-attestation.md](recorder-attestation.md) | Session-start recorder attestation + config-change observation (v0.2.0-expanded) | proposed |
| [managed-policy-install.md](managed-policy-install.md) | Managed-settings/MDM/plugin install + honest `doctor` (v0.2.0-expanded) | proposed |
| [native-telemetry-join.md](native-telemetry-join.md) | Harness-native OTel ingest + `tool_use_id` join (v0.2.0-expanded) | proposed |
| [capability-supply-chain.md](capability-supply-chain.md) | Skills/plugins/hooks/rules/memory inventory, drift, load attribution (v0.2.0-expanded) | proposed |
| [code-provenance.md](code-provenance.md) | `provenance`, Agent Trace export/ingest, range+hash capture (v0.2.0-expanded) | proposed |
| [local-console.md](local-console.md) | `agentwatch ui` + embedded rebuildable query index (v0.2.0-expanded) | proposed |
| [agent-interfaces.md](agent-interfaces.md) | Read-only MCP server, skill, versioned CLI JSON contract (v0.2.0-expanded) | proposed |
| [policy-from-history.md](policy-from-history.md) | `suggest-policy` + `what-if` (advisory) (v0.2.0-expanded) | proposed |
| [access-and-governance.md](access-and-governance.md) | Fleet access model, access log, notice/DPIA (v0.2.0-expanded) | proposed |
| [legal-hold.md](legal-hold.md) | Legal hold suspends retention/purge with provenance (v0.2.0-expanded) | proposed |
| [environment-fingerprint.md](environment-fingerprint.md) | Environment fingerprint + delta in `diff`/`drift` (v0.2.0-expanded) | proposed |
| [browser-verifier.md](browser-verifier.md) | Offline, zero-network browser evidence verifier (v0.2.0-expanded) | proposed |
| [owasp-asi-mapping.md](owasp-asi-mapping.md) | OWASP Agentic ASI + Skills Top-10 coverage mapping (v0.2.0-expanded) | published |
| [outcomes-signals.md](outcomes-signals.md) | Deterministic outcome facts + recurring failure signatures (v0.2.0-expanded) | proposed |
| [runner-segments.md](runner-segments.md) | Sealed CI/cloud runner segments + chain-of-custody import (v0.2.0-expanded) | proposed |

> The **record format contract** is normative reference: [`../reference/record-format-spec.md`](../reference/record-format-spec.md).
> The former `record-format-design.md` was merged into it.
