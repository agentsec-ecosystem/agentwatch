# Design — Threat → Control → Test Traceability

**BLUF:** Each threat in the [threat model](threat-model.md) maps to a control and a test that proves it.
No unverified controls.

| Threat | Control | Test |
|---|---|---|
| Spoofing (impersonate daemon) | Local socket perms; identity check | socket-perm test |
| Tampering (records edited) | Hash chain (DD-07) | `verify-store` + F4 fault test |
| Repudiation ("agent didn't do it") | Ordered, correlated records | replay-fidelity test |
| Info disclosure (secrets) | Redaction before store (DD-06); export gating (DD-09) | redaction attack pack; export-locked test |
| DoS (silent stop) | Fail-closed + health surfaced (NFR-8/12) | F1/F3 fault tests; `/healthz` |
| EoP (poisoned hook config) | Config validation; least privilege; signed releases | bad-config test (F7); supply-chain checklist |
| On-box tamper (kill/strip/move/skew) | Chain + recorder-state records + coverage reconciliation | anti-forensics suite; [recorder attack matrix](recorder-attack-matrix.md) |
| Foreign-data weaponization (R5) | Untrusted-data rule ([ADR-0024](../adr/0024-foreign-data-threat-posture.md)): no shell/eval on any ingest/reader path | `test:packages/python-sdk/tests/test_ingest.py::test_unmappable_input_is_quarantined` (plus `test_fuzz_parsers.py`, the static shell-reference guard, and the mutation gate) |

## v0.2.0 surfaces (R5)

Every new trust surface the v0.2.0 program introduces, traced to a regression test:

| Surface | Control | Test |
|---|---|---|
| Foreign-data weaponization | Untrusted-data rule; redaction + B4 quarantine; no shell/eval | `test:packages/python-sdk/tests/test_ingest.py::test_unmappable_input_is_quarantined` |
| Foreign AAT chain tamper | Verify a foreign bundle's chain before any record is stored | `test:packages/python-sdk/tests/test_aat_ingest.py::test_ingest_aat_rejects_tampered_chain` |
| Streaming side-channel | Derived views; store authoritative; back-fill; gaps classified | `test:packages/python-sdk/tests/test_live_tail.py::test_overflow_is_degraded_and_backfilled` |
| Proxy-surface growth | Fuzz, bounded buffers, quarantine; no silent trust | `test:packages/python-sdk/tests/test_fuzz_parsers.py::test_aat_bundle_verification_never_raises` |
| Compliance-API pull | Explicit opt-in; pulls recorded as `store-access` | `test:packages/python-sdk/tests/test_store_access.py::test_record_store_access_appends_scope_and_kind` |
| Identity-field abuse | Principals/delegation hashed by default in metadata-only | `test:packages/python-sdk/tests/test_identity.py::test_metadata_only_hashes_principal_and_chain` |
| OTLP/gRPC streaming ingest | Bounded memory; no whole-stream load | `test:packages/python-sdk/tests/test_otlp_protobuf_ingest.py::test_large_grpc_stream_has_bounded_memory` |
