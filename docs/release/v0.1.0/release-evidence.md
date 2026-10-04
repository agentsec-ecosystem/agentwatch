# Release Evidence — v0.1.0 (M24 24.4)

**BLUF:** the v0.1.0 release bundle **builds, checksums, and verifies** locally. A
CycloneDX 1.5 SBOM with resolved dependency versions is produced, and
`agentwatch verify-release` accepts the bundle. Keyless Sigstore signing and SLSA L3
provenance require a CI OIDC identity and run in `.github/workflows/release.yml` on the
`v0.1.0` tag (M24 24.8), not on a workstation.

Status: **dry-run validated** (unsigned) · Reproduce: `make release-dry-run`
(Acceptance: verifiable.)

## What the dry-run does

`scripts/release/dry_run.sh` (wrapped by `make release-dry-run`) mirrors the build half
of the release workflow, without an identity token:

1. `python -m build --no-isolation packages/python-sdk` → sdist + wheel
2. `scripts/release/generate_sbom.py` → `sbom.cdx.json` (CycloneDX 1.5)
3. `scripts/release/checksums.py` → `SHA256SUMS` (SHA-256)
4. `agentwatch verify-release <dist> --allow-unsigned --json` → fail-closed report

## Dry-run result

```json
{
  "ok": true,
  "checks": [
    { "name": "artifacts",  "ok": true, "detail": "2 artifact(s)" },
    { "name": "checksums",  "ok": true, "detail": "2 artifact(s) verified" },
    { "name": "sbom",       "ok": true, "detail": "CycloneDX 1.5 with 3 component(s)" },
    { "name": "signature",  "ok": true, "detail": "skipped (--allow-unsigned)" }
  ]
}
```

Artifacts produced: `agentwatch-0.1.0-py3-none-any.whl`, `agentwatch-0.1.0.tar.gz`,
`sbom.cdx.json`, `SHA256SUMS`. `verify-release` **fails closed** on a tampered artifact,
a missing SBOM, or a bundle whose checksum line is absent — covered by
[`tests/test_release_pipeline.py`](../../../packages/python-sdk/tests/test_release_pipeline.py)
and [`tests/test_release_tooling.py`](../../../tests/test_release_tooling.py).

### SBOM (components and resolved versions)

| Component | Version |
|---|---|
| `opentelemetry-api` | resolved from the environment |
| `opentelemetry-sdk` | resolved from the environment |
| `tomli` | resolved from the environment (3.10 backport) |
| `agentwatch` (root) | `0.1.0` |

Versions come from `importlib.metadata` at generation time; a dependency that is not
installed falls back to an exact `==` pin, then `unspecified`.

## Tag-time actions (M24 24.8)

`.github/workflows/release.yml`, triggered by a `v*` tag and **refusing to publish an
artifact it cannot verify**:

| Step | Mechanism |
|---|---|
| Build sdist + wheel | hash-pinned build tools (`requirements-build.txt`) |
| SBOM + checksums | `scripts/release/` |
| Keyless signatures | `cosign sign-blob` (Sigstore, OIDC) |
| Verify before publish | `agentwatch verify-release dist` with identity/issuer pins |
| Provenance | `actions/attest-build-provenance` (GitHub) + SLSA L3 generator |
| Publish | `softprops/action-gh-release` |

## Residual (stated, not hidden)

- No keyless signature is produced by the local dry-run; that is CI-only by design
  (it needs an OIDC identity). The local report is therefore `--allow-unsigned`.
- SBOM dependency versions reflect the generating environment; the release tag pins
  them to the CI build environment.
