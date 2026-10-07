# Reference — Compliance reports

**BLUF:** `agentwatch compliance report` renders a framework's controls as
**control → evidence command → verdict → refs**, offline, from the local store
and the active configuration, plus retention and checkpoint-signature status.
It produces **evidence, not a certification**.

## Command

```sh
agentwatch compliance report --framework eu-ai-act-art12 [--period P] [--out FILE] [--json]
```

Frameworks: `generic`, `eu-ai-act-art12`, `iso-42001`, `iso-27001`, `soc2`,
`nist-800-92` (templates added by CMP-2).

### Framework templates (CMP-2)

Each framework renders its own control vocabulary, mapped to the generic
computed checks above:

| Framework | Control ids | Maps to (checks) |
|---|---|---|
| `eu-ai-act-art12` | `art12-1-automatic-logging`, `art12-2-retention`, `art12-3-traceability`, `art12-4-integrity` | log-integrity, retention, identity, checkpointing |
| `iso-42001` | `aims-logging`, `aims-retention`, `aims-identity`, `aims-evidence` | log-integrity, retention, identity, evidence |
| `iso-27001` | `a8-15-logging`, `a8-24-storage`, `a5-33-evidence` | log-integrity, redaction, evidence |
| `soc2` | `cc7-1-monitoring`, `cc6-1-access`, `cc7-2-coverage` | log-integrity, redaction, coverage |
| `nist-800-92` | `log-management-integrity`, `log-retention`, `log-protection`, `log-accountability` | log-integrity, retention, redaction, identity |
| `generic` | the default catalog (7 controls) | — |

Templates are offline and every row still names a regenerating command.

## Rows

Each row is computed, never asserted:

| Control | Evidence command | Verdict from |
|---|---|---|
| `log-integrity` | `agentwatch verify-store` | the hash chain verifies |
| `redaction-default` | `agentwatch verify-privacy` | `privacy.mode` is not `full` |
| `retention-configured` | `agentwatch retention apply` | a retention window is set (cites the active profile) |
| `checkpointing` | `agentwatch checkpoint` | `store.checkpoint_every` is set |
| `recording-coverage` | `agentwatch coverage` | `unknown` without a transcript |
| `identity-attribution` | `agentwatch search --identity` | records carry an on-behalf-of/workload identity |
| `evidence-bundle` | `agentwatch evidence <session>` | a session exists to bundle |

A verdict is `pass`, `fail`, or `unknown`; a row with no evidence fails rather
than being omitted. Every row names a command that regenerates it.

## Retention & signature status

- **Retention** reports the configured window against the oldest retained
  record; a record older than the window degrades to `overdue`.
- **Checkpoints** are reported honestly: signing is opt-in and off by default,
  so an unsigned report says so — hash integrity is not attributability.

## Not a certification

The report states, verbatim, that it is evidence of configuration and recorded
activity for *this installation* — not a certification, not an opinion, and not
an attestation of any human's identity. Compliance language stays in
non-conformity terms ([PRD 44](../prd/44-identity-enterprise-and-compliance.md)).
