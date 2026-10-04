# Tutorial 02 — Instrument a LangGraph Agent

**BLUF:** Two-line instrumentation for a LangGraph agent.

```python
from agentwatch import AgentTracer, TracedGraph

AgentTracer.setup(otlp_endpoint="http://localhost:4317")

graph = TracedGraph(my_state_graph, agent_name="request-triage", agent_version="1.0.0")
```

Run the graph; node executions become spans. Add `tool_span("search")` inside a node to capture tool calls.
Choose a [privacy mode](../design/privacy-data-handling.md) before enabling export.
