# Release Evidence — v0.2.0

M32 item **32.7** (issue #399): SBOM + checksums + Sigstore signing + build provenance. The artifacts are built,
SBOM'd, checksummed, and verified locally (`make release-dry-run`); keyless Sigstore signing and SLSA/GitHub build
provenance are CI-managed on a `v*` tag (they require an OIDC identity).

## Local dry-run (unsigned) — `make release-dry-run`

```
==> build sdist + wheel
==> generate SBOM (CycloneDX)
==> checksums
==> verify-release (unsigned)
{ "ok": true, "checks": [
  { "name": "artifacts", "ok": true, "detail": "2 artifact(s)" },
  { "name": "checksums", "ok": true, "detail": "2 artifact(s) verified" },
  { "name": "sbom",      "ok": true, "detail": "CycloneDX 1.5 with 3 component(s)" },
  { "name": "signature", "ok": true, "detail": "skipped (--allow-unsigned)" } ] }
release-dry-run: OK
```

Artifacts produced: `agentsec_agentwatch-0.2.0-py3-none-any.whl`, `agentsec_agentwatch-0.2.0.tar.gz`,
`sbom.cdx.json` (CycloneDX **1.5**, component `agentsec-agentwatch` **0.2.0**), `SHA256SUMS`.

## CI signing & provenance — `.github/workflows/release.yml` (on a `v*` tag)

| Step | Tool | Result |
|---|---|---|
| Build sdist + wheel | `python -m build --no-isolation` | dist artifacts |
| SBOM | `scripts/release/generate_sbom.py` (CycloneDX) | `sbom.cdx.json` |
| Checksums | `scripts/release/checksums.py` | `SHA256SUMS` |
| **Keyless Sigstore signing** | `cosign sign-blob --yes --bundle <file>.sigstore.json` (OIDC) | per-artifact `.sigstore.json` |
| Verify before publish | `agentwatch verify-release dist --cosign-identity-regexp … --cosign-issuer https://token.actions.githubusercontent.com` | must pass to publish |
| **Build provenance** | `actions/attest-build-provenance` | GitHub attestation for whl + tar.gz |
| Publish | `softprops/action-gh-release` | GitHub release with all `dist/*` |
| Publish (PyPI) | `pypa/gh-action-pypi-publish` (trusted publishing, OIDC) | gated by `PYPI_TRUSTED_PUBLISHING=true` |

All actions are pinned by commit SHA. The workflow **refuses to publish** an artifact `verify-release` cannot confirm.

## Verification

```bash
make release-dry-run                       # local: build + SBOM + checksums + verify-release (unsigned)
# on a v* tag, CI adds cosign signatures + GitHub provenance and re-verifies before publishing
```
