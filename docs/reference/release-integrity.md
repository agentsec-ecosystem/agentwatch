# Reference — Release Integrity (v0.1.0)

**BLUF:** Releases are built, hashed, SBOM'd, **signed**, and carry **GitHub-native build provenance**
(SLSA Build L2); a consumer can
check all of it with `agentwatch verify-release`. GitHub Actions are pinned by commit SHA and the release
build toolchain is hash-pinned, so a moved tag or an unhashed dependency cannot silently change what ships
(PRD 38 §Q13, PRD 18 §D/§F, issue #230).

Status: **implemented** · Workflow: [`.github/workflows/release.yml`](../../.github/workflows/release.yml)

## Pipeline

Triggered by a `v*` tag (or manual dispatch), the `build` job:

1. builds the sdist + wheel;
2. writes a **CycloneDX** SBOM (`scripts/release/generate_sbom.py`);
3. writes `SHA256SUMS` (`scripts/release/checksums.py`);
4. signs every artifact, the SBOM, and the checksums with **keyless Sigstore cosign**
   (`cosign sign-blob --bundle`), producing `<file>.sigstore.json`;
5. runs **`agentwatch verify-release dist`** — the release refuses to publish an artifact it cannot verify;
6. attests GitHub build provenance and publishes the release.

The `provenance` job runs the reusable
[SLSA L3 generator](https://github.com/slsa-framework/slsa-github-generator) over the artifact hashes.

## Hardening

| Risk | Control |
|---|---|
| A moved action tag changes CI | every `uses:` is pinned to a 40-hex commit SHA (enforced by `tests/test_release_pipeline.py`) |
| An unhashed build dependency changes the artifact | `scripts/release/requirements-build.txt` pins the build toolchain with `--hash=sha256:` and is installed with `pip install --require-hashes`; the build runs `--no-isolation` |
| A tampered download is trusted | `agentwatch verify-release` re-hashes every artifact against `SHA256SUMS` and fails closed |
| A release is unsigned | `verify-release` requires a cosign bundle or SLSA provenance unless `--allow-unsigned` is passed (local/dry-run only) |

## Verifying what you installed

```sh
pip download agentwatch==0.1.0 --no-deps -d dist
# fetch SHA256SUMS, sbom.cdx.json, and *.sigstore.json from the GitHub release
agentwatch verify-release dist \
  --cosign-identity-regexp "https://github.com/agentsec-ecosystem/agentwatch/.*" \
  --cosign-issuer "https://token.actions.githubusercontent.com"
```

The command exits `0` and prints `release verified` when the checksums match, the SBOM is a valid CycloneDX
document, and the signatures verify; otherwise it exits non-zero with a machine-readable error
([error contract](errors.md)) naming the failing check.

## Pinned by

`.github/workflows/release.yml`, `scripts/release/generate_sbom.py`, `scripts/release/checksums.py`,
`scripts/release/requirements-build.txt`, `packages/python-sdk/tests/test_release_pipeline.py`
(`verify-release` accepts a good release and rejects a tampered one; every workflow action is SHA-pinned;
the build lock is hash-pinned).
