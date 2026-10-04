# Schema stewardship

The `schema/` directory is the published contract between agentwatch and any
emitter or consumer. Defaults are won on governance, not JSON, so the policy is
stated and enforced.

## Versioning (semver)

- **Additive minor** — a new optional field or a new enum value increments the
  minor version and keeps old readers working.
- **Breaking major** — removing/renaming a field or changing a type increments
  the major version and requires a deprecation window (at least one minor release
  announcing the removal).
- A schema version is `const` in the JSON (`schema_version` / `event_version`); an
  unknown version is **rejected with the supported range named**, never coerced.

## Proposal process for a new event type

1. Open an issue describing the event, its `evidence` shape, and the OCSF target
   (or an explicit `unmapped`).
2. Add it to `records.SecurityEventType` and `security-event.schema.json`
   **together**, plus the OCSF mapping in `docs/design/ocsf-mapping.md`.
3. Add a `schema/CHANGELOG.md` entry naming the version and the event type.
4. The policy check (`agentwatch.schema_policy`, run in CI) fails if the enum,
   the changelog, or the `$id` URLs drift.

The first test of this process was `tool-surface-changed` (M20 S4).

## Registry

Schemas are published with resolvable `$id` URLs and are intended for listing in
SchemaStore. Changes are proposed upstream to OTel (DD-05) where they overlap.

## Conformance

`schema/vectors/` holds store/chain conformance vectors. The third-party-facing
emitter/consumer suite is exercised by `tests/test_schema_conformance.py`.
