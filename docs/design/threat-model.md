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

## v0.2.0 additions

New trust surfaces and the controls that bound them ([PRD 48](../prd/48-v0.2.0-risks-testing-and-decisions.md)):

| Threat | Scenario | Control |
|---|---|---|
| **Foreign-data weaponization** | A rollout/transcript/gateway dump contains executable-shaped content that a consumer evaluates (Codex #36937: a rollout JSONL executed as shell input deleted a user's HOME) | Untrusted-data rule ([ADR-0024](../adr/0024-foreign-data-threat-posture.md)): no ingest/reader path spawns a shell or evaluates foreign content; redaction + B4 quarantine mandatory; `replay` render-only; bundles label content untrusted; regression seed in the fuzz suite |
| **Streaming side-channel** | A poisoned/low-latency live view diverges from the chain | Views are derived; store is authoritative; back-fill reconciles; gaps classified (S2) — [ADR-0018](../adr/0018-streaming-views-vs-store-truth.md) |
| **Proxy-surface growth** | More wire surface (MCP full surface + A2A) → more attacker-reachable parsing | Same containment as MCP: fuzz, bounded buffers, quarantine; **A2A card-signature verification is a recorded outcome, never silently trusted** ([ADR-0025](../adr/0025-a2a-interposition.md)) |
| **Compliance-API pull** | Egress-adjacent vendor pull leaks credentials or expands the trust boundary | Explicit opt-in; pulls recorded as `store-access` (S21); credentials session-scoped, never stored |
| **Identity-field abuse** | Principals/SPIFFE refs/emails create a surveillance surface | Hashed by default in metadata-only; operator consent for plaintext identity ([ADR-0020](../adr/0020-agent-identity-dimension.md)) |

### v0.2.0-expanded additions (PRD 49–59)

| Threat | Scenario | Control |
|---|---|---|
| **Authorization laundering** | A classifier or bypass-mode approval recorded as human consent | Authorization taxonomy v2 ([ADR-0027](../prd/49-authorization-and-oversight.md)); fixtures + no inference from `outcome=ok` |
| **Managed-policy silent inertness** | The recorder is blocked by `allowManagedHooksOnly` and reports "installed" | Managed install + honest `doctor` ([managed-policy-install](managed-policy-install.md)); attestation |
| **Capability rug-pull** | A plugin/skill's content changes while its pin/version does not | Content-digest inventory + `capability-changed` ([capability-supply-chain](capability-supply-chain.md)) |
| **Attestation forgery** | A same-user attacker writes a fake attestation | Not preventable; detectable by cross-checks with native telemetry; published non-claim ([recorder-attestation](recorder-attestation.md)) |
| **Console CSRF / DNS-rebinding** | A web page reaches the local console | Loopback-only + per-launch token + host-header check + no mutation endpoints ([ADR-0036](local-console.md)) |
| **Agent reads its own record** | Poisoned record content steers an agent via the MCP server | Read-only tools; untrusted labeling; metadata-only default; fuzz ([agent-interfaces](agent-interfaces.md)) |
| **Derived-index erasure drift** | Purge/hold not propagated to the index/exports | Holds + propagation to all derived stores ([legal-hold](legal-hold.md), EXT-5) |
| **Provenance over-claim** | Human work attributed to the agent, or vice versa | Confidence labels; "no recorded activity" wording; mixed ranges ([code-provenance](code-provenance.md)) |
| **Runner segment tampering** | A forged CI/cloud segment imported as if locally witnessed | Segments verify independently; imported records visibly weaker ([runner-segments](runner-segments.md)) |

## Out of scope (v1)

Multi-tenant isolation (addressed at the derived-index layer in v0.2.0, [ADR-0019](../adr/0019-derived-postgres-index.md));
remote attackers with host access; provider-side model compromise.
