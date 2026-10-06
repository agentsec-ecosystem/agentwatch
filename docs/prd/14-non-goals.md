# PRD 14 — Non-Goals (Consolidated)

**BLUF:** What agentwatch deliberately will **not** do — so scope stays honest.

**Status:** v0.1.0 + v0.2.0 additions (2026-10-05) · **Parent:** agentsec-ecosystem #209

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

## v0.2.0 additions — explicitly not to add (PRD 40–48)

The v0.2.0 program keeps every line above and adds these clarifications:

- **Not enforcement, even when we consume enforcement output.** ACS ingest (PRD 45) records a Guardian's
  permit/deny decisions; agentwatch never executes a decision. A2A agent-card signature verification is
  *recorded*, never silently trusted as an authorization (ADR-0025).
- **Not a browser extension / browser-agent capturer.** Browser-resident agents (Atlas/Comet/… ) are a declared
  gap; capturing them needs a browser trust surface we deliberately do not build (PRD 45).
- **Not an incident *submitter*.** `evidence --include incident-report.json` (PRD 43) emits a file; submission to
  AIID/AIR is a human act. No auto-egress exists (proved by test).
- **Not a general OTel backend / not OTLP/gRPC *export* as a product.** OTLP/gRPC *ingest* (PRD 41) is a
  transcoder, not a storage backend (D-Q holds).
- **Not a certification or conformity claim.** The compliance report (PRD 44) cites evidence; it never certifies.
  Naming/rename is a decision (ADR-0026), not a scope expansion.
- **No LLM in the trust path, ever.** Detector telemetry and the eval harness (PRD 43) judge detectors; detectors
  judge nothing; the sampler (PRD 46) is deterministic.

## v0.2.0-expanded additions — explicitly not to add (PRD 49–59)

The expanded program keeps every line above and adds these clarifications:

- **Not an enforcement tool, even when we generate policy.** `suggest-policy`/`what-if` (PRD 55) emit *inert artifacts*
  and simulations; agentwatch never applies a permission rule, and `agentpolicy` is the named consumer. Wording is
  "suggestion/simulation", never "policy applied".
- **Not a dashboard product.** The local console (PRD 54) is the *reference viewer of the record* — read-only, loopback,
  no accounts, no hosted offering; it supports the evidence mission and does not compete with observability platforms.
- **No built-in alerting rules.** Event forwarding stays rule-free (S10); `NTF-1` ships *recipes* that route events in the
  user's own stack (Slack/PagerDuty/Alertmanager).
- **Not a scanner or an enforcer of capabilities.** `CAP`/`MEM` (PRD 52) record and diff skills/plugins/hooks/memory;
  they never scan content for malice, block a load, or claim a capability is malicious.
- **Not a certifier.** The OWASP ASI coverage map (PRD 59) cites evidence or says "not evidenced"; it never certifies.
- **No LLM in the outcome/analytics path.** `OUT` facts (PRD 58) are deterministic; LLM-judged quality stays in
  agentdrill.
- **No agentwatch-initiated egress.** Pulls/imports (Compliance API, runner segments) and registry exports are explicit
  user acts; tested as such.
- **We generate suggestions; we do not apply them.** (Restates the first bullet as a standing rule.)

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
