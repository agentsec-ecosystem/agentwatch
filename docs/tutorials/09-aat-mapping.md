# Tutorial 09 — AAT mapping

agentwatch is the first reference implementation of the IETF **Agent Audit Trail**
(AAT) — it can emit a standards-shaped bundle of a session and verify a foreign
one before storage.

## 1. Emit AAT for a session

```sh
agentwatch export-session <session-id> --format aat > session.aat.json
```

The bundle carries the chain envelope, a field-mapping coverage block, and an
explicit `unmapped` block (fields AAT cannot express, e.g. `response_hash`/
`response_size`) — lossless or explicit, never dropped.

## 2. Verify a foreign AAT bundle

```sh
agentwatch ingest session.aat.json --format aat
```

A foreign bundle's chain is **verified before storage**; untrusted or
non-normalizable records are quarantined with a reason (never dropped silently).

## 3. What you should see

- `record_phase` (`pre_execution`/`post_execution`) on both sides of a call.
- Identity dimensions populated (`principal`, `workload_identity`, `delegation_chain`).
- The pinned draft revision in `--version`; a revision drift check fails CI.
- The `unmapped` block naming anything the mapping could not carry.

See [aat-mapping.md](../design/aat-mapping.md) and the conformance vectors in
`schema/vectors/aat/`.
