# Release artifact — Offline Browser Evidence Verifier

**BLUF:** `agentwatch-verify.html` is the M30 VFY-1 release artifact: a single, self-contained page that
re-verifies an evidence bundle **from `file://` with zero network requests**. The bundle never leaves the
browser. This directory is the release evidence for the artifact.

## Artifact

| File | Purpose |
|---|---|
| `agentwatch-verify.html` | The offline verifier page (self-contained; no external assets). |
| `SHA256SUMS` | The page's sha256, `sha256sum`-format, for manual verification. |
| `SHA256SUMS.sig` | *(release pipeline)* detached ed25519 signature over `SHA256SUMS`, written by `scripts/build_browser_verifier.py --sign`. |

**sha256 (agentwatch-verify.html):**

```
b578c506eb6e003f9ae4a60515621e1ee953edd444f0e2cd19ea2369d09b8576
```

## Verify the artifact

```sh
cd docs/release/verifier
shasum -a 256 -c SHA256SUMS
```

## Use the artifact

Open `agentwatch-verify.html` in a browser (double-click or `file://`). Choose a `*.evidence.zip` produced by
`agentwatch evidence <session>`. The page reports `intact`, `complete`, and `leak-free` with the same wording
as `agentwatch evidence verify`, plus `recording attested: present|absent` when the bundle carries attestation.
A tampered bundle reports the first broken chain link.

## Trust model

See [ADR-0044](../../adr/0044-browser-verifier-trust-model.md) and
[design/browser-verifier.md](../../design/browser-verifier.md). The page is a port of the same spec as the CLI
verifier; a differential test asserts identical verdicts across the fixture set. No server, no upload, no
telemetry: static assets only.
