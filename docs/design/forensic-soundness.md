# Forensic soundness

**BLUF:** What the hash chain proves, what it does **not**, and how to handle a
bundle. Stated in the vocabulary of NIST SP 800-86 and ISO/IEC 27037.

The canonical statement ships inside every evidence bundle as
`FORENSIC_SOUNDNESS.md` (source: `agentwatch.forensic.statement()`); this page is
its public home.

## The chain proves

- **Append-order integrity** and **no undetected in-place edit** of any covered
  line (`agentwatch verify-store`).

## The chain does **not** prove

- **Immutability against an operator with disk access.** The whole chain can be
  rewritten before any checkpoint is anchored, and the rewrite will verify.
- **Absence of a record is not proof of absence of an action.** Missed hooks,
  a down daemon, or a trust-gated headless run leave no record; coverage windows
  and `agentwatch coverage` narrow and name the gap.
- **Origin.** Hash integrity is not attributability; optional signed checkpoints
  add "produced by this installation," never "by this human."
- **Content truth.** It records what the harness reported.

## Narrowing the gaps

- **Checkpoints** (E1) bound how far a rewrite reaches undetected once a
  checkpoint digest is anchored off-machine — **W7 notarization** (RFC 3161) or
  the zero-infrastructure options (commit the digest to git, email it to
  yourself).
- **Signed checkpoints** (W9) add attributability to this installation.
  Signing is a **supported posture**, not an experiment: `agentwatch checkpoint
  export --sign` signs a digest with the installation key, and
  `agentwatch checkpoint rotate` replaces that key and records the change as a
  metadata-only `key-rotation` chain event (previous → new key id). A signature
  is tied to its **epoch**; a verifier who does not hold the epoch key reports
  *"signed by key id X, key unavailable"* rather than silently passing. The
  posture is surfaced by `agentwatch verify-store`, `agentwatch evidence`,
  AAT export, `agentwatch doctor`, and `/healthz`.
- **Coverage windows** (S5) reconcile the store against an independent
  transcript.

## Handling a bundle

1. `agentwatch verify-store` — verify the chain.
2. `agentwatch verify-privacy` — verify no leak.
3. Read the coverage section; a gap is stated on the front page.
4. Verify checkpoint signatures and timestamps with the published key.
5. Preserve the bundle unchanged.
