# Third-Party Notices

agentwatch is licensed under the Apache License 2.0. It incorporates or derives from third-party work
listed below.

## agent-exec-trace (AgentObservatory)

- **License:** MIT
- **Source:** https://github.com/agentsec-ecosystem/agent-exec-trace (archived; retained as a private repo — not deleted)
- **Imported commit:** `008e1c7eeed9de74044e8065e1be241bfee20704` (imported 2026-10-02)
- **What is retained:** behavior trace schema concepts, instrumentation approach, detector catalog,
  analytics pipeline design, operator UI concepts, and field-test methodology — absorbed into agentwatch
  per the ecosystem consolidation.

```
MIT License

Copyright (c) 2026 Debashish Ghosal

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the "Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the
following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO
EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
USE OR OTHER DEALINGS IN THE SOFTWARE.
```

## Cross-harness test-kit corpus (`packages/python-sdk/tests/testkit`)

Redistributed test data, each under MIT with the upstream license kept beside the
corpus. Provenance and reproduction steps:
`packages/python-sdk/tests/testkit/PROVENANCE.md`. Content-addressed lock:
`packages/python-sdk/tests/testkit/checksums.json`.

### kylesnowschwartz/agent-ouija

- **License:** MIT · Copyright (c) 2025 Kyle Snow Schwartz
- **Source:** https://github.com/kylesnowschwartz/agent-ouija
- **Pin:** `c4be5b1d0c6faaa25fc2d4c0d3718276a8c71ecc`
- **Used:** `claude/testdata/*.jsonl` (Claude Code transcripts) and
  `codex/rollout/testdata/*.jsonl` (Codex rollout logs), copied verbatim.

### indranildchandra/cursor-session-tracer

- **License:** MIT · Copyright (c) 2026 Indranil Chandra
- **Source:** https://github.com/indranildchandra/cursor-session-tracer
- **Pin:** `78219cea67e92d03bc9b5d96798adfac0636cbc9`
- **Used:** `.cursor/traces/**/*.json` (real Cursor session traces), copied verbatim.

### Cursor hooks reference (vendor documentation)

- **Source:** https://cursor.com/docs/hooks (retrieved 2026-10-05)
- **Used:** payload *shapes* for `cursor/vendor-1.7.2` and the Cursor conformance
  pack, transcribed by hand (no content copied verbatim beyond field names and
  example values). Cursor is a trademark of Anysphere, Inc.; this project is not
  affiliated with or endorsed by Cursor.

Other dependencies are listed in the SBOM published with each release.

## XHT-3 cross-parser validation tools (used in CI, not redistributed)

The Codex rollout reader (M27 COD-1) is cross-checked against two independent
OSS parsers on a golden fixture (`.github/workflows/xht3-cross-parser.yml`). They
are **cloned at a pinned commit and run only in CI** — no code is vendored into
this repository.

- **kvsankar/agent-history** — **License:** MIT · Copyright (c) 2025 Sankaranarayanan Viswanathan ·
  **Source:** https://github.com/kvsankar/agent-history · **Pin:** `56c766ad182689c887e575a1a387dfec2e4a5ebd` ·
  **Used:** its `codex_read_jsonl_messages` parser cross-checks tool-call tuples; its `docs/codex-format.md`
  documents the rollout format.

- **kylesnowschwartz/agent-ouija** — **License:** MIT · Copyright (c) 2025 Kyle Snow Schwartz ·
  **Source:** https://github.com/kylesnowschwartz/agent-ouija · **Pin:** `c4be5b1d0c6faaa25fc2d4c0d3718276a8c71ecc` ·
  **Used:** its `codex/rollout` parser cross-checks the session id/cwd and tool-I/O counts.

- **openai/codex** — the format is grounded in the Codex CLI source
  (`codex-rs/core/src/rollout/recorder.rs`, `codex-rs/protocol/src/protocol.rs`), consulted as the authoritative
  format reference. Codex is a product of OpenAI; this project is not affiliated with or endorsed by OpenAI.

- **sst/opencode** — **License:** MIT · **Source:** https://github.com/sst/opencode · the OpenCode transcript
  reader (M27 LOG-1) is implemented against the generated SDK types
  (`packages/sdk/js/src/v2/gen/types.gen.ts`: `Session`, `ToolPart`, `ToolState`). No code is vendored.
