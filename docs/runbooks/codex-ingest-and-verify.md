# Runbook — Codex CLI ingest & verify

Goal: record Codex CLI from its documented rollout logs (`~/.codex/sessions/…`).

> **Status: reader pending (COD-1 / #339 blocked).** The Codex rollout reader is not yet shipped;
> this runbook documents the intended flow and the mandatory safety posture so the gap is explicit,
> not silent. `CODEX_HOME` / `CODEX_SESSIONS_DIR` override the sessions directory for testing.

```sh
# Intended (once COD-1 lands):
agentwatch ingest ~/.codex/sessions --agent codex
agentwatch sessions
agentwatch replay <session-id>
```

## Verify (intended)

- [ ] A dangling session ends `crashed`/`inferred`, not silent.
- [ ] Duplicated message text is deduped (appears in multiple places in the rollout).
- [ ] `.jsonl.zst` rollouts are read (zstd support); unknown top-level types are skipped for forward-compat.

## Safety (non-negotiable)

- Rollout content is **attacker-influenced**: no ingest/reader path spawns a shell or evaluates foreign content
  (Codex #36937: a rollout JSONL executed as shell input deleted a user's HOME). Redaction + B4 quarantine are
  mandatory; `producer: import`, `source: log-read`.
- Fidelity stays **modeled until a real capture + cross-parser validation (XHT-3, #352)** land.
