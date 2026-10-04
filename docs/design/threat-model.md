# Design — Threat Model

**BLUF:** agentwatch is part of the security path, so its own threats are modeled explicitly. Recording must
never fail silently, leak secrets, or be a vector itself.

Status: **draft** (v0.1.0).

## Assets

Records; the store; hook/daemon config; the event stream (consumed by other tools).

## STRIDE

| Threat | Scenario | Control |
|---|---|---|
| **Spoofing** | A process impersonates the daemon/socket | Local socket perms; identity checks |
| **Tampering** | Records edited/deleted | Hash chain (DD-07) |
| **Repudiation** | "The agent didn't do that" | Ordered, correlated records |
| **Information disclosure** | Secrets/PII persisted or exported | Redaction before storage (DD-06); export gated (DD-09) |
| **Denial of service** | Hook/daemon disabled → silent stop | Fail-closed + health surfaced (NFR-8/12) |
| **Elevation of privilege** | Poisoned hook config executes code | Config validation; least privilege; signed releases |

## Abuse of agentwatch as a vector

- Malicious adapter/harness input → strict normalization + schema validation.
- Export endpoint as exfiltration → explicit opt-in only; no defaults.

## Recorder as an attack target

The recorder runs as the same user as the agent, so an on-box attacker can stop the daemon, rewrite the
store, strip hooks, or skew the clock. The published [recorder attack matrix](recorder-attack-matrix.md)
(M16 S30) states, per scenario, what is preventable, what is detectable after the fact, and which
command evidences it — every "neither" row paired with its compensating control (S2 coverage / S5 state
records).

## Content-flow fingerprints

The M18 content-flow observation and secret exposure path store only **keyed** HMAC-SHA256 fingerprints
(per-install key at `<store>/flow.key`, `0600`, or `AGENTWATCH_HMAC_KEY`) — never the matched content.
This blunts a confirmation attack: an attacker who exfiltrates the store cannot confirm a guessed
plaintext without the key. It does **not** prevent an attacker who also has the key (the same user can
read it by definition); the control reduces the blast radius of a store leak, not same-user access.
See [content-flow.md](content-flow.md).

## Out of scope (v1)

Multi-tenant isolation; remote attackers with host access; provider-side model compromise.
