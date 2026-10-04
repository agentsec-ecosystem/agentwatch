"""agentwatch SDK: execution traces for agent behavior.

========================================================
What this package provides
========================================================
A thin, OTel-native instrumentation layer that turns an agent run into a coherent
trace tree -- one root ``invoke_agent`` span containing nested ``plan``,
``execute_tool``, ``retrieval``, and ``memory`` spans -- plus privacy-safe
redaction, so the same run is comparable across frameworks and visible in Jaeger.

========================================================
Public API surface
========================================================

Core building blocks
--------------------
  * :func:`agentwatch.tracer.configure_tracing` --
    Bootstrap the OTel tracer provider. Call once at startup.
  * :func:`agentwatch.tracer.configure_otlp_tracing` --
    Same as above but attaches an OTLP gRPC exporter for production backends.
  * :func:`agentwatch.tracer.get_tracer` --
    Return the active tracer (fallback to OTel global if not configured).
  * :func:`agentwatch.tracer.reset_tracing` --
    Tear down the provider (test isolation / reconfiguration).

Run identity
------------
  * :class:`agentwatch.context.RunContext` --
    Frozen identity + metadata carrier for one agent run.  Holds agent name,
    version, workload type, model, provider, and an auto-generated run id and
    start timestamp.  Passed into ``invoke_agent`` to stamp the root span.

Root span entry point
---------------------
  * :func:`agentwatch.instrument.invoke_agent` --
    Context manager that opens the root ``invoke_agent`` span.  Every adapter
    (and the ``@trace_agent`` decorator) funnels through this function so the
    root shape is always consistent.

Nested behavior span helpers
---------------------------
  * :func:`agentwatch.spans.plan_span` --
    Open a ``plan`` child span (agent deciding what to do next).
  * :func:`agentwatch.spans.tool_span` --
    Open an ``execute_tool`` child span with default redaction (TRUNCATED mode,
    tool args captured).  Convenience wrapper requiring no redaction config.
  * :func:`agentwatch.spans.execute_tool_span` --
    Open an ``execute_tool`` child span with explicit redaction control.
  * :func:`agentwatch.spans.retrieval_span` --
    Open a ``retrieval`` child span (RAG / vector-search lookup).
  * :func:`agentwatch.spans.memory_span` --
    Open a ``memory`` child span (set / get / delete).
  * :func:`agentwatch.spans.record_event` --
    Attach a structured, timestamped event to an existing span.

Privacy / redaction
-------------------
  * :class:`agentwatch.redact.PrivacyMode` --
    Enum controlling HOW content is handled: metadata-only, truncated, or hashed.
  * :class:`agentwatch.redact.RedactionConfig` --
    Frozen config that gates which fields (prompts, tool args, memory) are
    captured and with what transformation.  This is the trust boundary for
    sensitive data -- no sensitive content reaches a span without passing
    through ``RedactionConfig.apply()``.

Configuration
-------------
  * :class:`agentwatch.config.SDKConfig` --
    Frozen dataclass holding runtime settings (service name, OTLP endpoint,
    default agent metadata, redaction config).
  * :func:`agentwatch.config.default_config` --
    Convenience factory returning a ``SDKConfig`` with truncated content capture
    (tool args enabled by default).  Use ``PrivacyMode.METADATA_ONLY`` if your
    deployment requires zero content on spans.

Semantic-convention attribute keys
----------------------------------
  * :mod:`agentwatch.attrs` --
    Centralized mapping of standard GenAI attribute keys (``gen_ai.operation.name``,
    ``gen_ai.agent.name``, etc.), provisional extension keys, and span operation
    name constants (``plan``, ``execute_tool``, etc.).  Never hard-code a key string
    anywhere else -- this file is the single source of truth.

Adapter layers
--------------
  * :func:`agentwatch.raw.trace_agent` --
    Decorator that wraps a plain Python agent function in ``invoke_agent`` on
    every call.  The "no-framework" onboarding path.
  * :func:`agentwatch.langgraph.trace_graph` --
    Wrap a compiled ``CompiledStateGraph`` so every ``invoke()`` produces a traced
    run with node-mapped behavior spans.
  * :class:`agentwatch.langgraph.TracedGraph` --
    The wrapped graph object returned by ``trace_graph``.

========================================================
Typical usage
========================================================

::

    from agentwatch.config import default_config
    from agentwatch.tracer import configure_tracing
    from agentwatch.context import RunContext
    from agentwatch.instrument import invoke_agent, set_output
    from agentwatch.spans import plan_span

    configure_tracing(default_config())   # once at startup
    with invoke_agent(RunContext(agent_name="request-triage")):
        with plan_span("decide next action"):
            ...

========================================================
Version
========================================================
"""

__version__ = "0.1.0"
