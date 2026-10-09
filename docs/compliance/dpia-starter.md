# DPIA starter — AI agent monitoring with agentwatch

> **This is a starter, not legal advice.** A Data Protection Impact Assessment is
> an organisational and legal exercise that must be reviewed by **counsel** and your
> DPO before any employee-monitoring rollout. agentwatch provides the factual,
> config-derived inputs below; it does not make the assessment, and it does not
> certify compliance with GDPR, the EU AI Act, or any other regime.

`agentwatch governance notice` prints the same facts from your **live effective
configuration**. Run it next to this document so the assessment and the notice
cannot drift:

```sh run
agentwatch governance notice
```

## 1. Describe the processing

- **What:** local-first recording of AI-agent tool calls (tool, outcome, timing,
  agent identity), with content redacted before storage.
- **Why (purpose):** security monitoring, auditability, and evidence for incident
  response. *State your own lawful basis; the tool does not.*
- **Who:** operators on whose behalf an agent acts (on-behalf-of principals), and
  the fleet/console readers governed by the role × data-class model.

## 2. Necessity and proportionality

- **Data minimisation:** the default fleet profile is `privacy.mode=metadata-only`
  — no prompt or tool-argument content is stored, and on-behalf-of principals are
  keyed-hashed (not reversible by agentwatch).
- **Access control:** `agentwatch access matrix` publishes who may read which data
  class; every cross-user read is recorded and the subject can list it with
  `agentwatch access log --owner <id>`.
- **Storage limitation:** `store.retention_days` (or a named retention profile)
  drives `agentwatch retention apply`, which tombstones records past the window.
- **Erasure:** `agentwatch purge <session> --yes` tombstones a subject's session
  while preserving the hash chain; a legal hold can suspend retention/purge for a
  scope (see [legal-hold](../design/legal-hold.md)).

## 3. Risks to data subjects

| Risk | Mitigation | Evidence / command |
|---|---|---|
| Employee monitoring without notice | Config-derived notice + this DPIA starter | `agentwatch governance notice` |
| Over-broad reader access | Least-privileged role × data-class model; cross-user reads recorded | `agentwatch access matrix`, `agentwatch access log` |
| Content/surveillance creep | Metadata-only default; content gated on the stored mode | `agentwatch privacy.mode` in `config explain` |
| Indefinite retention | Retention window + tombstone (never hard-delete) | `agentwatch retention apply --dry-run` |
| Irreversible deletion during litigation | Legal hold suspends purge; an override needs a recorded reason | `agentwatch hold list` |
| Secret/PII leakage into the record | Redact-before-store; protected-term detector | `agentwatch verify-privacy` |
| Egress beyond the machine | Export/sinks are opt-in and named in the notice | `agentwatch config explain export.enabled` |

## 4. Sign-off

- [ ] Purpose and lawful basis documented (organisation).
- [ ] Notice reviewed by counsel; `agentwatch governance notice` attached.
- [ ] Role assignment (who is `team-reviewer` / `security-auditor` / `admin`)
      documented — see [access-and-governance](../design/access-and-governance.md).
- [ ] Retention window and holds agreed with legal.
- [ ] DPO sign-off.

*agentwatch supports this assessment; it does not replace it.*
