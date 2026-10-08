# ADR-0032 — Capability inventory: content digests, origin scope, no content

- **Status:** accepted (2026-10-07, v0.2.0 M30 CAP-1)
- **Context:** The 2026 agent supply chain is *capabilities* — skills, plugins,
  hooks, subagent definitions, slash commands, rules files and MCP servers — not
  just tools. Background auto-update is the default; attackers swap a capability
  body while leaving the declared version unchanged (Plugin4Shell). An inventory
  that trusts the declared pin is blind to exactly the swap that matters, and one
  that stores capability bytes turns a security tool into a prompt/content
  exfiltration surface.
- **Decision:**
  1. **Digest the content, not the pin.** Every capability entry carries a
     `sha256` over the capability's bytes (a directory tree hashed over its files
     in sorted relative-path order). A declared version is kept as an optional
     label, never as the identity of the capability. The Plugin4Shell shape —
     same name and version, different content — therefore yields a new digest.
  2. **No content is retained.** Only kind, name, origin scope, digest, size and
     (when declared) version are stored or emitted. Files are read to hash and
     then discarded; a property test proves a planted secret never appears in the
     JSON or a serialized capability.
  3. **Origin scope is explicit** (`managed` / `user` / `project` / `plugin`) so a
     capability's provenance is part of the record, not inferred later.
  4. **Coverage is per `(harness, kind)` and honest.** Claude Code is `exposed`
     for every kind here; Cursor, Codex CLI and Gemini CLI are `none`, and memory
     is `none` for every harness (MEM-1). An unread harness is a *named* gap, not
     silence.
  5. The inventory is a **read-only derived view**; BOM includes capabilities as
     CycloneDX components (kind → component type; `agentwatch:capability-*`
     properties). It records and diffs; it never scans, scores, or blocks.
- **Consequences:** `inventory --capabilities` and `bom --format cyclonedx`
  expose the loadable surface by content digest. CAP-2 diffs these digests into
  `capability-changed`; CAP-3/MEM-1 extend kinds and attribution. Per-harness
  coverage is CI-checkable and the declared gaps in
  `reference/known-limitations.md` follow the matrix.
- **Alternatives rejected:** trusting the declared version (misses the rug-pull);
  hashing only a manifest or lockfile (misses files that are loaded without a
  manifest); storing capability content for "richer" diffing (breaks
  redact-before-store and D-K); a single global coverage flag (hides per-harness,
  per-kind gaps). Deciding maliciousness is out of scope — verdicts belong to
  scanners and policy engines.
