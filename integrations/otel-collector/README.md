# agentwatch OTel Collector component (reference)

> **Reference, not a supported product.** The mapping lives in agentwatch
> (`agentwatch/otel_component.py`); this component is deliberately thin so
> collector API churn does not touch the mapping (PRD 36 S39).

The receiver reads the local agentwatch store (`records.jsonl`) and emits
GenAI-semconv spans so records load into a standard backend unmodified.

## Pinned semantic conventions

The receiver reports `otel.semconv.version` (currently **1.29.0**) on every
span's resource attributes. W4 (M22) formalizes the upstream proposal.

## Using it

1. Copy [`config.yaml`](config.yaml) and point `receivers.agentwatch.path` at
   your store.
2. Replace the `debug` exporter with your backend (OTLP, Jaeger, …).
3. Run your collector build that includes the `agentwatchreceiver`.

## Behavior

- **No store / empty store** → the receiver reports `unavailable` and emits
  nothing; it never fabricates spans.
- **Export only** — read-only on the store; no ingestion back into agentwatch.
