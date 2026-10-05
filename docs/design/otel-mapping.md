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
| agent id/version | `gen_ai.agent.id`, `gen_ai.agent.version` |
| conversation/session | `gen_ai.conversation.id` |
| provider discriminator | `gen_ai.provider.name` |
| operation name | `gen_ai.operation.name` (`invoke_agent`, `plan`, `execute_tool`, …) |
| content capture | opt-in content vs metadata-only (privacy-mode ↔ capture-ladder mapping) |

## Security events

Emitted as OTel events/annotations on the span (naming/versioning per DD-14, proposed upstream).

## v0.2.0 — agent-span alignment and OTLP/gRPC

The semconv moved to the dedicated `open-telemetry/semantic-conventions-genai` repository and now defines **agent
spans**. v0.2.0 ([PRD 41](../prd/41-standards-and-interop-ii.md) OTEL-1..4):

- Align operations to the canonical set: `create_agent`, `invoke_agent` (client/internal), `invoke_workflow`,
  `plan`, `execute_tool`, plus skills (`load skill`, `read skill resource`, command execution).
- Re-pin the semconv version; carry it in `--version` + resource attributes; drift-check (W4).
- Add **OTLP/gRPC + protobuf ingest** (streaming) alongside JSON.
- State the privacy-mode ↔ content-capture mapping explicitly; metadata-only by default.

## Conformance

Tracked against `open-telemetry/semantic-conventions-genai`; breaking upstream changes are versioned. The pinned
version is stated wherever a record is exported.
