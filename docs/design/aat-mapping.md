# Design — IETF Agent Audit Trail Mapping

**BLUF:** How agentwatch records map to the IETF Agent Audit Trail (AAT) draft, how the draft is pinned and
drift-checked, and the `lossless-or-explicit` rule that keeps export/ingest honest. **How**, not whether — the
product requirement is [PRD 41](../prd/41-standards-and-interop-ii.md) (AAT-1..5).

**Status:** 🚧 partially implemented (2026-10-05, v0.2.0) · **Milestone:** M25–M26 · Sources:
[PRD 41](../prd/41-standards-and-interop-ii.md), PRD 23, PRD 31, PRD 39 (W4/W5).

> **Implementation (M25 AAT-1/AAT-2; M26 AAT-3):** `agentwatch.aat` holds the mapping
> (`AAT_MAPPING`, `aat_record`), the pinned `AAT_DRAFT` revision, the chain verifier
> (`verify_aat`, `aat_entry_chain_error`), and the bundle writer (`export_aat`,
> `write_aat`). `export-session --format aat` emits the bundle with the chain envelope,
> an `unmapped` block (response_hash/response_size), and a coverage/gap block.
> `ingest --format aat` (`agentwatch.ingest.transcode_aat`) verifies every entry's chain
> hash and inter-entry linkage before storage, runs foreign content through the secrets
> pipeline, and quarantines any untrusted or non-normalizable record with a reason (B4).
> **AAT-4** adds `schema/vectors/aat/` (valid/tampered/unmapped/unsupported-revision)
> with `expected-verdicts.json`, a dependency-free second verifier
> (`schema/vectors/verify_aat.py`), and the dual-verifier CI check
> (`packages/python-sdk/tests/test_aat_vectors.py`). **AAT-5** pins the revision
> (`AAT_DRAFT`) and its mapped fields (`AAT_DRAFT_FIELDS`), carries the pin in
> `agentwatch --version`, and ships `scripts/aat_drift_check.py` + the
> `AAT draft drift` workflow against `schema/aat/upstream-revision.json`
> (simulated-bump test: `tests/test_aat_drift.py`). AAT-1..5 are implemented.

## Pin

- Pin `draft-sharif-agent-audit-trail-<nn>` by revision (at time of writing `-06`, Sept 2026).
- The pin is carried in `--version`, in exported AAT `metadata`, and in a CI drift check (same mechanism as the
  OTel semconv pin, W4): a new draft revision fails the pin check and opens an issue.
- We never claim "AAT-conformant" generically; we claim "conformant to `<revision>`."

## Record ↔ AAT field mapping

| AAT concept | agentwatch source | Notes |
|---|---|---|
| agent identity | `agent_identity` (IDN-1) | name/version/harness/model/workload-id ref/credential class; missing → `unmapped` |
| action_type | step type (`tool_call`, `tool_response`, `decision`, lifecycle) | taxonomy aligned to the draft |
| outcome | record `outcome` (`ok`/`error`/`denied`) | |
| `record_phase` | new provenance field: `pre_execution` \| `post_execution` \| `unknown` | a `denied` decision with proven pre-execution phase is `pre_execution`; otherwise `unknown` — **never inferred** (S14 discipline) |
| `response_hash` / `response_size` | redaction-stage hash of the pre-redaction response + byte size | reuses the content-fingerprint mechanism (S22/S32) |
| trust level | derived from `producer` + chain state | not a verdict |
| chain linkage | store envelope `seq`/`prev_hash`/`hash` | 1:1 with the AAT chain |
| timestamps | UTC record timestamps | explicit offset on render (time correctness) |

Unmappable AAT fields are emitted in an `unmapped` array naming each field and why; we never invent values.

## Export (`export-session --format aat`)

- Emits the session's records in AAT shape plus the chain envelope, so an AAT consumer can verify linkage.
- Content obeys the active privacy mode; a metadata-only store exports metadata-only AAT (and says so).
- A `coverage`/gap block is attached (AAT's retention/§9 context) — a bundle that hides a gap is not honest.

## Ingest (`ingest --format aat`)

- Validate strictly (F8), redact foreign content through the secrets pipeline, quarantine non-normalizable records
  with a reason (B4).
- Foreign chain linkage is verified before storage; a foreign AAT bundle is not trusted just because it parses.

## Conformance vectors

`schema/vectors/aat/` holds valid, tampered, unmapped, and unsupported-revision fixtures with a machine-readable
`expected-verdicts.json` (the Q6 store-vector pattern). Two independent verifiers — our code
(`agentwatch.aat.verify_aat_report`) and a dependency-free script (`schema/vectors/verify_aat.py`) — must agree;
divergence is a contract bug. Both are checked against the table in CI
(`packages/python-sdk/tests/test_aat_vectors.py`); regenerate with `python scripts/generate_aat_vectors.py`.

## Wording

"AAT export/ingest" — never "certified" or "compliant." Compliance language stays in [PRD 44](../prd/44-identity-enterprise-and-compliance.md)
non-conformity terms.

## Built-in regulatory mapping (carried through from the draft)

The AAT draft maps its record to several regimes; our export therefore satisfies more than EU AI Act alone. When we
emit AAT, the mapping is inherited and documented:

| Regime | AAT/aligned provision |
|---|---|
| EU AI Act (Reg. 2024/1689) | Art. 12 (record-keeping); staging by Reg. 2026/1744 |
| SOC 2 | Trust Services Criteria (audit-trail integrity) |
| ISO/IEC 42001 | AI management system controls |
| ISO/IEC 24970 (draft) | logging/process outcomes |
| prEN 18229-1 (draft) | logging standard |
| PCI DSS v4.0.1 | logging requirements (Requirement 10.3/10.5/10.7 alignment) |

This is why AAT is the adoption trigger: EU AI Act Art. 12(2) requires logs to "conform to recognized standards,"
and AAT is the emerging one that already carries the cross-regime mapping. We cite the exact draft revision and
never claim certification.

## Draft-revision pinning detail

The draft moves on a fast cadence (`-01` Aug 2026 → `-06` Sept 2026 at time of writing; expiry ~Apr 2027). We pin
the revision in `--version`, exported metadata, and the CI drift check; a new revision opens an issue rather than
silently changing output.

- **Single source of truth:** `AAT_DRAFT` (and the mapped field set `AAT_DRAFT_FIELDS`) in
  [`agentwatch.aat`](../../packages/python-sdk/src/agentwatch/aat.py). `aat_version_line()` carries
  `IETF AAT <revision>` in `agentwatch --version`; every bundle carries `aat_version`.
- **Drift check:** [`scripts/aat_drift_check.py`](../../scripts/aat_drift_check.py) compares the pin against
  [`schema/aat/upstream-revision.json`](../../schema/aat/upstream-revision.json). A revision bump, or a mapped
  field the upstream draft drops, fails the check; a new upstream field is informational. A unit test simulates a
  bump (`packages/python-sdk/tests/test_aat_drift.py`), and the `AAT draft drift` workflow opens an issue on
  divergence.
- **Re-pin policy:** when the draft moves, (1) update `AAT_DRAFT` / `AAT_DRAFT_FIELDS`, (2) refresh
  `schema/aat/upstream-revision.json`, (3) regenerate the conformance vectors
  (`python scripts/generate_aat_vectors.py`), and (4) update this mapping and `CHANGELOG.md`. Never claim
  conformance to a revision we have not re-pinned.
