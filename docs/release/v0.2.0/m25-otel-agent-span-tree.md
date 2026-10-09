# M25 evidence — OTel agent-span tree in a reference backend

Trace `c8f563d588fb2574ad239bfceef38b32` from service `agentwatch-m25-evidence`, exported through the SDK's
`configure_otlp_tracing` path to the local collector (`:4317`) and rendered from the
Jaeger HTTP API. Raw trace: `m25-otel-agent-span-tree.json`.

```
- `invoke_agent` [request_triage] (0.1 ms)
  - `execute_tool` [search_kb] (0.0 ms)
  - `plan` (0.0 ms)
  - `execute_tool` [lookup_account] (0.0 ms)
  - `create_agent` [triage-subagent] (0.0 ms)
    - `execute_tool` [escalate] (0.0 ms)
```
