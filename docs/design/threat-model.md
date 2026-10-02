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

## Out of scope (v1)

Multi-tenant isolation; remote attackers with host access; provider-side model compromise.
