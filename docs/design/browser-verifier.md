# Design — Browser Verifier

**BLUF:** How a third party verifies an evidence bundle with **nothing installed**: a single static, self-contained page
that works from `file://`, makes **zero network requests**, and re-verifies chain, completeness, leak-scan and (where
present) recorder attestation — showing the same verdicts as the CLI verifier.

**Status:** proposed (2026-10-05, v0.2.0-expanded) · **Milestone:** M28 · Sources:
[PRD 57](../prd/57-investigation-depth-and-verification.md), [evidence-verifier.md](../reference/evidence-verifier.md),
[recorder-attestation.md](recorder-attestation.md).

## Why

CUJ-8's promise is "verify offline, on another machine, without installing agentwatch." The standalone verifier is a
Python zipapp, so an auditor still needs a runtime and must trust a downloaded executable. A browser page lowers the bar
to "open the file".

## Behavior

- Opens from `file://`; **no network requests** (asserted by test); the bundle never leaves the browser.
- Verifies: chain integrity (intact), completeness (gaps classified), leak scan (leak-free), and attestation
  (recording attested / absent) when the bundle carries it.
- Output uses the **same wording** as the CLI verifier; a tampered bundle names the first broken link.

## Trust model (ADR-0044)

- The page is a **signed, checksummed release artifact**, listed in release evidence; users can verify its hash.
- Verification logic is a port of the same spec as the CLI verifier; a **differential test** asserts identical verdicts
  across the whole evidence fixture set.
- No server, no upload, no telemetry; static assets only.

## Static demo bundle (DEMO-1)

A committed, synthetic `examples/demo-bundle/bundle.json` lets an evaluator see replay/impact/oversight/provenance
**before** installing anything: it opens from `file://`, makes zero network requests, has no server/telemetry/account,
and is synthetic (`producer.kind: demo`) and secret-scanned. It is the same static, offline posture as the verifier
page, carrying demo data instead of an evidence bundle. The page rendering is owned by **30.VFY-1** and is deferred
while the page is not in this branch; the artifact is complete and the page consumes it unchanged.

## Testing

- Zero network requests (FT-VFY-1); bundle stays local.
- Verdicts equal the CLI verifier on all fixtures.
- Tampered bundle → clear failure identifying the first broken link.
- Release artifact hash verifies.
- The static demo bundle is synthetic, secret-scanned, and carries no network reference
  (`packages/python-sdk/tests/test_demo_bundle.py`).

## Decision

ADR-0044 — browser verifier trust model and release signing.
