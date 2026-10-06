# Changelog

All notable changes to agentwatch are documented here. Format: [Keep a Changelog](https://keepachangelog.com/),
versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- v0.2.0 Interop & Proofs (M26):
  - AAT-3: `agentwatch ingest --format aat` verifies a foreign AAT bundle's chain before storage and
    quarantines untrusted/non-normalizable records with a reason (#313).
  - AAT-4: AAT conformance vectors (`schema/vectors/aat/`) with a dependency-free second verifier and a
    dual-verifier drift check (#314).
  - AAT-5: the AAT draft revision is pinned and carried in `--version`, with a drift check + re-pin policy (#315).
  - OTEL-3: `ingest --format otel` auto-detects OTLP protobuf; `--format otlp-grpc` streams gRPC-framed OTLP
    with bounded memory (#316).
  - TRACE-2: `agentwatch trace <tid>` and `replay --trace` reconstruct one causal chain across hosts/sessions,
    surfacing clock skew and propagation breaks (#317).
  - CUR-3: Cursor coverage reconciliation against the session-tracer corpus (`gap:cursor-hook-coverage`) (#318).
  - STR-2: `agentwatch.live.LiveTail` — store-truth back-fill reconciliation with classified gaps and a
    visible `degraded` state (#319).
  - STR-3: a bounded streaming soak harness + CI job asserting zero store loss (#320).
  - DET-2/DET-3: the field-test scenario matrix is the rule-detector coverage gate (38/38 non-silent); the
    catalog publishes generated, drift-guarded per-detector precision/recall; detectors replay the real testkit
    traces (#321, #322).
  - COR-1: a versioned, machine-checkable, governance-scanned public detector corpus
    (`schema/vectors/detectors/detector-corpus-v1.json`) (#323).
  - IDN-2/IDN-3: `search --identity`, and attribution (agent, credential, on-behalf-of, delegation, approval)
    rendered in `blame`/`tree`/`trace`/`impact` (#324, #325).
  - CMP-1/CMP-2: `agentwatch compliance report` (control → evidence → verdict → refs + retention/signature
    status; never certifies) with five framework templates (#326, #327).
  - GWY-1/GWY-2: LiteLLM/Portkey OTel ingest recipes and exact, source-stamped gateway cost attribution
    (`exact`/`estimated`/`mixed`/`unknown`) (#328, #329).
  - API-1: published `openapi.json` + a drift-checked typed client (#330).
  - RSK-2/SEC-1: threat-model rows linked to real tests, accepted v0.2.0 ADRs, and v0.2.0 surface rows in the
    threat→test traceability and recorder attack matrix (#332, #429).
  - PERF-1: the perf harness now covers OTLP protobuf ingest, live-tail reconciliation, and the detector-eval
    matrix, each with its own absolute budget and committed-baseline drift band; `docs/reference/performance.md`
    is regenerated from the run (#430).
- v0.2.0 Foundations (M25):
  - OTEL-1: re-pinned GenAI semconv to `1.37.0`, added the canonical agent-span operations
    (`create_agent`, `invoke_agent`, `invoke_workflow`, `plan`, `execute_tool`) and an operation drift check;
    the pin rides in `--version` and resource attributes (#297).
  - XHT-4: compatibility matrix now declares fidelity tiers (`live-verified | fixture-verified | modeled`);
    `compatibility.FIDELITY_TIERS` is the single source and the generated table is regenerated (#310).
  - NAM-1: install-integrity guard (`agentwatch.naming`) — a distribution-check warning in
    `--version`/`init`/`doctor` when `agentwatch` came from a namesake distribution, the namesake FAQ, and a
    guard test; ADR-0026 records the full-rename decision (#312).
  - FLD-1a: the v0.2.0 field-test plan (`docs/field-test/v0.2.0/field-test-plan.md`) with the case roster (#370).
  - AAT-1/AAT-2: IETF Agent Audit Trail export — `agentwatch.aat` field mapping (pinned
    `draft-sharif-agent-audit-trail-06`), `record_phase` + identity population, an explicit `unmapped` block
    (response_hash/response_size) and `agentwatch export-session <id> --format aat` emitting the bundle with
    the chain envelope and a coverage/gap block, re-verifiable via `verify_aat` (#295, #296).
  - IDN-1: agent-identity privacy policy (`agentwatch.identity`) — on-behalf-of `principal` and
    `delegation_chain` are hashed with a per-install keyed HMAC by default (plaintext only under `full`),
    and identity fields never carry secret material (property-tested). The Claude Code adapter attaches the
    dimension from optional hook fields (`principal`, `workload_identity`, `credential_class`,
    `delegation_chain`); absent facts stay honest `unknown` (#299).
  - SCHEMA-1: additive record/event schema — `record_phase` (AAT-1, pre/post-execution), `traceparent`
    (W3C Trace Context), the `agent_identity` dimension (`workload_identity`, `credential_class`,
    `principal`, `delegation_chain`), and the `agent-delegation` observation event; record-format spec,
    data dictionary, OCSF mapping, and a forward-compat fixture updated. The `schema_version` /
    `event_version` read range is `0.1.0`–`0.2.0`; the emit version stays `0.1.0` until the release bump
    (M30 30.3) (#424).
  - ADR-0026 recorded: naming decision is a **full rename at v0.2.0** (target name TBD; tracked with the
    M30 30.16 rename outcome) (#312).
  - CUR-2: Cursor native-hooks adapter (`agentwatch.adapters.cursor`), realigned to the published Cursor
    contract (`conversation_id`, `generation_id`, `workspace_roots`, `file_path`, `cursor_version`,
    `user_email`) — normalizes the full agent loop (session boundaries, pre/post tool use + failure,
    shell, MCP, `beforeReadFile`, file edits, subagents, prompt submission, compaction,
    `afterAgentThought`/`afterAgentResponse`, Tab hooks, `stop`, `workspaceOpen`), records blocking
    `before*` events as observations and never answers them (monitor-only, R2), tags the IDE/CLI/remote
    environment, hashes the `user_email` principal (IDN-1), and declares the cloud-agent hook gap;
    conformance pack + compatibility row `fixture-verified` (#304).
  - CUR-1: Cursor audit corpus — a version-tagged, secret-scanned cross-harness test kit
    (`tests/testkit/`) adopting MIT upstream test data (agent-ouija Claude Code transcripts + Codex
    rollouts; cursor-session-tracer session traces) and vendor-documented Cursor payloads, with a
    content-addressed lock, per-corpus manifests, license copies, `PROVENANCE.md`, and a pinned
    re-fetch tool (`scripts/fetch-testkit-corpus.py`); replay/containment suite
    `tests/test_testkit_corpus.py` (XHT-1) (#303).
  - RSK-1: extended the untrusted-input fuzz suite to the v0.2.0 parsers — Cursor hook JSON,
    Gemini/OTel telemetry, and AAT bundles — plus the Codex #36937 backtick-execution regression seed,
    a static shell-reference guard, and a dynamic no-exec test; the mutation gate now covers Cursor
    phase/MCP normalization, AAT chain/unmapped mapping, sampler never-sample-security, and stream
    overflow (#311).
  - 25.T: milestone integration suite (`tests/test_m25_integration.py`) composing the M25 pieces end
    to end — Cursor hooks -> store -> replay, an oversized-segment containment case, Gemini telemetry
    file -> ingest -> store, privacy-mode content-containment across all four modes, AAT export ->
    verify with trace/identity/chain, streaming drop-consumer against store truth, and sampler
    determinism (#371).
  - 25.D: milestone documentation swept to the implemented state — design statuses (aat-mapping,
    agent-identity, streaming-views, sdk-lifecycle, cross-harness-testing, harness-adapter-design),
    PRD 41/42/46/47 M25-subset notes, README compatibility, the regenerated reference/compatibility
    table, reference/known-limitations, THIRD_PARTY_NOTICES, and the WBS index; link-check and
    executable-doc gates green (#372).
- Standards & Compliance Acceptance (M22, PRD 39):
  - EU AI Act (Art. 12/19/26) and ISO/IEC 27001/42001 + NIST SP 800-92 mappings, each control naming an
    evidence command, with an explicit "what we do not provide" (W1 #270, W2 #271).
  - Open artifact standards pinned: OCSF 1.5.0, CloudEvents 1.0, CycloneDX 1.5, lossless-or-explicit
    (W3 #272).
  - OTel GenAI semconv pinned (1.29.0), carried in `--version` and resource attributes, with a drift
    check (W4 #273).
  - Enforceable schema stewardship: `schema/GOVERNANCE.md`, `schema/CHANGELOG.md`, and a policy check
    that fails a schema change without a changelog entry (W5 #274).
  - A forensic-soundness statement shipped inside every evidence bundle (W6 #275).
  - `agentwatch checkpoint export` (digest + optional RFC 3161 token) and optional ed25519 signed
    checkpoints with `checkpoint verify` (W7 #276, W9 #278).
  - OpenSSF Best Practices self-assessment and OSV/advisory process (W8 #277).
- Configuration, Profiles & Capture Hygiene (M21, PRD 37):
  - `agentwatch config explain [KEY] [--diff]` — each key's effective value, winning layer, and the
    layers it overrode; never prints a secret value (S34 #265).
  - `agentwatch init --profile solo|team|compliance|ci` — consent-first config bundles; `--set` wins
    (S35 #266).
  - Per-record capture limits (`limits.*`) with a visible `truncated` marker naming the field, original
    size, and rule; over-limit records are still appended (S36 #267).
  - `agentwatch union` — a read-time union of hook records and SDK spans with an explicit `source` and
    a stated chain-protection distinction; no write-time chain change (S11 #268).
  - `agentwatch.redactor` — a standalone, experimental public redaction API and a `redact` stdin→stdout
    filter; findings name a kind and location, never a value (S13 #269).
- Standards & Interop (M20, PRD 36):
  - OCSF + CloudEvents mappings for the security-event schema; `export-session --format ocsf|cloudevents`
    (S8 #260, pinned OCSF 1.5.0 / CloudEvents 1.0, lossless-or-explicit `unmapped`).
  - A reference security-event consumer under `examples/`, exercised in CI against a fixture stream
    (S38 #261).
  - A thin OTel collector component mapping records to GenAI-semconv spans with a pinned semconv
    version (S39 #262).
  - Opt-in, rule-free file/webhook/syslog event forwarding sinks (`sinks.*`), gated on the redaction
    self-test; events only, bounded queue, visible `degraded` on failure (S10 #263).
  - MCP tool-surface snapshot + drift: `mcp-surface` carriers, `inventory --snapshot|--diff`, and the
    new `tool-surface-changed` security event (S4 #264).
- Capture Context (M19, PRD 35):
  - Approval provenance: an `approval` dimension (`user | auto | not-required | denied | unknown`)
    derived from the permission surface, defaulting to `unknown` where unproven (S14 #255).
  - Context-compaction boundaries as a metadata-only `context-compacted` step (S15 #256).
  - A session-start environment snapshot: git revision/branch/dirty (S16 #257) and the OS principal
    with `interactive | headless | ci` (S29 #258), metadata only.
  - `agentwatch demo [--purge]` — proves the hook→daemon→store→chain pipeline with synthetic events
    tagged `producer.kind: demo` (S31 #259). `search --approval`.
- Content-Flow Forensics (M18, PRD 34):
  - Keyed-HMAC `content-flow` edges: when captured response content reappears in a later tool argument,
    a metadata-only observation records source/sink indices, source class, and a fingerprint — never
    content (S22 #253). `agentwatch flow <id> [--record]`.
  - `agentwatch secrets` — exposed-secret tracing across a session by keyed fingerprint, with a plain
    `rotate: recommended` / `no evidence of egress` line and no values (S23 #254).
- Investigation & Impact (M17, PRD 33):
  - A shared, published, versioned argument classifier (`cls1`) with `exact`/`heuristic` confidence and an
    `unclassified` bucket; facts only, never a verdict (S3).
  - `agentwatch impact <id>` — a session's change footprint / blast radius (files, side effects, network,
    VCS, credential-adjacent) (S3 #244).
  - `agentwatch blame <path>` — the file-centric reverse index, newest first (S18 #246).
  - Session behavior fingerprint `bd1:<sha256>` and `sessions --group-by-behavior` (S7 #249).
  - `agentwatch cost [--by …]` over a versioned local pricing table (`pr1`); unknown models are
    `tokens only, price unknown` (S6 #252).
  - `agentwatch tree <id>` — the subagent fan-out (S17 #245).
  - `agentwatch at "TIME" [--window]` — the cross-session time window with a gap header (S24 #247).
  - Denied-then-retried sequences surfaced in `replay`, `impact`, and the evidence bundle (S25 #248).
  - Session end-state derivation (`completed`/`interrupted-by-user`/`errored`/`abandoned`/`unknown`)
    shown in `sessions` and `diff` (S33 #250).
  - `agentwatch digest` — a local markdown weekly readout (S37 #251).
- Coverage & Recorder Trust (M16, PRD 32):
  - `agentwatch coverage [--since] [--project] [--session] [--transcripts] [--json]` reconciles the
    store against transcript ground truth (A5 allow-list: counts + tool names only) and classifies every
    gap as `gap:daemon-down`/`quarantined`/`trust-gated-headless`/`hook-not-installed`/
    `transcript-format-drift`/`harness-drift`/`unexplained` (S2).
  - Recorder-state audit records — `recorder-installed`/`recorder-uninstalled`/`config-changed`/
    `privacy-mode-changed`/`retention-changed`/`export-configured`/`coverage-window-open`/`-close`
    markers written by `init`/`uninstall` and config reconciliation (S5).
  - Harness-drift canary — the daemon observes unrecognized top-level fields and unknown hook phases
    (names only, allow-listed, capped, debounced) as `harness-drift` observations, surfaced by `doctor`
    and `/healthz` and cited by `coverage` (S19).
  - `agentwatch quarantine list | inspect <id> | requeue [--all] | clear --yes` over the B4 dead-letter
    queue; `inspect` is redacted by default and a `--raw` read is recorded as a `store-access` (S27).
  - `agentwatch archive --before DATE [--out DIR]` seals an old chain prefix into an independently
    verifiable segment and leaves one anchor record; `verify-store`, `search`, and `replay` read across
    the boundary and report a missing segment as present-but-unavailable (S28).
  - Anti-forensics suite and the published
    [recorder attack matrix](docs/design/recorder-attack-matrix.md) (S30).
- Evidence & Provenance (M15, PRD 31):
  - `producer` provenance field on every record (`hook`/`import`/`event`/`ingest`/`proxy`/`sdk`);
    legacy records read as an inferred `hook`, never rewritten; `search --producer` (S26).
  - `agentwatch annotate <id> --note TEXT [--tag NAME]` — append-only, redacted, metadata-only
    operator notes in the chain; `sessions --tag` filters (S20).
  - `store-access` audit records for `export`/`export-session`/`evidence`/`bom` (scope + destination
    kind; failed attempts recorded) (S21).
  - Redaction receipts: `replay --receipts` / `--json` receipt block, and `redact --preview SAMPLE`
    (before/after, stores nothing) (S32).
  - `agentwatch bom` — an observed Agent Bill of Materials as CycloneDX 1.5, with a mandatory
    `coverage` block and tool-surface digests (S9).
  - `agentwatch evidence <id>` — a self-contained, offline-verifiable incident bundle
    (`manifest.json`, `records.ndjson`, `chain.json`, `verify.*`, `privacy.json`, `coverage.json`,
    `inventory.json`/`bom.cdx.json`, `summary.md`, `SCHEMA/`); `evidence verify bundle.zip` reports
    intact / complete / leak-free independently (S1).
  - `agentwatch-verify` — a stdlib-only zipapp verifier plus a published reference implementation,
    both checked against the Q6 store vectors (S12).
- Local hash-chained store (M4): `agentwatch.store.RecordStore` (append-only JSONL envelope with a
  sha256 chain), `agentwatch verify-store`, retention tombstones that keep the chain links, and a
  size-cap that fails closed without overwriting (F3/F4).
- Secret/PII redaction (M4, R5): `agentwatch.secrets` masks API keys/tokens, private keys, JWTs, cards
  (Luhn-checked), SSN, email, phone, and credential-bearing connection strings to `<REDACTED:kind>`,
  emits a `secret-detected` security event, and adds the `full` privacy mode; `agentwatch.selftest`
  gates export on a fixed-corpus self-test (DD-09).
- `agentwatch init` / `agentwatch uninstall` (M3): install Claude Code hooks into
  `.claude/settings.local.json` (or `--scope user`) and start/stop the local daemon; `agentwatch sessions`
  lists recorded sessions; `agentwatch status` reports installed hooks (project/user) and daemon state.
  `PostToolUseFailure` is recorded as `outcome="error"`; hook installation is idempotent and refuses a
  malformed settings file rather than overwriting it (F7).
- Claude Code adapter, hook, and daemon (M3): `agentwatch.adapters.claude_code.normalize`, the
  `agentwatch-hook` fire-and-forget UDS client, and the `agentwatch-daemon` (owner-only socket,
  newline-delimited JSON, JSONL sink) with F2 `hook-error` recording and conformance fixtures.
- `agentwatch.records` (M2): the record + security-event model and strict, reject-never-coerce
  `validate_record()` / `validate_event()` with unknown-version rejection (F8); valid/invalid fixtures and
  a JSON-Schema contract test against `schema/`.
- `agentwatch` CLI (argparse): `status` implemented; `replay`, `export`, `verify-store`, and `migrate`
  wired and failing closed until their milestones (WBS M1).
- Operator configuration loader `agentwatch.configuration` (PRD 16): system < user < project < env < CLI
  precedence, strict unknown-key rejection, and fail-closed export rules (WBS M1).
- `agentwatch` console script, `tomli` backport for Python 3.10, and `python -m build` wheel + sdist
  configuration; `@agentsec-ecosystem/cli` npx launcher (`packages/cli/`) (WBS M1).
- Real CI workflow (ruff, `mypy --strict`, pytest with coverage ≥95% on Python 3.10 and 3.12) (WBS M1).
- Imported the `agent-exec-trace` codebase (MIT, commit `008e1c7`) — `packages/`, `services/`, `apps/`,
  `deploy/`, `examples/`, `scripts/`, and build tooling (WBS M0).
- Complete v0.1.0 documentation set: PRDs 00–14, design (decisions, record format, storage, adapter,
  threat model, privacy, OTel mapping, data dictionary, a11y), reference (API, SDK, adapter conformance,
  compatibility, limitations, detector catalog, record-format spec), machine-readable `schema/`, plans
  (execution, testing & parity), release/migration, runbooks, tutorials, ADRs.
- Governance/DCO/OpenSSF Scorecard automation.
- Shadow-agent + MCP-server inventory (M9, R9): `agentwatch inventory [--session-id] [--project] [--json]`
  aggregates recorded agents and MCP servers; the Claude Code adapter splits `mcp__<server>__<tool>`
  into `ToolCall.server`/`name` (defensive, plugin-scoped-safe).
- Capture fidelity (M9): records carry optional `project` (event cwd) and `parent_session_id`; the hook
  records a metadata-only `prompt_version` digest of `CLAUDE.md` + `.claude/rules/*.md`; `replay` follows
  the parent chain; `sessions`/`search`/`tail` accept `--project`.
- Retention & erasure (M9, R11): `agentwatch retention apply` runs a tombstoning pass on demand and reports
  the chain status; `agentwatch purge <id> --yes [--reason]` tombstones one session (chain links preserved)
  and writes a metadata-only `session-purge` marker — never a hard delete.
- Published plumbing contract (M10 #79/#203): `agentwatch.protocol` pins the store envelope, tombstone,
  and daemon frames; reference specs `store-format.md`, `daemon-protocol.md`, and `adapter-api.md` describe
  them. `conformance.assert_packs_populated()` requires every registered adapter to ship a conformance
  pack; a sample out-of-tree adapter (`tests/community_adapter.py`) proves the plugin contract is usable.
- Provisional harness adapters (M10 #80–#82): modeled **Cursor**, **Codex CLI**, and **Gemini CLI** adapters
  (shared `agentwatch.adapters.modeled` helper), registered in the conformance runner with fixture packs.
  Shapes are assumed, not captured — replace the fixtures with real captures (M14/N4).
- MCP interposition proxy (M10 N1 #83/#212): `agentwatch.adapters.mcp_proxy` normalizes MCP `tools/call`
  request/response frames with `tool.server` attribution, and the `agentwatch-mcp-proxy` console script /
  `agentwatch mcp-proxy` stdio relay records both directions through the daemon (new `phase: "mcp"`),
  reusing redaction, secret detection, dedup, and the hash chain (Plan A, stdio). MCP
  `resources`/`prompts`/`sampling` are relayed but declared gaps.
- MCP HTTP/SSE interposition + config install (M10 N1 #212, Plan B): `agentwatch mcp-proxy --http
  --route NAME=URL ...` serves a loopback `ThreadingHTTPServer` that forwards HTTP/SSE MCP traffic
  unchanged and records `tools/call` both directions (SSE `data:` frames included); hop-by-hop headers
  are dropped, `Host` rewritten, and `Authorization` preserved. `agentwatch init --mcp-proxy
  [--mcp-scope project|user] [--mcp-servers A,B] [--mcp-port N]` re-points `.mcp.json`/`~/.claude.json`
  at the proxy consent-first (stdio servers wrapped, HTTP/SSE servers pointed at the loopback route),
  preserving unrelated keys and backing up the exact original bytes; `agentwatch uninstall` restores the
  config byte-identically (hash-guarded, fail-closed) and stops the long-lived proxy (occupied port fails
  closed). MCP resources/prompts/sampling remain relayed-not-recorded gaps.
- Tier-2 framework adapters (M10 10.6 #84): provisional **modeled** CrewAI and PydanticAI record adapters
  (`agentwatch.adapters.crewai`, `agentwatch.adapters.pydantic_ai`) with conformance packs; shapes are
  assumed, not captured (replace at M14/N4). The in-process PydanticAI instrumentation wrapper remains
  `agentwatch.pydantic`.
- OTel/NDJSON ingestion (M10 N2 #213): `agentwatch ingest <path> --format otel|ndjson` transcodes foreign
  GenAI spans (OTLP JSON or newline-delimited JSON) into validated, redacted, hash-chained records; foreign
  secrets are masked before storage and unmappable spans/JSON are quarantined with a reason (D-Q: a
  transcoder, not a general OTel backend).
- Fake-harness emitters (M10 N3 #214): deterministic per-platform test utilities (`tests/fake_harness.py`)
  producing realistic, out-of-order, duplicate, malformed, and clock-skew streams for daemon/pipeline soak.
- Generated compatibility table + version matrix (M10 N4 #215): `agentwatch.compatibility` is the source of
  truth for tested harness ranges; `scripts/generate_compatibility.py` renders the table into
  `docs/reference/compatibility.md` and fingerprints version-tagged fixtures, and
  `scripts/check_harness_drift.py` + `.github/workflows/harness-drift.yml` open an issue nightly on a shape
  change (never applied silently).

- Fleet aggregation (M11 R13, #87/#88): a `host` record tag (additive) and `agentwatch.fleet`
  (`agentwatch fleet ingest HOST=PATH …` / `fleet show`) — opt-in, self-hosted, local-first multi-host
  ingestion (idempotent, chain-preserving) and host/agent/version rollups. No egress.
- Trailing-baseline drift signals (M11 #89/#90): `agentwatch.drift` + `agentwatch drift --metric M
  [--bucket session|hour] [--window N] [--z-threshold Z] [--emit] [--deploys FILE]` detects deviations
  against a rolling mean/stdev of **prior** samples (never a fixed threshold), emits a new
  `drift-detected` security event (additive event type), and correlates deployment markers to shifts.
  Signals are observations only — the CLI exits `0` (PRD 14/30).

- Resilience & hardening (M12, PRD 13/17/21/22/28): least-privilege file posture (`agentwatch.posture`,
  store dir `0700`, files `0600`), **adaptive durability** (`store.durability`: `record`/`checkpoint`/`none`,
  surfaced in `/healthz`), **chain checkpoints** (`store.checkpoint_every`, `checkpoint()`), **continuous
  chain verification** (daemon sweep flips health on a mid-session tamper), and **`verify-store --repair
  --yes`** (rebuilds from the intact prefix with byte-identical corrupt-file evidence).
- Fault handling (M12, PRD 17): **clock-skew flagging** (F9, future-dated events degrade health with an
  evidence gap), **bounded rotated daemon logs** (`agentwatch.rotating_log`, 5 MB × 2), and **optional
  service supervision** (`agentwatch init --service`, launchd/systemd user units; removed on `uninstall`).
- Verification suites (M12): perf harness `agentwatch.perf` + NFR-1 budget test, sizing tests, consolidated
  **fault-injection F1–F10**, i18n/UTC baseline, and a dependency **egress audit**
  (`scripts/dependency_egress_audit.py`) with offline (`offline-e2e.yml`) and nightly **soak** (`soak.yml`,
  `agentwatch.soak`, `scripts/soak.py`) CI jobs.
- Engineering rigor (M14 Q1 #218): **property-based + differential redaction testing**
  (`tests/test_redaction_properties.py`) — Hypothesis strategies build secret-shaped strings under channel
  mutation and assert no plaintext survives; `tests/_secret_oracle.py` pins gitleaks/detect-secrets rule
  classes as an independent oracle, and a rule class agentwatch misses must be declared in `EXPECTED_GAPS`,
  so a new miss fails CI. `hypothesis` is a dev-only dependency (PRD 38 / NFR-5).
- Engineering rigor (M14 Q2 #219): **mutation gate on the trust path** (`scripts/mutation_gate.py`,
  `.github/workflows/mutation.yml`) mutates the chain verifier, redaction double-gate/truncation, secret
  masking, and strict record validation, and fails when any mutant survives the focused suite. Budget +
  allow-list + `--self-test` prove the gate fails on a survivor. `cosmic-ray` is an optional
  `[mutation]` extra for deep non-gating runs.
- Engineering rigor (M14 Q3 #220): **parser fuzzing** (`tests/test_fuzz_parsers.py`, nightly
  `.github/workflows/fuzz.yml`) covers hook JSON, daemon socket frames, store lines, transcripts,
  NDJSON/OTel ingest, and MCP JSON-RPC; malformed input is contained, never a crash. Fuzzing found and
  fixed a `TypeError` in `session_export.parse_ndjson` on a JSON scalar (`"0"` is now a regression seed).
- Engineering rigor (M14 Q4 #221): **performance gate** (`scripts/perf_gate.py`,
  `.github/workflows/perf.yml`) enforces NFR-1 (p99 ≤ 5 ms/step) plus a committed-baseline drift band
  (3.0× above a 2.0 ms floor) for `normalize`, `redaction`, and `daemon_handle_message`, and generates the
  published numbers in `docs/reference/performance.md` from the run. `--self-test` proves a slowdown fails.
- CI runs the whole repo (M14 Q5 #222): web type-check + unit + **axe** (`.github/workflows/web.yml`),
  Playwright **E2E against the compose stack** (`.github/workflows/e2e.yml`), a compose **stack smoke**
  (`.github/workflows/stack-smoke.yml`), alongside the no-network E2E and nightly soak. Shared runner
  scripts (`scripts/run-e2e.sh`, `scripts/stack-smoke.sh`) and `make web-*` / `make e2e` targets; required
  vs informational jobs documented in `docs/development.md`.
- Engineering rigor (M14 Q6 #223): **published store/chain conformance vectors** in `schema/vectors/store/`
  (valid, tampered, tombstoned, purged, gap, checkpoint, unsupported-format) with a machine-readable
  `expected-verdicts.json`. Two independent implementations — `RecordStore.verify()` and the standalone,
  dependency-free `schema/vectors/verify_store.py` — are checked against the same table in CI; a
  divergence is a contract bug. Generated by `scripts/generate_store_vectors.py`.
- Engineering rigor (M14 Q7 #224): **forward-compatibility matrix** — frozen stores per released format
  version plus the pre-marker legacy shape (`packages/python-sdk/tests/fixtures/store-versions/`,
  `manifest.json`). CI asserts every supported store reads, verifies, replays, and exports; an unknown
  `format` fails closed (`tests/test_forward_compat.py`). Grows per release; removed only at a major.
- Engineering rigor (M14 Q8 #225): **one machine-readable error contract** — every CLI failure emits one
  envelope `{"error": {"code","message","hint","doc_url"}}` on stderr (`agentwatch.errors`). Exit statuses
  derive from the code catalog, and the table in `docs/reference/errors.md` is generated from it (checked
  in CI). `tests/test_error_contract.py` asserts every subcommand's failure path emits an envelope.
- Engineering rigor (M14 Q9 #226): **claims ledger** — `docs/release/claims-ledger.json` traces every public
  claim to live evidence (exact wording, source, test/file/script links, last verified). `scripts/check_claims`
  fails a claim with no evidence, a renamed test (checked by AST), or a deleted file, and the published
  table in `docs/release/claims-ledger.md` is generated from the ledger. Wired in `.github/workflows/claims.yml`.
- Engineering rigor (M14 Q10 #227): **executable documentation** — the J3 investigation cookbook's
  `run`-annotated blocks execute offline against the synthetic seed dataset via `scripts/check_docs_commands.py`
  (CI: `.github/workflows/docs.yml`); a broken command fails the build. Illustrative blocks and
  service-bound tutorials stay unexecuted (compose-covered by Q5, or link-checked).
- Accessibility (M14 Q11 #228): **stated WCAG 2.2 Level AA** in `docs/reference/accessibility.md` with a
  VPAT-lite per view. The unit axe suite runs on every PR; a new Playwright axe run checks contrast in a
  real browser and adds a **keyboard-only journey** through the operator UI (`apps/web/tests/e2e/a11y.spec.ts`).
  The contrast check surfaced and drove fixes for muted-text contrast and a heading-order issue.
- Time correctness (M14 Q12 #229): **UTC store/compare + explicit-offset local rendering**, stated in
  `docs/reference/time.md` and property-tested in `tests/test_time_properties.py` across DST boundaries
  and a non-UTC zone (since parsing, hour bucketing, retention). Fixed naive/`Z` `--since` handling: a
  naive ISO value is now interpreted locally and returned aware (no naive/aware comparison), and `Z`
  works on Python 3.10; `tail`/`view` render `HH:MM:SS+HHMM`.
- Supply chain (M14 Q13 #230): the release pipeline now **signs what it ships** —
  `.github/workflows/release.yml` builds, writes a CycloneDX SBOM + checksums, signs them with **keyless
  Sigstore/cosign**, generates **GitHub-native build provenance** (attestation), and refuses to publish unless
  **`agentwatch verify-release`** confirms the artifacts (checksums + SBOM + signature). Every GitHub Action
  is pinned by commit SHA; the build toolchain is hash-pinned (`scripts/release/requirements-build.txt`).

- Replay-as-code (M13 J2 #204): `agentwatch export-session <id> --format ndjson [--output FILE]` exports a
  session's records with their chain envelope (`seq`/`prev_hash`/`hash`); `agentwatch.session_export`
  round-trips through a reference consumer (`verify_export`) for agentdrill/CI.
- Release + compliance (M13): release tooling (`scripts/release/generate_sbom.py` CycloneDX SBOM,
  `checksums.py`, `.github/workflows/release.yml` with Sigstore provenance), an executable **A1–A6 parity
  gate** (`scripts/check_parity.py`), the OWASP LLM / NIST AI RMF+SSDF / ISO 42001 / SOC 2 / OpenSSF
  [compliance matrix](docs/release/v0.1.0/compliance-matrix.md), versioning/backwards-compat
  validation, first-run evidence, a self-audit, and a partial field-test report. A1 `approval_span` added
  (`SPAN_KIND_APPROVAL`). `v0.1.0` tagging and predecessor-repo privacy remain maintainer actions.

### Fixed
- Operator UI accessibility (#63): corrected heading order (h1 skipped to h3 on Dashboard and
  Version Compare) and associated the Version Compare input labels; now guarded by automated
  axe checks for all five views in `apps/web/src/__tests__/a11y.test.tsx`.

### Changed
- `AGENTWATCH_SOCKET` (the daemon socket selector from the hook contract) is now a reserved environment
  variable and is no longer parsed as a configuration key.
- Porting policy: `agent-exec-trace` is **retained and made private** at v0.1.0 instead of being deleted —
  no repositories are deleted (WBS M13/M15 predecessor retention).
- Release readiness (M24): added a reproducible first-party security scan (`make security-scan`; gitleaks +
  trufflehog + pip-audit + egress, wired into CI) and a local release dry-run (`make release-dry-run`:
  build + SBOM + checksums + `verify-release`). SBOM components now carry resolved versions, and a guard
  test enforces one version across the SDK, CLI, and CHANGELOG.

## [0.1.0] - 2026-10-04

### Added
- Initial release: Claude Code recording, OTel GenAI export, security-event schema, redaction-by-default,
  local-first hash-chained store, session replay (R1–R8).

[Unreleased]: https://github.com/agentsec-ecosystem/agentwatch/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/agentsec-ecosystem/agentwatch/releases/tag/v0.1.0
