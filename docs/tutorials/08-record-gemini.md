# Tutorial 08 — Record Gemini CLI via telemetry

Gemini CLI emits OpenTelemetry natively. Recording it is a settings flip plus an
`ingest`, and its attributes carry authorization + identity you would otherwise
infer.

## 1. Turn on telemetry

In `.gemini/settings.json`, enable the `telemetry` block and point `otlpEndpoint`
at your collector (or use `outfile` for a local capture). `logPrompts` defaults to
true, so the redaction pipeline runs on this path.

## 2. Ingest and inspect

```sh
agentwatch ingest /tmp/gemini-telemetry.log --format otel
agentwatch sessions
agentwatch search --session <session-id> --json
```

## 3. What you should see

- `active_approval_mode` → `approval` (`auto`→`auto`, `on-request`→`user`, `never`→`denied`).
- `user.email` → a **hashed** on-behalf-of `principal` (plaintext only under `full`).
- `installation.id` → agent identity; `session.id` → session correlation.

See the [runbook](../runbooks/gemini-install-and-verify.md). Attribute shapes are modeled
until a live capture lands, with version-pinned fixtures + a drift job.
