# ADR-0024 — Foreign-data threat posture

- **Status:** accepted (2026-10-05, v0.2.0) — implemented
- **Context:** see [PRD 48](../prd/48-v0.2.0-risks-testing-and-decisions.md) R5 and
  [design/threat-model.md](../design/threat-model.md). Codex issue #36937: a session rollout JSONL was placed in a
  shell program position and executed, deleting a user's HOME.
- **Decision:** Every foreign input (AAT, rollouts, transcripts, gateway OTLP, ACS frames) is treated as
  **untrusted data, never executable**. No ingest/reader path ever spawns a shell or evaluates foreign content;
  redaction + B4 quarantine are mandatory; `replay` is render-only; evidence bundles label content untrusted. A
  regression seed encodes the #36937-shaped payload.
- **Consequences:** Containment is a hard rule and a fuzz/property gate; a whole class of "record layer executes
  hostile log" incidents is closed by construction.
