# v0.2.0 field-test fixtures (M31 31.2/31.3)

These are **assembled**, not hand-maintained: `python3 scripts/fieldtest/build_fixtures.py`
(`make fieldtest-fixtures`) copies the parser-valid fixtures the SDK test suite
already ships into `fixtures/<kind>/` and synthesizes the few kinds with no
source (CCA, OpenCode, hostile). Re-running is safe — each directory is cleared
and rebuilt from its source, so it cannot drift. Every kind carries a
`manifest.json` (version, source, synthesised flag, file list) and is
secret-scanned (`build_fixtures.py` reports any real-secret-looking markers).

Version-tagged, secret-scanned fixtures the v0.2.0 drivers read from
`/ft/fixtures/<kind>/` inside the recorder container. Each fixture cites its
public source and ships shape-synthesized only (never real secrets), per
ADR-0024 / COR-4. Populated by M31 31.2/31.3; a driver whose fixture is absent
fails its case (no skip).

| Kind | Used by | Contents |
|---|---|---|
| `aat/` | FT-AAT-1/2/3 | AAT bundles + a foreign bundle with non-normalizable records |
| `otel/` | FT-OTEL-1/2/3/4 | canonical agent-span trees; privacy-mode samples |
| `cursor/` | FT-CUR-1/2 | version-tagged Cursor golden corpus + blocking events |
| `gemini/` | FT-GEM-1 | captured Gemini native-OTel telemetry (logPrompts) |
| `codex/` | FT-COD-1 | rollout logs incl. `.jsonl.zst`, dedup, dangling session |
| `mcp/` | FT-MCP-1/2 | MCP frames across 2025-06-18 / 2025-11-25 / 2026-07-28 |
| `logreaders/` | FT-LOG-1 | Codex/Gemini/Copilot/OpenCode long-tail logs |
| `a2a/` | FT-A2A-1 | signed + unverifiable agent cards; task lifecycle |
| `gateway/` | FT-GWY-1 | LiteLLM-shaped gateway OTLP (exact vs estimated cost) |
| `cca/` | FT-CCA-1 | Claude Compliance API pull fixture |
| `acs/` | FT-ACS-1 | ACS Guardian audit-trail fixture |
| `cco/` | FT-CCO-1/2 | captured Claude Code OTel + Agent-SDK run |
| `system/` | FT-SYS-1 | AgentSight/Tracee-shaped process tree (Linux) |
| `xht/` | FT-XHT-1/3 | payload corpus for replay + a deliberately broken adapter |
| `opencode/` | FT-XHT-2 | hermetic OpenCode session for the live soak |
| `hostile/` | FT-HOSTILE-1 | weaponized payloads (Codex #36937 backtick, AAT/Cursor/OTel/A2A fuzz) |
