# Design — Cross-Harness Test Kit

**BLUF:** How agentwatch proves harness compatibility without owning proprietary CLIs: a version-tagged payload/
transcript corpus + replay runner wired into the O1 conformance suite, a live OpenCode soak, cross-parser
validation, and fidelity tiers. **How** — the requirement is
[PRD 47](../prd/47-cross-harness-testkit.md) (XHT-1..4).

**Status:** proposed (2026-10-05, v0.2.0) · **Milestone:** M25 · Sources:
[PRD 47](../prd/47-cross-harness-testkit.md), PRD 27 (O1/N3/N4/I2), PRD 42, PRD 45. Raw provenance:
[reference/v0.2.0-research-sources.md](../reference/v0.2.0-research-sources.md) §9.

## Three verification levels

| Level | Mechanism | Owns the CLI? |
|---|---|---|
| Payload replay | JSON on stdin → hook binary (Claude Code + Cursor both work this way) | no |
| Golden fixtures | transcript/rollout files replayed through the reader | no |
| Live stand-in | OpenCode (MIT, provider-agnostic) with our plugin hooks | free/OSS |

## How to test without owning the CLI (practical recipes)

The core insight: a recorder adapter is tested against a harness's **event shape**, not the harness binary.

### 1. Payload replay (offline, today)

Both Claude Code and Cursor deliver hooks as **JSON on stdin to a command**, so the officially documented test
pattern is simply piping a payload into the hook:

```sh
# Claude Code shape
echo '{"session_id":"s1","hook_event_name":"PreToolUse","tool_name":"Bash",
       "tool_input":{"command":"ls"},"cwd":"/tmp"}' | agentwatch-hook

# Cursor shape (hooks.json; same stdin contract)
echo '{"hook_event_name":"beforeShellExecution","command":"npm test",
       "session_id":"f3b9...","ide":"cursor-cli"}' | agentwatch-hook
```

Fixture sources to mine for real shapes (all OSS/published):
- **o11y-dev/opentelemetry-hooks** — managed setups for Cursor/Codex/Claude/Gemini/Copilot/OpenCode/Windsurf;
  **published canonical cross-harness event-name mapping table** (mirror/cite it in our adapter docs).
- **base76-research-lab/claude-code-hooks** `HOOKS_REFERENCE.md` — every Claude Code hook event's stdin payload +
  the manual test recipe; **Vizzuality/claude-code-vault** and **dinesh-bay/claude_code_hooks** corroborate.
- **Elastic Security Labs' Cursor audit** — a deployed `hooks.json` + audit script (the best reference for
  Cursor `before*/after*` payloads and IDE-vs-CLI env detection).
- **last9/cursorscope · LangGuard-AI/cursor-otel-hook · indranildchandra/cursor-session-tracer** — Cursor hook→span
  mappings to cross-check our expected span trees.

### 2. File-format replay (offline)

For file formats, adopt OSS test fixtures as golden corpora and cross-check against two independent parsers:
- **kvsankar/agent-history** (`docs/codex-format.md` verified from source; supports `CODEX_SESSIONS_DIR` override —
  designed for testing; 728 unit + 16 E2E tests).
- **ahmojo/codex-claude-transfer** (Go; treats rollout JSONL as source of truth; handles `.jsonl.zst`; Claude↔Codex
  cross-format conversion = a fixture generator).
- **kylesnowschwartz/agent-ouija** (verified vs codex-cli 0.144.1; dangling-session heuristic).
- **klyne-ai/klyne**, **shinshin86/codex-history-list**, **wondercoms/codex-logs**, **osolmaz/codex-session-extract**,
  **ethpandaops/codex-agent-sdk-go**, **lin-guanguo/llm-memory-research**.

### 3. Live stand-in (real agent, no proprietary CLI)

- **OpenCode** (`sst/opencode`, MIT, provider-agnostic — local/cheap models) exposes the same modern hook surface
  as the proprietary CLIs (`tool.execute.before/after` covering bash/read/write/MCP, `session.created/deleted/idle`,
  `file.changed`). Run it locally with a pinned model and the recorder attached → a genuine authenticated-free
  pipeline in CI.
- **Codex CLI itself is open source** (`openai/codex`, Rust) — no ChatGPT subscription required; point it at an
  alternative provider and run headless against a scratch repo to generate genuine rollouts (then scrub, I2).
- **Claude Code Agent SDK** (TS/Python) runs headless with just an API key for authentically-shaped Claude traffic.
- **Goose (Block)** and other OSS agents for breadth.

**Honest boundary:** Cursor is closed — for it, Level 1+2 plus community-contributed golden captures is the path,
and the matrix row stays `fixture-verified` until a consented live capture lands. Never blur fixture-verified into
`full`.

## Corpus layout

```
tests/testkit/<harness>/<version>/
  payloads/*.json        # Claude Code, Cursor hook payloads
  rollouts/*.jsonl(.zst) # Codex, Claude transcripts
  telemetry/*.log        # Gemini OTel
  frames/*.json          # OpenCode, Copilot
  manifest.json          # version tags, source citations, expected record shape
```

Sources: published docs, OSS projects' test data (o11y-dev/opentelemetry-hooks canonical event map; Elastic's
Cursor payloads; kvsankar/agent-history; ahmojo/codex-claude-transfer; kylesnowschwartz/agent-ouija), and consented
captures. **I2 scrub-and-commit:** every fixture passes the secret scan; licenses recorded in `THIRD_PARTY_NOTICES`.

## Replay runner

- `agentwatch replay-fixtures --adapter <x> --dir <corpus>` (or an O1 pytest entry) pipes each payload/fixture
  through the adapter/daemon and asserts the canonical record output.
- Includes ordering, duplicate, and malformed variants (the fake_harness emitter behaviors, N3).
- `--self-test` runs a deliberately broken adapter and asserts the runner fails (proves the gate works).

## OpenCode live soak

- Nightly CI: OpenCode in a scratch repo, recorder attached via plugin hooks
  (`tool.execute.before/after`, `session.created/idle`, `file.changed`), full pipeline for hours.
- Hermetic: a pinned local/cheap model, no egress beyond the model endpoint (or fully offline).
- Discovered quirks become corpus fixtures (feedback loop into XHT-1). OpenCode becomes a supported matrix row.

## Cross-parser validation

For Codex/Claude file formats, CI diffs our reader against **two independent OSS parsers** on the same fixtures.
Divergence is a failing test or a documented interpretation gap. Parsers are version-pinned and attributed.

## Fidelity tiers (XHT-4)

`live-verified | fixture-verified | modeled`, emitted by the N4 matrix generator with corpus citations. A
`full`/`live-verified` claim requires a live-capture reference; a closed harness stays `fixture-verified` until
captured. Claims-ledger entries for tier statements.

## Non-goals

- Not a behavioral emulator of the CLIs — we validate the **recorder**, not the harness.
- No scraping proprietary binaries for shapes; docs + OSS fixtures + consented captures only.
