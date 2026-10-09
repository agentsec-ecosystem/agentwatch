# Design — Agent Identity & Delegation

**BLUF:** How agent identity is captured, hashed, and rendered onto records so that *which non-human entity, under
which credential, on whose behalf, with whose approval* is answerable end to end. **How** — the requirement is
[PRD 44](../prd/44-identity-enterprise-and-compliance.md) (IDN-1..4).

**Status:** 🚧 partially implemented (2026-10-05, v0.2.0) · **Milestone:** M25 · Sources:
[PRD 44](../prd/44-identity-enterprise-and-compliance.md), PRD 35 (S14/S29), IETF AIMS/WIMSE, AAT draft.

> **Implementation (M25 IDN-1):** the field set below is in the record schema (`schema 0.2.0`) and the
> principal-hashing policy is implemented in [`agentwatch.identity`](../../packages/python-sdk/src/agentwatch/identity.py):
> `apply_identity_privacy()` hashes `principal` and each `delegation_chain` entry with a per-install keyed
> HMAC by default and keeps plaintext only under the `full` mode; `scrub_identity()` guarantees identity
> fields never carry secret material (PII such as an email principal is the dimension's legitimate subject
> and is hashed, not masked). The Claude Code adapter attaches the dimension from optional hook fields.
> **IDN-2 (M26):** the Claude Code adapter captures the on-behalf-of `principal`, `workload_identity`,
> `credential_class`, and `delegation_chain` from optional hook fields (absent stays honestly unknown; never
> inferred), `identity_handles()` enumerates every handle on a record, and `agentwatch search --identity <handle>`
> matches any of them (case-insensitive substring). AAT export already populates the identity block.
> **IDN-3 (M26):** `agentwatch.identity.attribution_for()` renders one `Attribution` (agent, credential class,
> on-behalf-of, delegation chain, approval) shown identically in `blame`, `tree`, `trace`, and `impact` (`--json`
> and text), so a multi-agent fixture answers "which agent, under which credential, on whose behalf, with what
> approval" in one command (CUJ-16). **IDN-4 (M28):** the credential *class* is exported as the
> `agentwatch.credential_class` span attribute and a deterministic `credential-hygiene` analytics detector
> (`analytics.detectors.identity`) flags a run that acted under `ambient/shared`; the concept mapping to
> AIMS/WIMSE/NCCoE is published in [reference/identity-mapping.md](../reference/identity-mapping.md).

## Two-layer model

Aligned to WIMSE/SPIFFE and the kagenti pattern:

- **Transport layer — WHO is calling:** workload identity (SPIFFE/WIMSE URI, process attestation) when the harness
  or gateway exposes it.
- **Application layer — ON WHOSE BEHALF:** the delegation chain (user principal → agent → subagent), where the
  harness exposes it (e.g. Gemini `user.email`; Claude Compliance API projects/workspaces).

## Field set (additive `agent_identity` dimension)

| Field | Source | Redaction |
|---|---|---|
| `agent.name` / `agent.version` | harness/config | plain |
| `harness` / `model` | record | plain |
| `workload_identity` | SPIFFE/WIMSE URI if present | plain (a URI, not a secret) |
| `credential_class` | `api-key \| oauth \| svid \| ambient/shared` | plain |
| `principal` | user identity if exposed | **hashed by default** in metadata-only |
| `delegation_chain` | on-behalf-of chain if exposed | principals hashed by default |

**Hard rule:** identity fields never contain secret material (property test extends the redaction suite). Hashed by
default in `metadata-only`; plaintext only under the `full` privacy mode with operator consent.

## Attribution rendering

`impact` / `blame` / `tree` / `trace` show, for each action: agent identity, credential class, delegation
(on-behalf-of), and approval provenance (S14). Where the harness does not expose a fact, the value is an honest
`unknown` — never inferred.

## Credential-hygiene observation (IDN-4)

A deterministic observation flags `credential_class: ambient/shared` (agents running on shared credentials — NIST's
pre-Q4-2026 audit ask). It is an **observation**, not a verdict; precision/recall published via the detector harness
([detector-evaluation.md](detector-evaluation.md)).

## AAT & A2A alignment

- AAT export populates the identity fields ([aat-mapping.md](aat-mapping.md)).
- A2A **signed agent cards** (v1.0) provide cryptographic workload identity; the card-signature verification outcome
  is recorded as `verified`/`unverified` and is **never silently trusted** as authorization (PRD 45, ADR-0025).
  **Implemented (M29 A2A-2):** [`agentwatch.agent_card`](../../packages/python-sdk/src/agentwatch/agent_card.py) verifies
  the card JWS deterministically against a held key (local `AGENTWATCH_A2A_JWKS` or an explicit mapping) and returns a
  `CardProvenance` whose outcome is recorded on the `a2a/agent-card` observation; a cross-agent hand-off emits an
  `agent-delegation` observation that extends `tree`/`trace` across org boundaries (evidence, never a verdict).

## Mapping doc

A published mapping (agentwatch identity field ↔ AIMS/WIMSE ↔ NCCoE concept-paper questions) accompanies IDN-4, so
the record layer can be cited by a federal reference architecture rather than guessed at: see
[reference/identity-mapping.md](../reference/identity-mapping.md).

## Standards & vendor landscape (why this is the right field set)

The 2026 stack agentwatch aligns to:

- **IETF AIMS** (`draft-klrc-aiagent-auth-00`, Mar 2026) — composes **WIMSE + SPIFFE/SPIRE + OAuth 2.0** into an
  Agent Identity Management System. Thesis: agents are workloads; treat them with workload identity, not a new
  category. "Agents MUST be uniquely identified in order to support authentication, authorization, auditing, and
  delegation." Identifier: WIMSE URI; credentials: X.509-SVID / JWT-SVID / WIT.
- **WIMSE for agents** (`draft-ni-wimse-ai-agent-identity-01`, Oct 2025) — a credential denotes *both* agent
  identity and human-owner identity (delegation binding), with cryptographic proof of user approval.
- **NIST NCCoE** concept paper (Feb 2026) — workstreams: Identification, Access Delegation, **Logging and
  Transparency** ("link actions to the identity of the non-human entity"), and tracking prompt/data-flow
  provenance (which our content-flow forensics S22 already does).
- **OpenID Foundation** — "Identity Management for Agentic AI" (Oct 2025): OAuth 2.0/2.1, OIDC, SPIFFE/SPIRE, SCIM
  as candidates.
- **Google Cloud Agent Identity** (2026) — productized per-agent SPIFFE IDs
  (`spiffe://trust-domain/resources/...`), 24 h X.509 rotation, **certificate-bound tokens** (token-theft
  prevention); end-user access events attributable to the agent's SPIFFE ID.
- **HashiCorp Vault 1.21+** — native SPIFFE auth: issue/rotate SVIDs to agents inside the secrets layer.
- **Red Hat kagenti** (Jun 2026) — SPIFFE mTLS + **RFC 8693 token exchange** for on-behalf-of delegation + agent
  lifecycle policy binding.

Adoption pressure (why identity is a product requirement, not a nicety): Entro reports **97%** of non-human
identities carry excessive privileges; Obsidian reports **90%** of AI agents over-permissioned; CSA finds **>75%**
of orgs lack AI-identity policy and only ~1 in 5 can interrupt an agent; Gartner (via Exabeam) has **37% of CISOs**
naming AI security their #1 concern. agentwatch records and joins identity; it never enforces it.
