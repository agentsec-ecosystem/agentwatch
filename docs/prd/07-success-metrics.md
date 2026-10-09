# PRD 07 — Success Metrics

**BLUF:** Success is **durable recording and fast forensics** — not installs. The metric that matters is
whether teams keep recording on and can answer "what did that agent do?" quickly, from a backend they own.

**Status:** v0.1.0 · **Parent:** agentsec-ecosystem #209

## Outcome metrics

| Metric | Target | Why this, not installs |
|---|---|---|
| Installs still recording after 30 days ("kept it on") | **>70%** | Retention proves the record is worth keeping |
| Time to answer "what did that agent do?" from a standard backend | **<5 min** | The user outcome, measured end-to-end |
| Secret leaks in stored records (attack pack) | **0** | Trust is binary for a security tool |
| Fresh machine → first recorded tool call | **≤15 min** | The setup promise (R2) |
| Security-event schema adopted by ≥1 non-ecosystem tool | within 12 months | The convention-setting goal (stretch) |
| Replay fidelity (automated) | replay matches raw transcript | R8 evidence |
| Time to first browser view of own record | ≤60 s after `ui`; ≤15 min from a fresh machine | Onboarding truth (CUJ-24) |
| Share of calls with non-`unknown` authorization (native telemetry on) | ≥95% | Oversight claim is real (CUJ-21) |
| Managed-fleet sessions with attestation | ≥99% or explicitly classified | "Was it on?" (CUJ-25) |
| End-to-end hook overhead p99 | within the published budget on macOS/Linux/Windows | Developer trust (CUJ-1) |
| Commits resolvable to a session (corpus) | target set in PRD 53 | Provenance usefulness (CUJ-22) |
| Non-ecosystem consumers of each export (AAT, Agent Trace, OCSF) | ≥1 each | Standards-native moat |

## Release gate (v0.1.0)

The v0.1.0 release is not ready until **all** of the following are true:

- [ ] R1–R8 met, each with its acceptance criterion demonstrated.
- [ ] Replay matches the raw transcript in an automated test.
- [ ] The verification attack pack finds **zero** secrets in stored records.
- [ ] Fresh machine → first recorded tool call in ≤15 min, zero agent-side code changes.
- [ ] Export loads into ≥2 standard OTel backends unmodified.
- [ ] The security-event schema is published and emitted by ≥1 other ecosystem tool.
- [ ] Field test report, release notes, and security audit published (see [release/](../release/)).

## Release gate — v0.2.0-expanded additions (PRD 49–59)

In addition to the v0.1.0 gate and PRD 40 §5:

- [ ] Clean-machine timing published for macOS, Linux, Windows (closes R2 "partial").
- [ ] Two OTel backends proven (closes R4 "partial").
- [ ] No Claude Code call under auto/bypass reported as `user`; `approval` v2 live (CUJ-21).
- [ ] `agentwatch ui` demonstrated from a clean install with no Docker (CUJ-24).
- [ ] Managed-policy install verified on a real managed config, or declared unverified in the matrix (CUJ-25).
- [ ] Plugin4Shell-shape capability drift detected (CUJ-23).
- [ ] A commit resolves to a session on the field-test corpus; Agent Trace export validates (CUJ-22).
- [ ] `suggest-policy`/`what-if` produce no write outside `--out`; measured prompt reduction (CUJ-27).
- [ ] `owasp-asi-2026` report: every row's command runs; no prevention claims (CUJ-18 ext.).
- [ ] Held records survive retention, purge and index rebuild (CUJ-32).

## Anti-metrics (do not optimize)

- GitHub stars, raw install counts, article count — vanity. The "kept it on" rate and time-to-answer are
  the real signals.
- Number of events emitted (volume ≠ signal).

## Measurement plan

- "Kept it on" via an opt-in, anonymous heartbeat **or** a local status the operator can share voluntarily —
  never silent telemetry (privacy baseline).
- Time-to-answer measured in field-test tasks, not asserted.
