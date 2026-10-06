# Design — OTel GenAI Attribute Mapping

**BLUF:** How agentwatch records map onto OpenTelemetry GenAI semantic conventions. Conformance is explicit
and versioned; improvements go upstream (DD-05).

Status: **draft** (v0.1.0); **OTEL-1 re-pinned to 1.37.0** (canonical agent spans) and **OTEL-2** added the
privacy-mode ↔ content-capture mapping below (v0.2.0, M25); **OTEL-3** added OTLP protobuf/gRPC ingest
(streaming, auto-detected under `--format otel`; M26).

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

### OTLP protobuf / gRPC ingest (OTEL-3)

`agentwatch ingest --format otel <source>` auto-detects input: valid JSON takes the
unchanged JSON path, and a bare OTLP protobuf `ExportTraceServiceRequest` is decoded via
`opentelemetry-proto` and normalized into the same `transcode_otel` mapping (trace/span
ids base64→hex, so records carry the OTLP hex ids). `--format otlp-grpc` decodes a
gRPC length-prefixed stream frame by frame (`iter_grpc_messages`), so a large file is
never fully loaded; compressed frames are rejected, not mis-decoded. The protobuf path is
optional (`agentsec-agentwatch[otlp]`); without it the JSON path is unaffected. Undecodable
bytes are quarantined with a reason (B4), never dropped.

The reader's conformance is `packages/python-sdk/tests/test_otlp_protobuf_ingest.py`
(bare-message decode, auto-detection, JSON unchanged, no-whole-stream-load, compressed
frame rejection, streaming ingest, bounded-memory decode). The 100 MB budget is enforced by
the perf harness (PERF-1).

**Ingest recipes (GWY-1):** gateways that already emit OTLP are capture points, not new adapters —
[`guides/gateway-otel-ingest.md`](../guides/gateway-otel-ingest.md) (LiteLLM OTel v2 / Portkey),
[`guides/gemini-native-telemetry.md`](../guides/gemini-native-telemetry.md) (Gemini CLI). Each ships a
committed fixture stream replayed in CI.

## Privacy mode ↔ content capture (OTEL-2)

| Privacy mode | Content attribute keys | Metadata attribute keys |
|---|---|---|
| `metadata-only` | **none, ever** | all |
| `truncated` | capped content | all |
| `hashed` | salted digests | all |
| `full` | raw content (consent) | all |

The record→span mapping is **metadata-only by construction**: `record_to_attributes` emits no
content-bearing key (`gen_ai.tool.args`, `gen_ai.tool.result`, `gen_ai.response.content`,
`gen_ai.agent.output`, `gen_ai.plan.content`, `gen_ai.node.output`, `gen_ai.memory.content`). The guard
`export.exported_content_keys()` returns the content keys present in an attribute mapping; the OTEL-2
property test proves it is always empty for the metadata path, so no content escapes the active mode.

## Conformance

Tracked against `open-telemetry/semantic-conventions-genai`; breaking upstream changes are versioned. The pinned
version is stated wherever a record is exported.
