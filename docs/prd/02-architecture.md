# PRD 02 — Architecture

**BLUF:** Harness hooks and MCP/proxy taps feed a **local daemon** that normalizes raw agent activity into
the agentwatch **record format** (OTel GenAI `execute_tool` spans plus the named security-event schema),
**redacts before persisting**, stores locally by default, and optionally exports over OTLP.

**Status:** v0.1.0 · **Parent:** agentsec-ecosystem #209

## Where agentwatch sits

Discovered from the ecosystem's four harness-agnostic interception points
(`LLM gateway`, `MCP authz proxy`, `eBPF/kernel`, `identity/token broker`), agentwatch is the **telemetry
layer below the policy engine**: every interception point emits into it, and the policy engine reads it.

```
harness (Claude Code)          MCP clients / proxy        (later) eBPF / gateway
        │ hooks                        │                          │
        ▼                              ▼                          ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │                     agentwatch daemon                              │
   │  adapter → normalize → REDACT → record (OTel GenAI + sec events)  │
   │                                   │                               │
   │                         local-first store (hash-chained)          │
   └───────────────────────────────┬───────────────────────────────────┘
                                    ▼ opt-in
                         OTLP export → Phoenix / Splunk / Datadog
```

## Components (v0.1.0)

1. **Harness adapter** — Claude Code `PreToolUse` / `PostToolUse` hooks are the first implementation. The
   adapter boundary is an explicit contract (`DD-04`) so Cursor/Codex/Gemini follow without redesign. See
   [harness-adapter-design.md](../design/harness-adapter-design.md).
2. **Local daemon** — receives adapter events over a local socket, normalizes, and writes records.
3. **Record format** — tool-call records + named security events; a versioned schema. This is the
   ecosystem's shared contract. See [record-format-design.md](../design/record-format-design.md).
4. **Redaction layer** — runs at normalization time, *before* storage (`DD-06`); no secret/PII is ever
   persisted.
5. **Local store** — local-first, append-only, hash-chained for tamper evidence (`DD-03`, `DD-07`). See
   [storage-design.md](../design/storage-design.md).
6. **OTLP exporter** — opt-in export to any OpenTelemetry backend. "We ship data, not a dashboard."
7. **CLI** — `agentsec init` (install hooks + daemon), `agentsec sessions`, `agentsec replay <id>`.
8. **Security-event schema** — the named, versioned event vocabulary (`denied`, `policy-fired`,
   `secret-detected`, `revoked`, `halted`) emitted as OTel events.

## Data flow (CUJ-1)

1. User runs `agentsec init` → hooks are registered in Claude Code settings; daemon starts.
2. Claude Code fires `PreToolUse` (intent) and `PostToolUse` (outcome) → daemon.
3. Daemon normalizes → redacts arguments → writes a record with trace context.
4. Records are stored locally; the OTLP exporter forwards them if configured.
5. `agentsec replay <session>` reads the store and reconstructs the ordered timeline.

## Standards

OpenTelemetry GenAI semantic conventions (`execute_tool` spans, agent spans, attribute registry) and W3C
Trace Context for cross-harness correlation. We contribute improvements upstream rather than forking
(`DD-05`). The security-event schema is versioned in public.

## Boundaries

- No alerting, no detection, no analysis (agentpolicy's and agentdrill's jobs).
- No cloud component in v1; not a SIEM.
- Harness-agnostic by format (OTel), pragmatic by adapter (Claude Code first).

## Open questions

- Cursor exposes less scripting surface than Claude Code — is full-fidelity recording possible, or does it
  require proxy interposition for some event classes?
- Security-event schema: steward alone, or propose into the OTel GenAI working group from day one?
