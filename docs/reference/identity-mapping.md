# Reference — Agent identity mapping (agentwatch ↔ AIMS/WIMSE ↔ NCCoE)

**BLUF:** How agentwatch's `agent_identity` dimension (IDN-1..4) maps to the three reference
architectures an enterprise or federal reviewer is likely to cite, so the record layer can be
*compared* rather than guessed at. agentwatch is not a conformant implementation of any of them; this
is a **concept mapping**, honest about what agentwatch records and what it leaves `unknown`.

Sources: [v0.2.0 research sources](v0.2.0-research-sources.md) §identity · design
[agent-identity](../design/agent-identity.md) · PRD 44 §IDN-1..4.

## The three references

| Reference | What it is | Identifier / credential vocabulary |
|---|---|---|
| **IETF AIMS** `draft-klrc-aiagent-auth-00` (Mar 2026) | Composes WIMSE + SPIFFE/SPIRE + OAuth 2.0 into an Agent Identity Management System: agents are workloads. | WIMSE URI; X.509-SVID / JWT-SVID / WIT |
| **WIMSE for agents** `draft-ni-wimse-ai-agent-identity-01` (Oct 2025) | A credential denotes *both* the agent and its human owner (delegation binding). | Workload identity + delegation proof |
| **NIST NCCoE** concept paper (Feb 2026) | Workstreams: Identification, Access Delegation, **Logging and Transparency**, prompt/data-flow provenance. | (Concept questions, not a wire format) |

## Field mapping

`agentwatch` records the identity dimension additively (`schema/agent-record.schema.json`,
`agent_identity`); where a harness does not expose a fact the value is an honest `unknown` — never
inferred. `principal` and each `delegation_chain` entry are hashed by default under `metadata-only`
(`agentwatch.identity`).

| agentwatch concept | Record field | AAT export block | AIMS / WIMSE | NCCoE workstream |
|---|---|---|---|---|
| Agent logical identity | `agent.name` / `agent.identity` | `identity` | Agent workload / WIMSE URI subject | Identification |
| Agent version | `agent.version` | `agent.version` | Workload attribute | Identification |
| Harness / model | `harness`, `agent.model_version` | `harness` / `model` | Workload attribute | Logging & Transparency |
| Workload identity | `agent.workload_identity` | `workload_identity` | **WIMSE URI / SPIFFE ID** | Identification |
| Credential class | `agent.credential_class` (`api-key` \| `oauth` \| `svid` \| `ambient/shared`) | `credential_class` | Credential type (SVID / OAuth / WIT) | Identification; **credential hygiene** |
| On-behalf-of principal | `agent.principal` (hashed by default) | `principal` | Human-owner identity (delegation) | Access Delegation |
| Delegation chain | `agent.delegation_chain` (hashed by default) | `delegation_chain` | Delegation binding / RFC 8693 token exchange | Access Delegation |
| Approval provenance | security-event `approval` / `policy_id` | (security events) | Cryptographic proof of user approval | Access Delegation |
| Attribution on reads | `attribution_for()` in `blame`/`tree`/`trace`/`impact` | — | — | Logging & Transparency |

## Credential hygiene (IDN-4)

The NCCoE *Identification* workstream and NIST's pre-Q4-2026 audit ask call out over-privileged
non-human identities — agents running on **shared/ambient** credentials. agentwatch records the
credential *class* (never the value) and exports it as the `agentwatch.credential_class` span
attribute; the deterministic `credential-hygiene` detector
(`analytics.detectors.identity.CredentialHygieneDetector`) flags a run that acted under
`ambient/shared`. It is an **observation, not a verdict**: it names the class the trace stated and is
silent when the credential is `unknown`. It never blocks a run, and an operator can switch it off
per-deployment with `detector_disabled` (the analytics per-detector toggle).

## Deliberate non-claims

- agentwatch does **not** issue, rotate, or revoke agent credentials; it observes the class under
  which an agent acted. Credential lifecycle is the enterprise IdP / secrets layer's job
  (e.g. Vault SPIFFE auth).
- agentwatch does **not** verify workload attestation; a `workload_identity` is recorded when the
  harness exposes it and is never assumed.
- A2A signed agent cards (v1.0) can supply cryptographic workload identity; the verification outcome
  is recorded (`verified`/`unverified`) and is never treated as authorization (ADR-0025).
