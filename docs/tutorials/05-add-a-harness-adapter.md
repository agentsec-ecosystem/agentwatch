# Tutorial 05 — Add a Harness Adapter

**BLUF:** Record a new harness by implementing the adapter contract.

1. Declare `harness`, capability classes, and **gaps** (explicit).
2. Implement `normalize(raw) -> Record[]` to the [record format](../reference/record-format-spec.md).
3. Add conformance fixtures and gap assertions ([adapter-conformance](../reference/adapter-conformance.md)).
4. Update the [compatibility matrix](../reference/compatibility.md).

An adapter is "supported" only when its conformance suite passes in CI.
