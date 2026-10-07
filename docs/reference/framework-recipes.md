# Reference — Certified Framework Recipes

**BLUF:** agentwatch is a **transcoder, not an OTel backend** (D-Q). Instead of a
hand-written adapter per framework, each certified recipe routes a framework's own
OpenTelemetry into the **shared** `agentwatch ingest --format otel` path, where the
[OTel GenAI](../design/otel-mapping.md) and [OpenInference](https://github.com/Arize-ai/openinference)
attribute vocabularies are mapped onto records with an **explicit `unmapped`
bucket**. Each recipe is pinned, held to an O1 conformance pack, and carries an
honest tier in the [compatibility matrix](compatibility.md).

Source: [PRD 51 §FWK-1](../prd/51-harness-native-telemetry-and-framework-reach.md) ·
Design: [native-telemetry-join](../design/native-telemetry-join.md).
Single source of truth: `agentwatch/frameworks.py` (the generator for the table
below). Drift canary: `scripts/check_framework_drift.py` +
`.github/workflows/framework-drift.yml`.

## Tiers

| Tier | Meaning |
|---|---|
| `live-verified` | a real, pinned framework run captured continuously |
| `fixture-verified` | a real capture committed as a fixture |
| `modeled` | the attribute shape is documented/assumed, **not captured here** |

**No recipe in this milestone is `live-verified` or `fixture-verified`:** the
frameworks are not installable in the sandbox that builds M29, so every row is
`modeled`, backed by a shape-derived fixture and a CI conformance pack. The live
pinned run is **BLOCKED** with the exact reason on the recipe and is *never faked*.

## Recipes

| Framework | Pinned | Source vocabulary | Tier | Live run |
|---|---|---|---|---|
| Google ADK (`google-adk`) | `1.5.0` | OTel GenAI (`gen_ai.*`) | modeled | BLOCKED — not installable in CI sandbox |
| Strands Agents (`strands-agents`) | `1.0.0` | OTel GenAI (`gen_ai.*`) | modeled | BLOCKED — not installable in CI sandbox |
| OpenAI Agents SDK (`openinference-instrumentation-openai-agents`) | `0.1.0` | OpenInference (`openinference.*`, `llm.*`) | modeled | BLOCKED — not installable in CI sandbox |
| Claude Agent SDK (`claude-agent-sdk`) | `0.1.0` | shared Claude Code OTel (CCO-1) | modeled | BLOCKED — depends on 29.CCO-1 (WS-A) |

### Google ADK · `1.5.0`

```sh
export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317  # agentwatch collector
python my_adk_app.py  # ADK emits GenAI spans over OTLP
```

ADK emits `invoke_agent` / `invoke_workflow` / `generate_content` spans with
`gen_ai.*` attributes. Identity comes from `gen_ai.agent.name` (falling back to the
resource `service.name`).

### Strands Agents · `1.0.0`

```sh
export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317  # agentwatch collector
python my_strands_agent.py  # Strands emits gen_ai.* spans over OTLP
```

Strands emits agent/model/tool spans with `gen_ai.*` attributes over standard OTLP.

### OpenAI Agents SDK · `0.1.0` (OpenInference)

```python
from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor; OpenAIAgentsInstrumentor().instrument()
export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317  # agentwatch collector
```

The Arize OpenInference instrumentor emits `openinference.span.kind`
(`AGENT`/`LLM`/`TOOL`/`CHAIN`/`RETRIEVER`), `tool.name`, `agent.name`,
`llm.model_name`, `llm.token_count.*` and `llm.cost.total`. agentwatch maps those
onto records (identity from `agent.name`/resource `service.name`; cost from
`llm.cost.total`).

### Claude Agent SDK · `0.1.0`

```sh
# Claude Agent SDK runs the Claude Code CLI; enable its shared OTel export (CCO-1)
export CLAUDE_CODE_ENABLE_TELEMETRY=1 OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317
```

The Agent SDK runs the same CLI and emits the same telemetry as Claude Code. It
routes through the **shared** Claude Code OTel ingest owned by **29.CCO-1 (WS-A)**;
agentwatch does **not** ship a second Claude Code ingest. The `tool_use_id` join to
hook records is CCO-1's, so until it lands the `tool_use_id` attribute is reported
in the explicit `unmapped` bucket — visible, not silently dropped.

## Mapping contract (`agentwatch.ingest`)

- **Identity**: span attributes win over resource attributes; `gen_ai.agent.name`
  → `agent.name` → resource `service.name` → `otel`.
- **Step mapping**: `gen_ai.operation.name` (`invoke_agent`/`invoke_workflow`/
  `execute_tool`/`generate_content`/…) and `openinference.span.kind`
  (`AGENT`/`LLM`/`TOOL`/`CHAIN`/`RETRIEVER`) map to a tool/step name; a span with an
  end time records as `observe`, an open span as `act` (unchanged ingest rule).
- **Cost**: `gen_ai.usage.cost` / `gen_ai.usage.total_cost` (GenAI) and
  `llm.cost.total` (OpenInference) become `cost_usd`; token totals come from
  `gen_ai.usage.total_tokens` or `llm.token_count.total`.
- **Provenance**: the ingestion `source` is stamped on the record's `producer`
  (`kind: ingest`), so an ingested framework stream is distinguishable from a
  default stream. No record-schema change.
- **`unmapped`**: every attribute key the transcoder did not consume is returned in
  an explicit, sorted `unmapped` tuple (and `IngestStats.unmapped`). A vendor or
  framework attribute addition is therefore surfaced for a human, never dropped.
  This is what makes the Claude Agent SDK's CCO-1 dependency honest: `tool_use_id`
  shows up as unmapped until the shared ingest owns it.

## CI

- Fixture conformance: `packages/python-sdk/tests/test_frameworks.py` (attribute
  mapping, identity, step, cost, explicit `unmapped`, tiers, drift).
- O1 conformance packs: `packages/python-sdk/tests/framework_conformance_registry.py`
  (`framework-adk`, `framework-strands`, `framework-openai-agents`,
  `framework-claude-agent-sdk`).
- Drift job: `scripts/check_framework_drift.py` vs
  `tests/fixtures/frameworks/upstream.json`; scheduled by
  `.github/workflows/framework-drift.yml`.
- Gallery recipe: `examples/framework_recipes.py`.
