# Runbook — Gemini CLI install & verify

Goal: record Gemini CLI via its built-in OpenTelemetry telemetry (a settings flip
plus `ingest`), and confirm the approval/principal attributes.

```sh
# 1. Enable telemetry in .gemini/settings.json and point it at a local sink.
#    {
#      "telemetry": {
#        "enabled": true,
#        "target": "local",
#        "otlpEndpoint": "http://localhost:4318",
#        "outfile": "/tmp/gemini-telemetry.log"
#      }
#    }
#    logPrompts defaults true — redaction is mandatory on this path.

# 2. Ingest the captured telemetry:
agentwatch ingest /tmp/gemini-telemetry.log --format otel

# 3. Confirm the mapped dimensions:
agentwatch search --session <session-id> --json   # approval + hashed principal
```

## Verify

- [ ] Telemetry reaches the collector/outfile (check before ingest).
- [ ] `agentwatch ingest` validates records; unmappable spans are quarantined with a reason.
- [ ] `active_approval_mode` maps to `approval`; `user.email` is a **hashed** principal; ids map to identity.

## Notes / limitations

- Full fidelity is a **settings flip**, not an adapter — Gemini has no hooks.
- The principal is hashed by default (IDN-1); plaintext requires `full` mode (operator consent).
- Attribute shapes are **modeled** until a live capture lands; version-pinned fixtures + a drift job guard them.
