# Architecture Tour

**BLUF:** A guided walkthrough of the recording path — from a harness tool call to a stored, redacted,
hash-chained record, and out to a backend you own.

## The path

The instrumentation SDK, analytics/detector engine, and operator UI are the **ported parity baseline**
(WBS M0); the Claude Code hook adapter, local hash-chained store, and gated OTLP export are delivered in
M3–M5.

1. **Harness** (Claude Code) fires `PreToolUse` (intent) and `PostToolUse` (outcome) hooks.
2. **Adapter** normalizes native events per the [adapter contract](../reference/adapter-conformance.md).
3. **Daemon** receives events over a local socket.
4. **Normalizer + redactor** maps to the [record format](../reference/record-format-spec.md) and applies the
   privacy mode — **before** anything is written (`DD-06`).
5. **Local store** appends the record and links it into a **hash chain** (`DD-07`).
6. **Exporter** (opt-in, gated on the redaction self-test) forwards OTLP to Phoenix/Jaeger/Tempo/Splunk.
7. **Analytics + detectors** summarize runs, roll up fleets, and flag anomalies (v0.2.0+).
8. **Operator UI** surfaces Fleet Health, Run Timeline, Version Compare, Anomaly Inbox, Agent Detail.

## Trust boundaries

- The store is the evidence: append-only, hash-chained.
- Recording **fails closed**: a gap is surfaced, never silent (NFR-8).
- Nothing leaves the host unless export is explicitly enabled.

## Standards seam

Records are OTel GenAI `execute_tool` spans; the security-event schema is the ecosystem's shared contract
(see [OTel mapping](otel-mapping.md)).
