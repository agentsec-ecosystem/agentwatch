# agentwatch v0.1.0 — Release Notes

Status: **unreleased** (template).

## Highlights

- First release: records every Claude Code tool call in OpenTelemetry GenAI format, redacted by default.
- The open security-event schema (`denied`, `policy-fired`, `secret-detected`, `revoked`, `halted`) published.
- Local-first storage; opt-in OTLP export; session replay.

## Install

```sh
npx @agentsec-ecosystem/cli init
```

## Compatibility

- Claude Code (v0.1.0). Cursor/Codex/Gemini follow in v0.2–v0.3.

## Security

See `security-audit.md` (added at release).
