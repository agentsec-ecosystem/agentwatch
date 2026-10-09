# Guide — Record Gemini CLI via native OTel telemetry

**Audience:** operators instrumenting Gemini CLI. **Path:** native OTel (**GEM-1**), not a bespoke adapter
([ADR-0022](../adr/0022-gemini-native-telemetry-ingest.md)).

Gemini CLI ships built-in OpenTelemetry. Point it at a collector, or write to a file and ingest it — either way
agentwatch records it, with the same redaction-before-storage guarantee as every other path.

## Prerequisites

- Gemini CLI with `telemetry` enabled in `.gemini/settings.json`.
- agentwatch installed (`pip install agentsec-agentwatch`).

## Option A — `otlpEndpoint` (collector)

In `.gemini/settings.json`:

```json
{
  "telemetry": {
    "enabled": true,
    "target": "otlp",
    "otlpEndpoint": "http://127.0.0.1:4318",
    "logPrompts": false
  }
}
```

Point `otlpEndpoint` at your OTLP collector, and export the collected spans as JSON for ingestion.

## Option B — `outfile` (local file)

```json
{
  "telemetry": {
    "enabled": true,
    "target": "local",
    "outfile": "/tmp/gemini-telemetry.json",
    "logPrompts": false
  }
}
```

Then ingest the captured file:

```bash
agentwatch ingest --format otel /tmp/gemini-telemetry.json
```

## Redaction is mandatory

`logPrompts` defaults to **true**, so prompts (and any secret they contain) can appear in the telemetry. agentwatch
runs the secrets pipeline over every ingested span **before storage** and raises a `secret-detected` event; even in
`privacy.mode=full` a detected secret is masked (DD-06). Set `logPrompts: false` to avoid capturing prompt content
at the source.

## What is recorded

- Each `execute_tool` / agent span → one record (`harness=otel`, `producer.kind=ingest`), schema-validated.
- `gen_ai.agent.name` → agent identity; `gen_ai.conversation.id` / `session.id` → session.
- Spans that cannot be mapped are quarantined with a reason, never dropped.
- `active_approval_mode` → approval provenance and `user.email` → principal (hashed by default) land in GEM-2.

## Verify

```bash
agentwatch verify-store      # the chain verifies
agentwatch view <session>     # the ingested records appear
```
