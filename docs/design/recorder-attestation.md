# Design — Recorder Attestation

**BLUF:** How a session proves, in the chain, that the recorder was actually on: a **session-start attestation fact**
(effective hook sources, a digest of the effective hook/permission config, managed-policy status, permission mode) plus a
`recorder-config-changed` observation when that digest changes. Answers the auditor question *"was recording active at
14:03?"* — which the chain alone cannot answer today.

**Status:** implemented (2026-10-06, v0.2.0 M29) · **Milestone:** M29 · Sources:
[PRD 50](../prd/50-deployability-and-recorder-attestation.md), [recorder-attack-matrix.md](recorder-attack-matrix.md),
[threat-model.md](threat-model.md).

> **Implementation (M29 DEP-2, #442).** `agentwatch.attestation` computes a keyed config digest over booleans/mode
> only and `attest_session` appends the `recorder-attested` fact, plus `recorder-config-changed` when the digest
> moves; `init` emits it at recorder activation. `coverage` and `evidence` carry `attestation: present|absent`.
> Digests/booleans only (property-tested). Same-user forgery remains out of scope. ADR-0029. **Integration note:**
> the daemon appends the attestation on the `session-start` hook (once per session), and `init` emits it at recorder
> activation; both call the same `attest_session` function.

## Why the chain alone is not enough

The [recorder attack matrix](recorder-attack-matrix.md) concedes: stripping hooks is "not preventable … a silent edit
leaves no chain record." A store that verifies clean can therefore be *empty* rather than *complete*. Attestation records
that recording was configured to run — and that it was not.

## Contents (metadata only)

At session start (or first observed record), append one attestation record:

| Field | Content |
|---|---|
| `hook_sources` | effective sources (`managed` / `user` / `project` / `plugin`), as booleans |
| `config_digest` | keyed digest of the effective hook/permission config — **no values** |
| `managed_policy` | whether `allowManagedHooksOnly` / `strictPluginOnlyCustomization` applied |
| `permission_mode` | starting mode (see authorization-provenance-v2) |
| `recorder_version` | agentwatch + adapter versions |
| `attestation` | `present` / `absent` |

When the digest differs from the prior session (or changes mid-session), append `recorder-config-changed` with the two
digests and the changed booleans. A gap with no attestation is classified `attestation:absent` (S2 taxonomy).

## Guarantees and non-claims

- **States:** which sources were effective; that the config digest changed; the permission mode.
- **Does not state:** that no attacker modified the store (same-user forgery is out of scope), or that every call was
  captured (that is `coverage`).
- The digest is **keyed** like content-flow fingerprints, so it cannot be confirmed from a leaked store without the key.

## Surfacing

`coverage` and `evidence` include the attestation; the compliance report cites attestations for its "recording active
during period" row; the fleet view shows attestation freshness per host.

## Testing

- Hooks stripped between two sessions → `recorder-config-changed` at the next start + classified gap (FT-DEP-2).
- Attestation carries digests/booleans only (property test: no values/secrets).
- Digest is stable for an unchanged config and changes on any effective hook/permission change.

## Decision

ADR-0029 — attestation contents and the published non-claims.
