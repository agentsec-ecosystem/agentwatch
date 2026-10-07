# ADR-0029 — Recorder attestation contents and non-claims

- **Status:** accepted (2026-10-06, M29 DEP-2)
- **Decision:** each session records one chain **attestation fact** carrying the
  effective hook sources (booleans), a **keyed digest** of the effective
  hook/permission config, managed-policy status, the permission mode, and the
  recorder version; a digest change raises a `recorder-config-changed`
  observation. Only digests and booleans are stored — never config values or
  secrets. A session with no attestation is `attestation:absent`, not "complete".
- **Consequences:** an auditor can establish "recording was configured to run at
  T" from the chain; the digest is keyed like content-flow fingerprints so it
  cannot be confirmed from a leaked store without the key.
- **Non-claims (published):** the attestation does **not** state that no attacker
  modified the store (same-user forgery is not preventable and is out of scope),
  nor that every call was captured (that is `coverage`). Cross-checking with
  native telemetry (PRD 51) is the detection path, not a guarantee.
- **Evidence:** `agentwatch.attestation`; `recorder_state` markers;
  `tests/test_recorder_attestation.py`.