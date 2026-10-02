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

## Release gate (v0.1.0)

The v0.1.0 release is not ready until **all** of the following are true:

- [ ] R1–R8 met, each with its acceptance criterion demonstrated.
- [ ] Replay matches the raw transcript in an automated test.
- [ ] The verification attack pack finds **zero** secrets in stored records.
- [ ] Fresh machine → first recorded tool call in ≤15 min, zero agent-side code changes.
- [ ] Export loads into ≥2 standard OTel backends unmodified.
- [ ] The security-event schema is published and emitted by ≥1 other ecosystem tool.
- [ ] Field test report, release notes, and security audit published (see [release/](../release/)).

## Anti-metrics (do not optimize)

- GitHub stars, raw install counts, article count — vanity. The "kept it on" rate and time-to-answer are
  the real signals.
- Number of events emitted (volume ≠ signal).

## Measurement plan

- "Kept it on" via an opt-in, anonymous heartbeat **or** a local status the operator can share voluntarily —
  never silent telemetry (privacy baseline).
- Time-to-answer measured in field-test tasks, not asserted.
