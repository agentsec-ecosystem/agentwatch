# Advisory process (OSV readiness)

agentwatch is registered for vulnerability reporting through the OSV ecosystem
and reports advisories in OSV's schema. This documents the flow end to end; a dry
run in CI proves it.

## Reporting a vulnerability

1. Report privately per [`SECURITY.md`](../../SECURITY.md).
2. Maintainers triage and assign an identifier.
3. A fix ships; an advisory is published in **OSV format** with the affected
   versions and the fixed version.
4. The advisory is linked from the release notes.

## OSV record shape

```json
{
  "schema_version": "1.6.0",
  "id": "AGENTWATCH-YYYY-NNNN",
  "affected": [{"package": {"ecosystem": "PyPI", "name": "agentwatch"}, "ranges": [...]}],
  "details": "...",
  "references": [...]
}
```

## Dry run

A dry-run advisory is produced by the release tooling to confirm the flow (record
shape + linkage) without disclosing anything; the dry run is checked at the M24
release gate.

## Evidence

`docs/compliance/openssf-badge.md` lists the vulnerability-reporting criterion as
met; the dry-run advisory and its OSV linkage are validated by the release gate
(`agentwatch verify-release`).
