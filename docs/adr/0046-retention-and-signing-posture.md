# ADR-0046 — Retention profiles & signed default posture

- **Status:** accepted (2026-10-06, v0.2.0 M28 CMP-3/CMP-4)
- **Context:** AAT §9 recommends a 12-month window for high-risk systems, but retention was a hand-edited
  number on `store.retention_days` and signed checkpoints were an unreleased experiment (G8). Both are
  procurement asks ("one-click retention", "signed trails").
- **Decision:**
  1. **Named retention profiles** drive `agentwatch retention apply`: `high-risk-12mo` (365 days, AAT §9),
     `general-6mo` (180 days), and `custom` (the operator-configured `store.retention_days`). The resulting
     policy change is a recorded chain event (S5, `retention-changed`). A window whose retention has not been
     applied degrades visibly (`doctor` WARN) and the compliance report cites the active profile.
  2. **Checkpoint signing is a supported posture**, not an experiment: `checkpoint export --sign` signs a
     digest; `checkpoint rotate` replaces the key and records the rotation as a metadata-only `key-rotation`
     chain event. Verification is folded into `verify-store`/`evidence`/AAT and the posture is surfaced in
     `doctor`/`/healthz`; an epoch key we no longer hold reports *"signed by key id X, key unavailable"*.
- **Consequences:** A policy choice is citable by name; retention never hard-deletes (D-K); signing remains an
  optional dependency (`[signing]`) so the core stays dependency-light (NFR-5). Rotation ends an epoch rather
  than re-reading old signatures, so bundles must state which epoch signed them.
- **Alternatives rejected:** per-record retention classes (no demand, more schema); automatic signing key
  generation with `cryptography` in the core install (breaks NFR-5).
