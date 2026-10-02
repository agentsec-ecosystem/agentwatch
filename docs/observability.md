# Observability

**BLUF:** What agentwatch emits (its own signals) and what it records (agent signals), and the backends it
targets.

## Emitted signal

- **OTel GenAI spans** — `execute_tool` for tool calls; child spans for plan/retrieval/memory/approval.
- **Security events** — `denied`, `policy-fired`, `secret-detected`, `revoked`, `halted`.
- **Trace context** — W3C `trace_id`/`span_id` for cross-harness correlation.

## Attributes

Mapping of agentwatch fields to OTel attributes: [design/otel-mapping.md](design/otel-mapping.md).

## Backends

Phoenix · Jaeger/Tempo · Splunk · Datadog · any OTLP endpoint. Export is opt-in and gated on the redaction
self-test (DD-09).

## Agentwatch about itself (meta)

Recording health is visible — "couldn't read the run" is distinguished from "clean run" (the AgentObservatory
lesson). Agentwatch surfaces its own status rather than failing silently (NFR-12).
