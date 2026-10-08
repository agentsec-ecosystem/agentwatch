# Design — Capability Supply Chain

**BLUF:** How agentwatch inventories, diffs and attributes the 2026 agent supply chain — **skills, plugins, hooks,
subagent definitions, slash commands, instruction/rules files, MCP servers and persistent memory** — each by **content
digest**, never by declared version, with drift raised as a `capability-changed` security event and loads recorded as
`capability-loaded` context. Records and diffs; never scans or judges.

**Status:** proposed (2026-10-05, v0.2.0-expanded) · **Milestone:** M27–M28 · Sources:
[PRD 52](../prd/52-capability-supply-chain-and-memory.md), [mcp-surface.md](mcp-surface.md),
[harness-adapter-design.md](harness-adapter-design.md).

## Capability model

| Type | Examples | Origin scope |
|---|---|---|
| skill | `SKILL.md` packages | managed / user / project / plugin |
| plugin | marketplace plugin (`name@marketplace`, version) | managed / user / project |
| hook | every hook entry (incl. non-agentwatch) | managed / user / project |
| subagent / command | custom agents, slash commands | user / project |
| rules / instructions | `CLAUDE.md`, `AGENTS.md`, rules dirs | user / project |
| MCP server | stdio/HTTP servers | user / project |
| memory | auto-memory files/dirs | user / project |

Each entry: name, type, origin, first/last-seen, **content digest** (sha256), and optionally declared version. Content is
**never stored**.

## Inventory & BOM

`inventory --capabilities` lists entries; `bom --format cyclonedx` includes them as components. `inventory --snapshot`
records a point-in-time set; `inventory --diff` compares.

## Drift → `capability-changed`

Emitted when: content digest changes **without** a declared version change (the rug-pull shape — background auto-update
is default in Claude Code/Codex); a new capability appears from an unseen origin; or a new hook appears. Event is
schema-governed, OCSF/CloudEvents-mapped, exposed to sinks and the compliance report. Language is factual ("content
changed, version unchanged"), never a verdict.

## Load attribution → `capability-loaded`

Where the harness exposes it, append a metadata-only step (name, origin, digest) when a capability is loaded, so
`replay`/`impact`/`blame`/`flow`/`search` show it as context for later calls. Wording: "followed the load of", never
"caused by". Harness exposure matrix published and CI-checked.

### Load exposure matrix (CAP-3)

Not every harness exposes *what* it loaded. This matrix is the published truth; `LOAD_EXPOSURE` in
`agentwatch.capabilities` and the CI test `tests/test_capability_attribution.py::test_exposure_matrix_is_published_and_honest`
must agree with it.

| Harness | Load exposure | Note |
|---|---|---|
| claude-code | partial | recorded via the capability-loaded API; not auto-emitted from the hook payload yet |
| cursor | none | no load signal exposed |
| codex-cli | none | no load signal exposed |
| gemini-cli | none | no load signal exposed |

## Memory

Memory stores are capabilities: digest, size, last-changed, and the **session that wrote** each change. A memory change
not attributable to any recorded session is flagged. `search --memory` returns sessions following a change.

## Privacy & containment

Digests/names/sizes/origin only; no content. Foreign/unmappable capability config → quarantine. Read-only on the system.

## Testing

- Plugin4Shell-shape fixture → `capability-changed` ("content changed, version unchanged") (FT-CAP-1).
- Out-of-band memory edit → unattributed flag (FT-MEM-1).
- Property: no capability content in the store.
- Per-harness exposure matrix green against fixtures.

## Implementation status (M30)

- **CAP-1 landed (`agentwatch.capabilities`, #458).** `discover_capabilities(project=, home=)` inventories Claude
  Code skills, plugins, hooks, subagents, commands, rules files and MCP servers under `~/.claude` / `<project>/.claude`
  (plus best-effort managed paths) by `sha256` content digest, with origin scope, size and declared version;
  `inventory --capabilities` renders it and `bom --format cyclonedx` adds the entries as components. Content is
  never retained. Per-harness coverage (`exposed`/`partial`/`none`) is a first-class tuple on the inventory:
  Claude Code is `exposed`; Cursor, Codex CLI, Gemini CLI — and memory for every harness (MEM-1) — are declared
  `none` gaps.
- **CAP-2 landed (#459).** `record_capability_snapshot` writes one metadata-only `capability-snapshot` carrier per
  session (the whole set, so an empty set is a baseline); `detect_capability_changes` diffs consecutive sessions and
  `capability_event` emits the reused `capability-changed` event with a factual class — `added`, `removed`,
  `content changed, version unchanged` (the Plugin4Shell shape), or `content changed, version changed`.
  `inventory --capabilities --snapshot` records; `inventory --capabilities --diff --since 7d` lists the drift.
  Language is factual throughout; no output path labels a change malicious.
- **CAP-3 landed (#460).** `record_capability_load` / `capability_loaded_record` append a metadata-only
  `capability-loaded` step (name, kind, scope, digest). `replay` prints it inline as "followed the load of …",
  `impact` lists the session's loads, and `search --capability <name>` returns the load plus the calls recorded
  after it (never other sessions). The load-exposure matrix above is published and CI-checked. Wording is context,
  never causation.

## Decision

ADR-0032 (inventory scope, digest semantics, no-content rule), ADR-0043 (memory scope).
