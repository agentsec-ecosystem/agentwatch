# Tutorial 03 — Export to Phoenix

**BLUF:** Send records to a local Phoenix instance over OTLP — after the redaction self-test passes.

```sh
agentwatch export enable --otlp-endpoint http://localhost:4317
# run a session, then open Phoenix and inspect execute_tool spans
```

Verify security events appear as events/annotations. Roll back with `agentwatch export disable`.
