# Test-kit corpus provenance & reproduction

**Why this file exists:** every byte of the cross-harness corpus under this
directory is third-party, licensed test data. This records *where each corpus
came from*, *how to recreate it exactly*, and *what scrub/scan it passed*, so the
corpus can be audited, refreshed, or rebuilt without guesswork. Milestone M25 ·
issues **#303 (CUR-1)**, **#309 (XHT-1)**.

The machine-readable lock is [`checksums.json`](checksums.json); the re-fetch
tool is [`scripts/fetch-testkit-corpus.py`](../../../../scripts/fetch-testkit-corpus.py).

## Pinned sources

| Corpus dir | Harness | Upstream repo | Pinned commit | Upstream path | License |
|---|---|---|---|---|---|
| `claude-code/ouija/rollouts/` | Claude Code | https://github.com/kylesnowschwartz/agent-ouija | `c4be5b1d0c6faaa25fc2d4c0d3718276a8c71ecc` | `claude/testdata/*.jsonl` | MIT |
| `codex/ouija/rollouts/` | Codex CLI | https://github.com/kylesnowschwartz/agent-ouija | `c4be5b1d0c6faaa25fc2d4c0d3718276a8c71ecc` | `codex/rollout/testdata/*.jsonl` | MIT |
| `cursor/cursor-session-tracer/traces/` | Cursor | https://github.com/indranildchandra/cursor-session-tracer | `78219cea67e92d03bc9b5d96798adfac0636cbc9` | `.cursor/traces/**/*.json` | MIT |
| `cursor/vendor-1.7.2/` (payloads) | Cursor | https://cursor.com/docs/hooks (retrieved 2026-10-05) | n/a (published docs) | hand-transcribed | vendor docs (cited) |

Each git-backed corpus directory keeps a copy of the upstream `LICENSE` and a
`manifest.json` recording its harness, version tag, source, commit, license, and
whether it came from a real harness run. The same facts are attributed in
[`THIRD_PARTY_NOTICES.md`](../../../../THIRD_PARTY_NOTICES.md).

## How the corpora were selected (and what was rejected)

- **Adopted (permissive, real captures):** `agent-ouija` (MIT) ships real Claude
  Code transcripts *and* Codex rollout JSONL; `cursor-session-tracer` (MIT) ships
  real Cursor session traces.
- **Reference only (no license):** `o11y-dev/opentelemetry-hooks` has per-harness
  contract fixtures for 8 harnesses but **no license file** — cited, never copied.
- **Reference only (docs/schema):** `johnlindquist/cursor-hooks` (MIT schema) and
  `dinesh-bay/claude_code_hooks`, `shanraisshan/claude-code-hooks`,
  `kvsankar/agent-history`, `ahmojo/codex-claude-transfer` (MIT) inform shapes but
  are not raw payload corpora.

## Reproduce / recreate

Requires `git` and network access for the git-backed corpora.

```sh
# Re-fetch every git corpus at its pinned commit, restage, and rewrite the lock:
python3 scripts/fetch-testkit-corpus.py

# Verify the staged bytes against the committed lock (offline):
python3 scripts/fetch-testkit-corpus.py --check

# Rewrite the lock from the currently staged files (offline; use after a
# reviewed change, never to paper over unexpected drift):
python3 scripts/fetch-testkit-corpus.py --rehash
```

The pinned commit is fetched with `git fetch --depth 1 origin <sha>`, so a moved
branch cannot change the corpus; a silent upstream change is caught because the
lock is content-addressed (`sha256`). `tests/test_testkit_corpus.py` asserts the
staged files match the lock on every test run.

### Cursor vendor payloads (`cursor/vendor-1.7.2`)

These are **transcribed by hand** from the published Cursor hooks reference
(https://cursor.com/docs/hooks, retrieved 2026-10-05) into the conformance pack
`packages/python-sdk/tests/fixtures/cursor/*.json` (`message` + `expected`). The
test-kit manifest points at that pack (`payloads_dir: ../../../fixtures/cursor`)
so the two suites cannot drift. There is deliberately no scraper: the vendor
payloads change with the Cursor contract and are re-transcribed under review,
then the compatibility table / drift baseline is regenerated with
`python3 scripts/generate_compatibility.py`.

## Scrub & scan

The corpus is committed **only** after it passes the secret scan. Every corpus
file is scanned by `agentwatch.secrets.detect` in
`tests/test_testkit_corpus.py::test_corpus_files_are_secret_free`; a hit fails
CI. One vendor example that carried a plaintext `user_email` was scrubbed (the
raw PII removed; principal hashing is exercised in the adapter unit test
instead). No corpus content is ever executed — see
`test_corpus_parsers_never_spawn_a_shell` and ADR-0024.

## Fidelity claim

Community/vendor corpora make the Cursor row **`fixture-verified`**, not
`live-verified` (a closed harness stays fixture-verified until a consented live
capture lands — `design/cross-harness-testing.md`). The generated table lives in
`docs/reference/compatibility.md`.
