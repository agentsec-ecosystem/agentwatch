# Migration Guide — `agent-exec-trace` → `agentwatch`

**BLUF:** Existing `agent-exec-trace` users keep working. The instrumentation API and read-API shapes are
preserved; a shim maps the old import path to agentwatch (DD-12).

Status: **draft** (v0.1.0).

## What changes

| Before | After |
|---|---|
| `pip install agent-exec-trace` | `pip install agentwatch` (shim keeps the old import working) |
| `from agent_exec_trace import AgentTracer, trace_agent, tool_span` | same names, re-exported by `agentwatch` |
| `TracedGraph` (LangGraph) | unchanged |
| Read API `/api/runs` … | same shapes |
| Jaeger/Tempo + Postgres stack | same at v0.2.0; v0.1.0 adds a local JSONL store |

## Steps

1. `pip install agentwatch`.
2. Replace the import root (or keep it via the shim): `agent_exec_trace` → `agentwatch`.
3. Point `AgentTracer.setup(otlp_endpoint=...)` at the same collector.
4. Verify recording; run the redaction self-test before enabling export.

## Compatibility promises

- Instrumentation call shapes (`@trace_agent`, span helpers, `TracedGraph`, privacy modes) stay source-compatible.
- Read API field shapes stay compatible; additions are additive.
- Any unavoidable break ships with a codemod or a documented step here.
