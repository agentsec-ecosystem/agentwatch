# Reference — Instrumentation SDK

**BLUF:** Two-line instrumentation for raw Python and LangGraph, emitting OTel GenAI spans. Preserved from
the shipped project (DD-12).

Status: **draft**.

```python
from agentwatch import AgentTracer, trace_agent, tool_span

AgentTracer.setup(otlp_endpoint="http://localhost:4317")

@trace_agent(agent_name="my-agent", agent_version="1.0.0")
async def handle(query: str) -> str:
    with tool_span("search", tool_args={"q": query}):
        ...
```

## Span helpers

`plan_span`, `tool_span`, `retrieval_span`, `memory_span`, `approval_span`.

## LangGraph

`TracedGraph` instruments nodes automatically.

## Privacy modes

`metadata-only` (default), `truncated`, `hashed`, `full`.

## Metadata

`agent_name`, `agent_version`, `workload_type`; optional `prompt_version`, `model_version`,
`tool_schema_version`.

## Compatibility

The shipped `agent-exec-trace` import path is preserved via a shim; see the migration guide.
