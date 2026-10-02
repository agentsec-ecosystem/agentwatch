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
