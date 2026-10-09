# ADR-0034 — Agent Trace export pin + write policy

- **Status:** accepted (2026-10-07, M30 PRV-2)
- **Context:** Agent Trace is an open, storage-agnostic code-attribution spec
  (RFC v0.1, Jan 2026) adopted by Cursor, Cognition, Cloudflare, Vercel, Jules,
  Amp, OpenCode, Cline and git-ai. Implementing it makes agentwatch an
  evidence-grade source (a verifiable chain behind each record) rather than a
  silo — but the spec is a *draft on a fast cadence*, and some tools (git-ai)
  store attribution as git notes *inside the repository*.
- **Decision:** (1) **Pin** `AGENT_TRACE_SPEC_REVISION = "agent-trace-rfc-0.1"`;
  export records cite the exact revision, never "conformant to the standard", and
  a committed upstream snapshot (`schema/agent-trace/upstream-revision.json`) is
  compared by `scripts/agent_trace_drift_check.py` in
  `.github/workflows/agent-trace-drift.yml` (the AAT-5 pattern) so a move is
  surfaced, not silently absorbed. (2) **Read-only cross-validation**: a reader
  accepts existing Agent Trace / git-ai notes and classifies each
  (revision, path) key `agree | disagree | agentwatch-only | notes-only` in
  `provenance --notes`; agentwatch never overwrites them. (3) **Write only by an
  explicit, consented command**: `export-session --format agent-trace` writes to
  a file/stdout by default; writing git notes into a repository requires the
  separate `--write-notes REPO` flag (an operator decision, never a default).
- **Consequences:** the export contains ranges / hashes / conversation ids / VCS
  revisions only — **zero code content** — and passes a content-free check; the
  AAT-style `unmapped` bucket stays explicit. Drift fails CI and opens an issue
  until a human re-pins. Cross-validation is diagnostic, never an auto-merge.
- **Evidence:** `agentwatch.agent_trace`; `tests/test_provenance.py`
  (`test_export_agent_trace_is_pinned_and_content_free`,
  `test_agent_trace_drift_reports_a_revision_move`,
  `test_cross_validate_classifies_agree_disagree_and_only`,
  `test_agent_trace_default_export_writes_nothing_to_the_repo`).
- **Alternatives rejected:** claiming conformance to an unpinned "Agent Trace"
  (a moving target); writing notes by default (silently mutating a repo);
  duplicating git-ai note storage instead of cross-validating it.
