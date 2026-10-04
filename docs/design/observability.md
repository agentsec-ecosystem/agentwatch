# Observability

**BLUF:** What agentwatch emits (its own signals) and what it records (agent signals), and the backends it
targets.

## Emitted signal

- **OTel GenAI spans** — `execute_tool` for tool calls; child spans for plan/retrieval/memory/approval.
- **Security events** — `denied`, `policy-fired`, `secret-detected`, `revoked`, `halted`, `drift-detected`.
- **Trace context** — W3C `trace_id`/`span_id` for cross-harness correlation.
- **Fleet rollups** (M11 R13) — opt-in, self-hosted aggregation of a host's local store into a
  self-hosted aggregate, grouped by host/agent/version (`agentwatch fleet`). No egress.
- **Drift signals** (M11) — a `drift-detected` event when a stored metric deviates from its **trailing
  baseline** (rolling mean/stdev, never a fixed threshold), optionally correlated with deployment markers
  (`agentwatch drift`). Signals are observations only — no enforcement; the CLI exits `0`.

## Attributes

Mapping of agentwatch fields to OTel attributes: [design/otel-mapping.md](otel-mapping.md).

## Backends

Phoenix · Jaeger/Tempo · Splunk · Datadog · any OTLP endpoint. Export is opt-in and gated on the redaction
self-test (DD-09).

## Agentwatch about itself (meta)

Recording health is visible — "couldn't read the run" is distinguished from "clean run" (the AgentObservatory
lesson). Agentwatch surfaces its own status rather than failing silently (NFR-12).
