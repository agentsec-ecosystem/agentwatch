# Design — OTel GenAI Attribute Mapping

**BLUF:** How agentwatch records map onto OpenTelemetry GenAI semantic conventions. Conformance is explicit
and versioned; improvements go upstream (DD-05).

Status: **draft** (v0.1.0).

## Span mapping

| agentwatch concept | OTel GenAI |
|---|---|
| tool call | `execute_tool` span |
| agent run | agent span |
| plan/retrieval/memory/approval | child spans |
| session | trace (`trace_id`) |
| cross-harness correlation | W3C Trace Context |

## Attribute mapping (indicative)

| agentwatch field | OTel attribute |
|---|---|
| `tool.name` | `gen_ai.tool.name` |
| `tool.server` | `mcp.server` (proposed) |
| `agent.identity` | `gen_ai.agent.name` |
| `model` | `gen_ai.request.model` |
| `outcome` | span status |

## Security events

Emitted as OTel events/annotations on the span (naming/versioning per DD-14, proposed upstream).

## Conformance

Tracked against `open-telemetry/semantic-conventions-genai`; breaking upstream changes are versioned.
