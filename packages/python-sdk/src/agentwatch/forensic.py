"""Forensic-soundness statement (M22 W6, PRD 39).

"Forensic evidence" is exactly the claim an opposing expert attacks, so we state
its limits precisely, in the established vocabulary (NIST SP 800-86, ISO/IEC
27037). This text ships inside every evidence bundle so the recipient reads the
guarantees — and the non-guarantees — with the evidence.
"""

from __future__ import annotations

FORENSIC_SOUNDNESS = """# agentwatch forensic-soundness statement

agentwatch is a **mechanism that helps you handle evidence**, not a certification
and not a legal opinion. It is written in the vocabulary of NIST SP 800-86 and
ISO/IEC 27037.

## What the hash chain proves

- **Append-order integrity.** Each stored line commits to the previous line's
  hash, so an in-place edit, deletion, or reordering of any covered line is
  detected by `agentwatch verify-store`.
- **No undetected in-place edit.** A verifier that reaches the expected head hash
  has seen a prefix consistent with what was written.

## What it does **not** prove

- **An operator with disk access can rewrite the whole chain** before any
  checkpoint is anchored elsewhere, and the rewritten chain will verify. The
  chain detects edits *to* a chain; it does not make a chain immutable.
- **Absence of a record is not proof of absence of an action.** A missed hook,
  a daemon that was down, or a trust-gated headless run can all leave no record.
  Coverage windows and `agentwatch coverage` narrow this gap and name it; they do
  not eliminate it.
- **Origin is not established by the chain alone.** Hash integrity is not
  attributability; optional signed checkpoints (W9) add "produced by this
  installation" — never "by this human."
- **Content truth.** agentwatch records what the harness reported. It does not
  prove the reported action succeeded, or that the agent's description is true.

## How checkpoints and coverage narrow the gaps

- Checkpoints (E1) bound how far back a rewrite can reach undetected when a
  checkpoint digest is anchored off-machine (W7 notarization, or commit it to
  git / email it to yourself).
- Coverage windows (S5) and `agentwatch coverage` reconcile the store against an
  independent transcript, so a gap is surfaced rather than hidden.

## Recommended handling for a bundle

1. Verify the chain: `agentwatch verify-store`.
2. Verify privacy: `agentwatch verify-privacy`.
3. Read the coverage section: a bundle with a gap says so on its front page.
4. Verify any checkpoint signature and timestamp (W7/W9) with the published key.
5. Preserve the bundle unchanged; do not re-export over it.
"""


def statement() -> str:
    """The statement text (single source, shipped in evidence bundles)."""
    return FORENSIC_SOUNDNESS


__all__ = ["FORENSIC_SOUNDNESS", "statement"]
