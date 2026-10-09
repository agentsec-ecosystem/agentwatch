# Recipe — Gateway OTel ingest (LiteLLM / Portkey)

**What:** turn a model **gateway** into a capture point with **no new adapter**.
LiteLLM and Portkey already emit OTLP with canonical OpenTelemetry GenAI
(`gen_ai.*`) spans; point their OTLP export at a file (or our collector) and run:

```sh
agentwatch ingest --format otel <gateway-export.json>   # OTLP JSON or protobuf
```

Records are produced through the same `transcode_otel` mapping every OTel source
uses (design: [`otel-mapping.md`](../design/otel-mapping.md)); the gateway is not a
new capture surface, it is an OTLP producer (D-Q).

## LiteLLM (OTel v2)

LiteLLM's OTel v2 emits a `litellm_request` span per call plus child
`execute_tool` spans, carrying `gen_ai.operation.name`, `gen_ai.request.model`,
`gen_ai.system`, `gen_ai.usage.*`, and `gen_ai.tool.name`. Point the exporter at a
local file/collector, then ingest:

```sh
# LiteLLM emits OTLP; capture to a file (or send to the agentwatch collector)
agentwatch ingest --format otel litellm-otlp.json
```

Mapping: the request span becomes a record with tool/operation `chat`; the tool
span becomes an `execute_tool` record; `gen_ai.conversation.id` is the session.

## Portkey

Portkey's OTel export uses the same `gen_ai.*` vocabulary with a
`portkey.request` span and `portkey.request.id`; ingest identically:

```sh
agentwatch ingest --format otel portkey-otlp.json
```

## Privacy

Gateway payloads can carry prompts/completions under `gen_ai.*` content keys.
**Redaction runs before storage** (DD-06); keep the default metadata-only capture
or pass `--capture` explicitly. No content is ever written unredacted.

## Exact cost (GWY-2)

`gen_ai.usage.*` tokens and a gateway-reported cost
(`gen_ai.usage.cost` / `portkey.cost` / `litellm.cost`) are captured onto the
record. `agentwatch cost` **prefers the exact gateway number** over the local
pricing table and stamps each row `exact`, `estimated`, `mixed`, or `unknown`
(also shown in `--json`), so a gateway deployment reports what the provider
actually charged rather than a table estimate.

## CI coverage

`packages/python-sdk/tests/test_gateway_ingest.py` replays committed fixture
streams (`tests/fixtures/ingest/litellm_otlp.json`,
`tests/fixtures/ingest/portkey_otlp.json`) and asserts they become validated
records — a regression in the gateway recipe fails CI.
