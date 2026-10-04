# Runbook — Export to OTLP

Goal: send records to a backend you own (Phoenix, Jaeger/Tempo, Splunk, Datadog).

```sh
agentwatch export enable --otlp-endpoint http://localhost:4317
```

## Preconditions

- [ ] **Redaction self-test passed** (export is blocked until it does — DD-09).
- [ ] Destination is intended; no silent endpoints.

## Verify

- [ ] Traces appear in the backend with `execute_tool` spans.
- [ ] Security events appear as events/annotations.

## Rollback

```sh
agentwatch export disable
```
