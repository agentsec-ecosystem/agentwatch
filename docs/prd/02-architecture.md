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

## Parity components (v0.2.0–v1.0, from the shipped project)

To retain shipped-feature parity ([PRD 10](../prd/10-feature-parity.md)), agentwatch also carries what
shipped in `agent-exec-trace`:

- **Instrumentation SDK** (Python) — `@trace_agent` + `plan/tool/retrieval/memory/approval` spans; LangGraph
  adapter; `AgentTracer` OTLP export; 4 privacy modes; version/workload metadata.
- **Analytics service** — trace ingestion (polling), run summaries, fleet rollup, version cohorts,
  configurable detector thresholds.
- **Detector engine** — 35 rule-based detectors (7 categories) + 5 optional LLM detectors.
- **Read API** (FastAPI) — `/runs`, `/runs/{id}`, `/fleet`, `/compare`, `/anomalies`.
- **Operator UI** (React) — Fleet Health, Run Timeline, Version Compare, Anomaly Inbox, Agent Detail.
- **Local stack** — Jaeger/Tempo + OTel Collector + Postgres + API + Analytics + Web (Docker Compose).

## Runtime & distribution

- **Core: Python** (instrumentation SDK + analytics service + FastAPI) — true parity with the shipped
  `agent-exec-trace` stack (`DD-01`, **accepted**).
- **CLI / launcher:** `npx @agentsec-ecosystem/cli init` is a thin launcher that installs/invokes the Python
  CLI; the Python CLI is also published on PyPI (`pip` / `uvx`).
- **Operator UI:** React (the shipped views: Fleet Health, Run Timeline, Version Compare, Anomaly Inbox,
  Agent Detail).

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

- **Detection/analytics live here** (restored from the shipped project) as **observability signals** — not
  enforcement. Allow/deny/ask decisions belong to agentpolicy; attack packs to agentdrill.
- No cloud component in v1; not a SIEM.
- Harness-agnostic by format (OTel), pragmatic by adapter (Claude Code first, then frameworks via SDK).

## Decisions

- **Cursor (DD-15):** native hooks first; proxy-interpose only event classes native cannot capture.
- **Schema stewardship (DD-05):** propose into the OTel GenAI working group from day one; keep a repo-local copy.
