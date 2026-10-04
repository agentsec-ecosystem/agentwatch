# PRD 14 — Non-Goals (Consolidated)

**BLUF:** What agentwatch deliberately will **not** do — so scope stays honest.

**Status:** v0.1.0 · **Parent:** agentsec-ecosystem #209

- **Not an enforcement tool.** No allow/deny/ask/rate-limit actions — those are **agentpolicy**.
- **Not an evaluation/attack framework.** No attack packs or CI gates — those are **agentdrill**.
- **No injection/intent classification as a security boundary.** The rule+LLM anomaly *signals* retained
  from the shipped project are observability signals, not enforcement.
- **Not a cloud service or SIEM (v1).** Local-first; exports data to a backend you own.
- **Not a general LLM-call observability tool.** We record agent behavior + security events, not prompt
  analytics.
- **Not fleet commercial discovery.** Local inventory only; fleet aggregation is opt-in/self-hosted (R13).
- **No silent telemetry.** No hidden phone-home; measurement is local and shared voluntarily.
- **No proprietary formats.** OTel GenAI + open, versioned security-event schema only.

## Additions — explicitly not to add (PRD 19–30)

The additions never cross these lines: enforcement (→ agentpolicy) · attack/eval framework
(→ agentdrill) · injection/intent classification as a security boundary · cloud service/SIEM in
v1 · prompt analytics · commercial fleet discovery · silent telemetry · proprietary formats.
Several additions (`doctor`, `inventory`, evidence) stop deliberately at *local, read-only, no
phone-home*, and the LLM explanation layer (PRD 29) keeps ML out of the trust path permanently.

## Considered and rejected for now (scope honesty — say why)

- **Store encryption at rest** — expands the threat model (key management, recovery) for marginal
  v1 gain; local-only + least-privilege file posture (PRD 28) + user-level disk encryption is the
  v1 posture. Revisit with enterprise.
- **Blockchain/external chain anchoring** — PRD 18: "don't claim what you can't prove";
  checkpoints (PRD 21) + evidence bundles deliver the real need without the theater.
- **Decision/blocking hooks** — contradicts monitor-only (R2); enforcement is agentpolicy.
- **Cloud sync / hosted mode** — non-goal; fleet (R13) is the sanctioned multi-host shape.
- **LLM in the redaction/validation path** — the trust boundary stays deterministic (PRD 29); an
  LLM that *decides* redaction makes "0 leaks" unprovable.
- **SDK→local-store unification** (SDK spans also chaining into the JSONL store) — genuine idea,
  but two producers on one chain needs ordering + identity design; fold into v0.2.0 Postgres
  analytics where SDK data lands anyway.
- **A TUI framework dependency** — `view` (PRD 26) stays stdlib or nothing; anything heavier waits
  for the React UI (M7).
