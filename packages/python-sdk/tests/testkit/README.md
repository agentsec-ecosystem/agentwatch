# Cross-Harness Test Kit corpus

Version-tagged, licensed payload/rollout corpora replayed offline against the
recorders so a harness shape change fails a fixture instead of a user. See
[`docs/design/cross-harness-testing.md`](../../../../docs/design/cross-harness-testing.md)
(PRD 47 XHT-1) and [`docs/prd/42-harness-fidelity-and-realtime.md`](../../../../docs/prd/42-harness-fidelity-and-realtime.md).

Every corpus directory carries a `manifest.json` recording its harness, version,
`kind`, source URL, upstream commit, license, and whether it came from a real
harness run. Files are scanned for secrets and are never executed — the replayer
contains them (`tests/test_testkit_corpus.py`).

| Corpus | Harness | Kind | Source | License |
|---|---|---|---|---|
| `claude-code/ouija/` | Claude Code | transcript rollouts | [kylesnowschwartz/agent-ouija](https://github.com/kylesnowschwartz/agent-ouija) | MIT |
| `codex/ouija/` | Codex CLI | rollout JSONL | [kylesnowschwartz/agent-ouija](https://github.com/kylesnowschwartz/agent-ouija) | MIT |
| `cursor/cursor-session-tracer/` | Cursor | session traces | [indranildchandra/cursor-session-tracer](https://github.com/indranildchandra/cursor-session-tracer) | MIT |
| `cursor/vendor-1.7.2/` | Cursor | native hook payloads | [cursor.com/docs/hooks](https://cursor.com/docs/hooks) | vendor docs (cited) |

The Cursor vendor payloads reuse the conformance pack at
`tests/fixtures/cursor/*.json` (framed `message` + `expected`) so the two suites
cannot drift. Upstream LICENSE files are kept beside each corpus and attributed
in [`THIRD_PARTY_NOTICES.md`](../../../../THIRD_PARTY_NOTICES.md).
