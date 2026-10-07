# Examples gallery

Runnable proof that agentwatch works with what you already have. Each recipe is
either **CI-executed** (a test runs it against a fixture, so it cannot rot) or
explicitly **illustrative** (it needs an external service; the reason is listed).

| Recipe | Integration | CI | Notes |
|---|---|---|---|
| [`security_event_consumer.py`](security_event_consumer.py) | security-event stream (hook/daemon) | **executed** | Validates each event against the shipped schema; copy-and-adapt consumer. |
| [`ocsf_consumer.py`](ocsf_consumer.py) | OCSF 1.5.0 → SIEM | **executed** | Validates the OCSF envelope from `export-session --format ocsf`. |
| [`claude_agent_sdk_otel.py`](claude_agent_sdk_otel.py) | Claude Agent SDK / headless OTel | **executed** | Transcodes a native export to `source: sdk-native` records (CCO-2); identity from resource attributes. |
| [`demo-agent/`](demo-agent/) | raw Python SDK → OTLP → collector | illustrative | Needs the `langgraph`/OTLP extras and a collector; see its README. |

The gallery index is enforced by `packages/python-sdk/tests/test_examples_gallery.py`:
a recipe must exist, be indexed here, and — if marked **executed** — pass in CI.

## Run a recipe

```sh
# Security-event consumer (fixture stream)
python examples/security_event_consumer.py --input examples/fixtures/events.ndjson

# OCSF consumer over a session export
agentwatch export-session <session-id> --format ocsf | python examples/ocsf_consumer.py
```
