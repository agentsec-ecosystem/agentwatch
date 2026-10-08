# ADR-0043 — Persistent memory stores are capabilities

- **Status:** accepted (2026-10-07, v0.2.0 M30 MEM-1)
- **Context:** Harnesses now keep persistent auto-memory that is loaded into
  future sessions. Memory poisoning is OWASP ASI06 and a cross-session path: a
  store edited between sessions steers later behavior with no trace. DET-7
  already records memory read/write/delete *operations*, but it does not
  inventory the store itself, so a changed file is not diffed and the writer of
  a change is not attributable.
- **Decision:**
  1. A memory store is inventoried as an ordinary **capability** (kind
     `memory`): name, origin scope (`user`/`project`), content `sha256` digest,
     size and last-changed. Content is never retained — the same no-content rule
     as CAP-1.
  2. A store change is **attributed** to the session that recorded a matching
     `memory` *write* operation (key/name match). A change with no matching
     recorded write — an out-of-band edit by something other than a recorded
     agent — is flagged **unattributed** (`MemoryStoreChange.is_unattributed`).
  3. Memory stores appear in `inventory --capabilities` and
     `inventory --memory`; `search --memory-store <name>` returns the write plus
     calls recorded after it in the same session. The existing `search --memory`
     (operation listing, DET-7) is unchanged.
  4. Exposure is declared per harness: Claude Code is `partial` (directory
     discovery + writer attribution; the auto-memory layout is not pinned);
     Cursor, Codex CLI and Gemini CLI are `none`. The matrix is published and
     CI-checked.
- **Consequences:** A poisoned memory file changed between sessions is visible as
  a digest change and, when no recorded session wrote it, explicitly
  unattributed — never silently blamed and never silently ignored. Detection of
  *malicious* memory content remains out of scope (that is a scanner/policy
  concern). CAP-1's per-harness coverage moves memory from `none` to `partial`.
- **Alternatives rejected:** hashing DET-7 operation records only (misses edits
  made outside any recorded operation); treating every change as attributed to
  the last session (a fabricated claim); storing memory content for comparison
  (breaks redact-before-store).
