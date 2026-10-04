# agentwatch

[![PyPI version](https://img.shields.io/pypi/v/agentsec-agentwatch.svg)](https://pypi.org/project/agentsec-agentwatch/)
[![Python versions](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-green.svg)](https://github.com/agentsec-ecosystem/agentwatch/blob/main/LICENSE)
[![Status: v0.1.0](https://img.shields.io/badge/status-v0.1.0-green.svg)](https://github.com/agentsec-ecosystem/agentwatch/blob/main/docs/release/v0.1.0/release-notes.md)

**Instrumentation SDK for AI agents** — turn agent behavior into OpenTelemetry GenAI
spans and validated, redacted execution records. Part of
[agentwatch](https://github.com/agentsec-ecosystem/agentwatch).

## Installation

```bash
pip install agentsec-agentwatch
```

Optional extras:

```bash
pip install "agentsec-agentwatch[langgraph]"   # LangGraph adapter
pip install "agentsec-agentwatch[otlp]"        # OTLP export
pip install "agentsec-agentwatch[signing]"     # cryptographic signing helpers
```

Requires Python 3.10+.

## Quickstart

Trace a plain Python agent — no framework required:

```python
from agentwatch.raw import trace_agent
from agentwatch.spans import plan_span, execute_tool_span

@trace_agent("support-bot", agent_version="v0.1.0", model="gpt-4o", provider="openai")
def answer(request: str) -> str:
    with plan_span("decide next action"):
        ...
    with execute_tool_span("search", arguments={"q": request}):
        ...
    return "done"
```

Or drive the run context explicitly:

```python
from agentwatch.config import default_config
from agentwatch.tracer import configure_tracing
from agentwatch.context import RunContext
from agentwatch.instrument import invoke_agent

configure_tracing(default_config())          # once at startup
with invoke_agent(RunContext(agent_name="request-triage")):
    ...
```

LangGraph:

```python
from agentwatch.langgraph import trace_graph

graph = trace_graph(compiled_graph, agent_name="planner")
```

## Privacy

Records are **redacted by default**. Four privacy modes are available per span/tool
call:

| Mode | What is stored |
|---|---|
| `truncated` (default) | Content-safe truncated values |
| `metadata-only` | Names, timings, and counts; no content |
| `hashed` | One-way digests of content |
| `full` | Raw content (opt-in) |

## Record, replay, verify

The same package installs the CLI:

```bash
agentwatch init            # install Claude Code hooks + start the local daemon
agentwatch sessions        # list recorded sessions
agentwatch replay <id>     # reconstruct a session's action timeline
agentwatch verify-store    # verify the hash chain
```

Records are written to a local-first, hash-chained JSONL store; OTLP export is opt-in
and gated on a redaction self-test.

## Documentation

- [SDK reference](https://github.com/agentsec-ecosystem/agentwatch/blob/main/docs/reference/sdk.md)
- [User guide](https://github.com/agentsec-ecosystem/agentwatch/blob/main/docs/guides/user-guide.md)
- [Record format spec](https://github.com/agentsec-ecosystem/agentwatch/blob/main/docs/reference/record-format-spec.md)
- [Docs index](https://github.com/agentsec-ecosystem/agentwatch/blob/main/docs/README.md)
- [Changelog](https://github.com/agentsec-ecosystem/agentwatch/blob/main/CHANGELOG.md) ·
  [Security policy](https://github.com/agentsec-ecosystem/agentwatch/blob/main/SECURITY.md) ·
  [Issues](https://github.com/agentsec-ecosystem/agentwatch/issues)

## License

Apache-2.0 — see [LICENSE](https://github.com/agentsec-ecosystem/agentwatch/blob/main/LICENSE).
