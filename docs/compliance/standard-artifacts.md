# Open artifact standards

agentwatch adopts the open standards that fit its outputs instead of inventing
shapes, strengthening the "no proprietary formats" promise. Each output pins its
standard version and is tested against it; the agentwatch schema stays the source
of truth.

| Output | Standard | Pinned version | Where |
|---|---|---|---|
| Security events | OCSF | `1.5.0` (`ocsf.OCSF_VERSION`) | `export-session --format ocsf` |
| Event envelope | CloudEvents | `1.0` (`ocsf.CLOUDEVENTS_VERSION`) | `export-session --format cloudevents` |
| Bill of materials | CycloneDX | `1.5` (`bom.CYCLONEDX_SPEC_VERSION`) | `agentwatch bom` |

## Lossless-or-explicit

A field a standard cannot express is **surfaced, never dropped**: OCSF carries
agentwatch-native fields under `unmapped`, an event type with no mapping is
exported with an explicit `unmapped_type` marker, and a version bump is pinned and
tested. CycloneDX output is validated by `bom.validate_cyclonedx`.

See [ocsf-mapping.md](../design/ocsf-mapping.md) for the OCSF/CloudEvents mapping
and the conformance tests in `tests/test_artifact_standards.py`.

## Evidence

Each output is validated against its pinned version by `tests/test_artifact_standards.py`;
unmapped fields are asserted present (`agentwatch export-session <id> --format ocsf`).
