# ADR-0044 — Browser verifier trust model and release signing

- **Status:** accepted (2026-10-07, v0.2.0 M30)
- **Context:** PRD 57 §VFY-1, [design/browser-verifier.md](../design/browser-verifier.md), issue #475.
- **Supersedes:** none.

## Context

An auditor, lawyer, or regulator verifying an agentwatch evidence bundle should need **nothing installed**.
The shipped standalone verifier is a Python zipapp (S12/DEP-2), so a third party still needs a Python runtime
and must trust a downloaded executable. A browser page lowers the bar to "open the file". The open questions
are trust: how does a user know the page does what it says, and how is the artifact distributed?

## Decision

1. **The page is a self-contained static artifact.** One HTML file with its verifier logic inlined; it opens
   from `file://` and makes **zero network requests**. The bundle is read with the File API and never leaves
   the browser. There is no server, no upload, and no telemetry.
2. **Logic is a port of the published spec, not a new source of truth.** The page re-implements the exact
   rules the CLI verifier encodes (member sha256, the `sha256(prev_hash + canonical_json(payload))` chain
   link, `coverage.json.complete`, `privacy.json.leak_free`, attestation). A **differential test** asserts
   identical verdicts to `agentwatch.evidence.verify_bundle` across the evidence fixture set; the test drives
   the inlined core under a JS engine, so drift is a test failure.
3. **Reports the first broken link.** A tampered bundle fails with the member name (for a member tamper) or
   the chain `seq` of the first row whose hash does not match — never a bare "invalid".
4. **Signed, checksummed release artifact.** The page is checksummed in `SHA256SUMS` and listed in release
   evidence (`docs/release/verifier/README.md`). The **release pipeline signs** the checksum with the release
   ed25519 key (`scripts/build_browser_verifier.py --sign`); `verify-release` consumes that signature like any
   other release artifact. A throwaway key is never committed.

## Consequences

- Users can verify the page's sha256 against the published checksum and verify the release like any other
  artifact; a fully offline auditor needs no Python.
- The port is intentionally narrow: it re-verifies evidence bundles of the current format; it is not a general
  zip or chain tool. An unknown `bundle_format` is rejected with the version named, matching the CLI.
- In-repo the artifact is checksummed but not signed; the signature is produced at release time. This is
  declared in [known-limitations](../reference/known-limitations.md).
