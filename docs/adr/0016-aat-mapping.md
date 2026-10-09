# ADR-0016 — AAT mapping and lossless-or-explicit policy

- **Status:** accepted (2026-10-05, v0.2.0) — implemented
- **Context:** see [PRD 41](../prd/41-standards-and-interop-ii.md) AAT-1..5 and
  [design/aat-mapping.md](../design/aat-mapping.md). The IETF Agent Audit Trail draft is Standards Track but
  moving (`-06`, Sept 2026); EU AI Act Art. 12(2) requires logs conforming to "recognized standards."
- **Decision:** Emit/ingest AAT as an export/ingest format over the source-of-truth record schema; map fields
  losslessly or carry them in an explicit `unmapped` array (never invent); add `record_phase` locally; pin the draft
  revision and drift-check it (W4 pattern).
- **Consequences:** First reference-grade AAT implementation and a compliance on-ramp; carries ongoing re-pin cost
  and a strict "never claim stable-standard conformance" wording rule.
