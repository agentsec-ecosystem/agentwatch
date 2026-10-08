# ADR-0033 — Content-free range+hash capture

- **Status:** accepted (2026-10-07, M30 PRV-3)
- **Context:** Line-level attribution (`provenance`, PRD 53) needs the affected
  line range of each file-modifying call and a way to tell whether the stored
  range still matches the code it names. The product's default posture is
  metadata-only capture with redact-before-store (ADR-0006, DD-06): tool
  arguments — and therefore any content-based line derivation — are dropped.
  Without a deliberate decision, PRV-1/PRV-2 would either be inaccurate or
  quietly erode the "no content stored" guarantee.
- **Decision:** Capture, per file-modifying call and **under every privacy
  mode**, a **content-free** attribution fact: the affected line range(s) (when
  the harness exposes a range) and a **keyed** content hash. The fact is
  metadata, not content, so it is legal in `metadata-only`; it rides in a
  reserved key inside `tool.arguments`
  (`agentwatch_attribution`, `agentwatch.provenance`). Hashes use the per-install
  keyed HMAC-SHA256 (the same mechanism as identity/content-flow fingerprints),
  so equal content is correlatable within one installation but not recoverable
  and not comparable across installations. When a harness does not expose a
  range, capture falls back to **file-level `heuristic`** attribution. The shape
  is versioned (`RANGE_CAPTURE_VERSION`) and guarded by `is_content_free`.
- **Consequences:** `provenance` shows `exact` ranges where a structured edit
  exposed one and `heuristic` file-level attribution otherwise; the store keeps
  its no-content guarantee (a range and a keyed hash are not content). Line
  tracking across rebase/squash remains git-ai's domain (not goals). The capture
  primitive and its content-free property are implemented and proven in
  `agentwatch.provenance`; persisting the reserved fact from the live hook before
  redaction is owned by the capture/redaction path (record schema/redact are a
  different workstream), so end-to-end persistence under `metadata-only` is a
  **declared gap** (see `reference/known-limitations.md`), not a silent claim.
- **Evidence:** `agentwatch.provenance.capture_ranges` / `is_content_free`;
  `tests/test_code_provenance.py` (`test_capture_is_content_free_under_metadata_only`,
  `test_attack_pack_never_leaks_content`, `test_property_capture_never_contains_the_content`).
- **Alternatives rejected:** storing content or diffs (violates DD-06); storing a
  line range with no hash (a range can drift under a later edit and cannot be
  validated); unkeyed hashes (enumerable / comparable across installs).
