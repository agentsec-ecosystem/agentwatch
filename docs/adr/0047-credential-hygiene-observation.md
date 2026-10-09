# ADR-0047 — Credential-hygiene observation

- **Status:** accepted (2026-10-06, v0.2.0 M28 IDN-4)
- **Context:** Over-privileged non-human identities (agents on shared/ambient credentials) are a stated NIST
  pre-Q4-2026 audit ask. agentwatch records the credential *class* (IDN-1, `ambient/shared`) but did not flag
  it as an observation.
- **Decision:** Export the credential class as the `agentwatch.credential_class` span attribute (class only,
  never the value) and add the deterministic `credential-hygiene` detector
  (`analytics.detectors.identity.CredentialHygieneDetector`) that flags a run that acted under
  `ambient/shared`. It is an **observation, not a verdict**: it names the class the trace stated, is silent
  when the credential is `unknown`, never blocks a run, and is toggleable via `settings.detector_disabled`.
  The concept mapping to AIMS/WIMSE/NCCoE is published in
  [reference/identity-mapping.md](../reference/identity-mapping.md).
- **Consequences:** The class becomes queryable across the OTLP boundary; precision/recall is published via the
  DET harness. agentwatch does **not** issue/rotate/revoke credentials and does not verify workload attestation.
- **Alternatives rejected:** a blocking control (agentwatch is observability-only, PRD 14/18); inferring a
  credential when the harness does not expose one (violates the honest-unknown rule).
