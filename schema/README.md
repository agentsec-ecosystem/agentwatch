# Schema

Machine-readable contracts for agentwatch.

| File | Purpose |
|---|---|
| [agent-record.schema.json](agent-record.schema.json) | The tool-call / behavior record |
| [security-event.schema.json](security-event.schema.json) | The named security-event vocabulary |
| [vectors/](vectors/README.md) | Published store/chain conformance vectors + expected-verdict table |

The Python form of these contracts is `agentwatch.records` (`validate_record()` / `validate_event()`);
its output is checked against these files by the contract tests. The OTel GenAI attribute mapping is in
[`../docs/design/otel-mapping.md`](../docs/design/otel-mapping.md).
Schema versions are published and follow a deprecation policy; improvements are proposed upstream to OTel
(DD-05).
