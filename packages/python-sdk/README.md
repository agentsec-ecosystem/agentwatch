# agentwatch SDK

Instrumentation SDK for `agentwatch`: OpenTelemetry-style observability for AI
agent workflows.

## Installation

```bash
pip install agentwatch
```

Add optional extras for LangGraph integration or OTLP export:

```bash
pip install agentwatch[langgraph]   # LangGraph adapter
pip install agentwatch[otlp]        # OTLP export extras
```

Published on [PyPI](https://pypi.org/project/agentwatch/).

## Overview

The SDK turns agent behavior into OpenTelemetry spans and attributes so runs can be
inspected in Jaeger, Tempo, or any OTLP-compatible backend, then analyzed by the
`agentwatch` analytics service.

## Status

Under active development for `v0.1.0`. Milestones tracked in `docs/wbs-v0.1.0.md`.
