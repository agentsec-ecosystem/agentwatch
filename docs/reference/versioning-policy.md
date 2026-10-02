# Reference — Project Versioning & Release Policy

**BLUF:** SemVer for the project; the record/security-event schemas have their own version fields and a
documented deprecation cycle (see [record-format spec](record-format-spec.md)).

## SemVer

- **Major** — breaking changes to the SDK or read API (requires a migration guide + a deprecation cycle).
- **Minor** — additive features (new harness adapter, new detector, new view).
- **Patch** — fixes, security patches.

## Support windows

- The latest minor is supported (fixes backported for ~3 months).
- Major versions get a 6-month deprecation notice before EOL.

## Backports

Security fixes are backported to the prior minor for 3 months.

## Release artifacts (every release)

- Release notes (`docs/release/vX/`) · compatibility table · security audit.
- SBOM + signed artifacts (Sigstore/SLSA) · OpenSSF Scorecard grade.

## Schema vs project

Schema versions (`schema_version`, `event_version`) are independent of the project version; a project
minor may bump a schema minor (additive). See [record-format spec §Versioning](record-format-spec.md).
