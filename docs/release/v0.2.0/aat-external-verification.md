# AAT External Verification — v0.2.0 (32.18)

**BLUF:** The flagship AAT claim — "an exported Agent Audit Trail chain can be verified by a consumer that is
**not ours**" — is verified by a **second, independent implementation** that imports nothing from `agentwatch`.

## The independent consumer

[`schema/vectors/verify_aat.py`](../../../schema/vectors/verify_aat.py) — *"Standalone, dependency-free AAT
bundle verifier (M26 AAT-4, #314). A second, independent implementation of the published IETF Agent Audit Trail
chain rules. It imports nothing from `agentwatch`: it reads the JSON bundle, recomputes each entry's sha256 chain
hash and its inter-entry linkage, and reports the same verdict as `agentwatch.aat.verify_aat_report`."*

It consumes the format defined by the IETF AAT draft (`draft-sharif-agent-audit-trail-06`) — it does not call into
agentwatch's code, so a divergence in agentwatch's own verifier cannot mask a broken bundle.

## Verification

```sh
python3 schema/vectors/verify_aat.py --table           # runs the published verdict vectors
python3 schema/vectors/verify_aat.py <bundle.json>     # verifies one exported bundle
```

Result (published vectors, `schema/vectors/aat/`):

| Vector | Expected | Independent verifier |
|---|---|---|
| `valid.json` | ok | ✅ ok |
| `tampered.json` | fail (broken link) | ✅ fail |
| `unmapped.json` | ok (unmapped tolerated) | ✅ ok |
| `unsupported-revision.json` | fail (unsupported revision) | ✅ fail |

`standalone verifier matches all 4 verdicts` (exit 0).

Proving tests: `packages/python-sdk/tests/test_aat_vectors.py` + `test_aat.py` — **24 passed**. Field case
**FT-AAT-1** (green with this independent verifier) plus FT-AAT-2 (foreign ingest quarantines a bad record with a
real reason) and FT-AAT-3 (the pinned draft revision is cited and drift is flagged).

## Honest scope

This is an independent **implementation** (out-of-tree, no `agentwatch` imports) — the strongest independent
consumer available in-repo. A **different organization's** consumer validating a released bundle is a
post-release ecosystem action; the published spec + vectors are what make that possible, and they ship here.
