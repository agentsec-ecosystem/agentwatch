# Changelog

All notable changes to agentwatch are documented here. Format: [Keep a Changelog](https://keepachangelog.com/),
versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- v0.2.0 M30 (Expanded II — Code, Capabilities, Console & Investigation):
  - LUI-1: `agentwatch ui` read-only loopback console — one command serves the chain store over a stdlib HTTP
    server with **no Docker**: loopback-only bind, per-launch token, Host-header (DNS-rebinding) check, no
    mutation endpoint, no egress; sessions → timeline → record detail with impact/cost/coverage/oversight and a
    read-only session export; chain gaps/tombstones rendered; UI numbers equal CLI `--json` (ADR-0036) (#465).
  - UI-1: live timeline + live anomaly inbox + streaming tail in the console — consumes the M26 STR-2
    store-truth tail (`LiveTail`): back-fills on (re)connect, classifies and renders gaps
    (`stream-drop`/`purged`/`missing`/`rotated`), keeps a backpressured subscriber visible as `degraded`, and
    serves Server-Sent Events over the token-gated loopback routes `/api/live/*` (#428).
  - LUI-2: embedded, rebuildable query index — `agentwatch.query_index` projects the hash-chained store into a
    stdlib `sqlite3` index (no heavyweight runtime dependency; ADR-0035); deleting it loses nothing and it
    rebuilds **bit-for-bit** from the chain; indexed lookup on a 1M-record store is ~2 ms (target < 250 ms);
    `agentwatch index rebuild|status|drop|export-parquet` (parquet is a lazy optional extra) (#466).
  - EXT-5: `purge`/retention propagate to every derived index/export — a successful purge/retention drops the
    erased rows from the embedded index (and next use rebuilds it from the now-tombstoned chain) so the index and
    console return nothing for the session; a hold still fails the purge closed; known leftover artifacts
    (archives, parquet/NDJSON exports, repair-evidence copies, quarantine) are enumerated (#483).
  - EXT-8: Postgres re-sequenced behind the embedded index — the embedded, rebuildable index is the general-case
    query tier and Postgres is the fleet / multi-tenant tier (PG-2); the decision is folded into ADR-0035 and
    recorded in `design/derived-postgres.md` (no separate ADR) (#484).
  - AGI-1: read-only MCP server over the record — `agentwatch mcp-serve --enable` (off by default) exposes a
    fixed, test-enumerated read-only tool set (`sessions`, `search`, `replay`, `impact`, `blame`, `coverage`,
    `cost`, `oversight`, `provenance`, `inventory`) over local stdio; responses are labeled `untrusted-data`
    with record citations, results are bounded and rate-limited, injection-shaped record content cannot change
    behavior, and every query is appended as a metadata-only `store-access` record (ADR-0037) (#467).
  - AGI-2: investigation skill + versioned CLI JSON schemas — `docs/skills/investigation/SKILL.md` teaches the
    search → replay → impact → evidence workflow, and the read/investigation commands' `--json` output is
    published as versioned schemas in `schema/cli/v0.1.0/` (own changelog, guarded by `agentwatch.cli_schema`);
    a scripted agent reaches documented answers on the demo store (#468).
  - POL-1: advisory `suggest-policy` + dangerous-broad lint — `agentwatch suggest-policy --since 30d --target
    claude-settings|mcp-allowlist|acs` derives least-privilege allow/ask/deny candidates from observed calls
    and cls1 classes, links each rule to evidence (calls/sessions/approvals/last-seen), never suggests
    destructive/network/credential-adjacent calls as `allow` by default, lints broad interpreter/network
    rules, writes nothing outside `--out`, and is deterministic (ADR-0038) (#469).
  - POL-2: `what-if` policy replay over history — `agentwatch what-if <policy-file> --since 30d` reports
    allowed/asked/denied counts and the delta vs actual behavior (prompts avoided, would-be denials with
    sessions, actual-authorization differences), with explicit parse errors, reported unsupported syntax, and
    a simulation label stamped with the policy-format version (ADR-0038) (#470).
  - OUT-2: recurring failure signatures in `digest` — failed calls/anomalies are grouped by a versioned signature
    (`sg1`: tool, error class, `cls1` class, `bd1` behavior fingerprint) into ranked top-N patterns with counts,
    first/last seen, trend vs the prior equal-length window, and `replay`/`diff` evidence links; same store → same
    output, unknowns preserved, no score. Console rendering is deferred to 30.LUI-1 (#478).
  - EXT-4: `cls2` — a published, versioned table of test/build/lint outcome classes (`outcome:test`/`build`/`lint`
    × `pass`/`fail`/`unknown`) added alongside the frozen `cls1` impact classifier; `classify_outcome` /
    `classify_record_outcome` read an explicit exit code else the record outcome, unknown stays unknown, and
    `cls1` outputs are unchanged and reproducible (#482).
  - DEMO-1: a static, synthetic `examples/demo-bundle/` (replay/impact/oversight/provenance) linked from the README
    and GTM — opens offline with zero network requests, is synthetic (`producer.kind: demo`) and clean under two
    independent secret scanners. The VFY-1 browser rendering is deferred (#480).
  - NTF-1: three CI-tested alert-routing recipes (`deploy/recipes/`: Slack incoming webhook, PagerDuty Events API
    v2, Alertmanager v2) that map agentwatch security events to each stack's payload and post them through the
    shipped `agentwatch.sinks.WebhookSink`. agentwatch defines no rules or thresholds — routing stays in the
    user's stack, and every event is forwarded (#481).
  - PRV-3: content-free range+hash capture (`agentwatch.provenance.capture_ranges`, ADR-0033) — per file-modifying
    call, the affected line range(s) and a keyed content hash, **never content or a diff**; the fact is metadata so it
    holds under `metadata-only`, and a harness that exposes no range falls back to file-level `heuristic`. Shape
    versioned (`RANGE_CAPTURE_VERSION`); guarded by `is_content_free` and a property + attack pack (#464).
  - PRV-1: `agentwatch provenance <commit|range|PR|file>` (`agentwatch.provenance.build_provenance`) — joins git
    facts to the recorded sessions that produced them, per range confidence `exact|heuristic|mixed|ambiguous|unknown`,
    contributing sessions with harness/model, authorization mix, cost, anomalies, coverage, and an evidence pointer; a
    commit with no recorded session says "no recorded agent activity" (never "human"); PR resolution is offline; the
    repo is read-only (#462).
  - PRV-2: Agent Trace export + git-ai notes cross-validation (`agentwatch.agent_trace`, ADR-0034) —
    `export-session --format agent-trace` emits a pinned-revision bundle (ranges/hashes/ids only, **zero code
    content**); a read-only reader cross-validates existing notes as agree/disagree/agentwatch-only/notes-only
    (`provenance --notes`); writing git notes requires the explicit `--write-notes` command; a pinned-revision drift
    check + CI job (AAT-5 pattern) (#463).
  - CNC-1: `agentwatch concurrency --project . --since 7d` (`agentwatch.concurrency.build_concurrency`) — a
    deterministic, evidence-only report of sessions overlapping in time on the same path and shared-file edits from a
    two-session fixture; `provenance` marks a range covered by two or more sessions `ambiguous` instead of silently
    picking one (#474).
  - OUT-1: deterministic outcome facts + `cost --per retained-change` (`agentwatch.outcomes`, derivation `out1`) —
    `agentwatch outcomes --since 30d --by project|model|harness` reports test/build/lint pass ratios and
    retained/reverted/interrupted/rejected counts with numerator/denominator and a derivation version (unknown stays
    unknown); `cost --per retained-change` is source-stamped and joins PRV-1; no LLM, no network, runs offline (#477).
  - CAP-1: capability inventory (`agentwatch.capabilities`) — Claude Code skills, plugins, hooks, subagents,
    slash commands, rules files and MCP servers are inventoried by **`sha256` content digest** (never the
    declared pin), with origin scope (`managed`/`user`/`project`/`plugin`), size and optional declared version;
    content is never retained (property-tested); `inventory --capabilities [--json]` lists them and
    `bom --format cyclonedx` includes them as components; per-harness coverage (`exposed`/`partial`/`none`) is
    declared honestly — Claude Code exposed, Cursor/Codex CLI/Gemini CLI (and memory, MEM-1) `none` gaps (#458).
  - CAP-2: capability drift — a per-session metadata-only `capability-snapshot` carrier is diffed across sessions and
    raises the reused `capability-changed` event (M29 EXT-3) with a factual class (`added` / `removed` /
    `content changed, version unchanged` — the Plugin4Shell shape / `content changed, version changed`);
    `inventory --capabilities --snapshot` records and `inventory --capabilities --diff --since 7d` lists the drift,
    never a verdict (#459).
  - CAP-3: `capability-loaded` attribution — a metadata-only load step (name/kind/scope/digest) is shown inline by
    `replay` ("followed the load of …"), listed by `impact`, and selectable with `search --capability <name>`
    (the load plus calls recorded after it, never other sessions); a per-harness load-exposure matrix is published
    and CI-checked. Context wording only — never "caused by" (#460).
  - MEM-1: memory stores as capabilities — `~/.claude/memory` / `<project>/.claude/memory` are inventoried with
    digest/size/last-changed (content never retained), shown by `inventory --capabilities` and `inventory --memory`,
    and diffed with writer-session attribution: a change no recorded session wrote is flagged `unattributed`
    (out-of-band edit); `search --memory-store <name>` returns the write plus calls after it; a per-harness
    memory-exposure matrix is published and CI-checked (#461).
  - ENV-1: environment fingerprint + delta — each session derives a content-free `env1:<sha256>` fingerprint
    (model, harness, permission mode, capability/rules/MCP-surface digests, recorder config digest; absent facts
    `unknown`); `diff` prints the environment delta above the behavior delta (model first), `sessions --group-by-env`
    groups by it, and `drift` annotates a signal with same-window environment changes under `environment_coincides`
    with "coincides with" wording, never "caused by" (#472).
  - SBX-1: sandbox-boundary events — signal availability was verified per harness first: Claude Code's OTel
    vocabulary exposes none, Cursor's raw shell hook carries `sandbox` (adapter capture is a follow-up), so the
    matrix is declared honestly. An additive nullable `sandbox` field on records and the `sandbox-boundary`
    security event (OCSF-mapped) carry metadata only; a missing signal stays `unknown` (never unsandboxed).
    `oversight` reports `% calls unsandboxed` + denials by class and `impact` keeps attempted-but-blocked network
    destinations apart from contacted ones (#476).
  - IR-1: incident cases — `agentwatch case create/add/remove/list/show/export/verify` groups sessions across
    hosts/days as metadata-only **chain records**, merges their records into one timeline that states its
    ordering rule and classifies gaps (`recording-gap`/`time-gap`/`purge`/`tombstone`/`unreadable`), and
    exports a self-contained case bundle (`case.json`, `records.ndjson`, COR-3-shaped
    `incident-report.json`) that re-verifies offline (member hashes **and** the chain segment) with no
    registry egress (#473).
  - VFY-1: offline browser evidence verifier — a single, self-contained
    `docs/release/verifier/agentwatch-verify.html` opens from `file://` with **zero network requests** and
    re-verifies an evidence bundle (member hashes, the hash-chain segment, completeness, leak-scan, and
    attestation) with the CLI's verdict wording, naming the first broken link of a tampered bundle; a
    differential test asserts identical verdicts to `agentwatch evidence verify`, `scripts/build_browser_verifier.py`
    checksums (and can sign) the artifact, and ADR-0044 records the trust model (#475).
  - RUN-1: sealed runner segments — `agentwatch segment export/verify/custody` and `agentwatch import-segment`
    seal an ephemeral/CI run into a self-verifying segment (its **own** hash chain from genesis, runner identity,
    start/end attestation), verify it offline, and anchor it locally as a `source: runner` chain-of-custody
    record; imported records are chain-protected but **NOT locally witnessed** (S11 distinction, visible in
    `segment custody`), sealing/import refuse unredacted records, a `traceparent` joins the originating session,
    a tampered segment fails and is not imported, and agentwatch performs no egress; ADR-0039 (#479).
  - RED-1: public redaction corpus + `redact eval` — a versioned, synthetic corpus
    (`schema/vectors/redaction/v1/`) drives `agentwatch redact eval --corpus v1` to publish per-class recall and a
    false-positive rate, reproduced deterministically offline; the committed numbers/table cannot drift
    (`docs/reference/redaction-corpus-numbers.json`); the one honest miss (base64-encoded API keys) is declared in
    known-limitations; the corpus is allowlisted for the first-party secret scan (#471).
- v0.2.0 M29 (Expanded I — Trust, Identity & Governance):
  - DEP-1: managed-policy install posture + honest `doctor` — `agentwatch.managed_policy` reads the effective
    managed settings (`allowManagedHooksOnly`, `strictPluginOnlyCustomization`) and `doctor` reports
    `hooks effective: yes | blocked by managed policy | unknown`, never "installed" when policy blocks the
    recorder; `init` warns that a user/project install will be inert and `managed_install_artifacts` generates
    the inert managed hook / org-plugin / MDM artifacts. Detect, never circumvent (#441).
  - DEP-2: session-start recorder attestation + `recorder-config-changed` — a chain-recorded
    `recorder-attested` fact (effective hook sources, a keyed config digest, managed-policy status, permission
    mode) is appended on the daemon `session-start` hook and at `init`; a digest change raises
    `recorder-config-changed`; `coverage`/`evidence` carry `attestation: present|absent`; digests/booleans only
    (#442).
  - DEP-3: end-to-end hook wall-clock per OS + budget + CI gate — `agentwatch.hook_perf` measures the real
    `agentwatch-hook pre` process-spawn cost against a draining socket; `scripts/hook_perf_gate.py`
    (`.github/workflows/hook-perf.yml`) gates macOS/Linux against a committed per-OS baseline and publishes the
    table plus a 500-call session overhead in `reference/performance.md`; Windows is reported blocked on WIN-1
    (#443).
  - EXT-3: security-event schema gains `recorder-config-changed` (DEP-2), `mode-transition` (APV-2/WS-A), and
    the forward-compatible `capability-changed` placeholder (M30 CAP-2, not built) — with OCSF/CloudEvents
    mappings, fixtures, and the schema changelog (#453).
  - EXT-7: the compatibility matrix gains a **Managed policy** column (`effective`/`blocked`/`unknown`/`n/a`)
    and framework rows (ADK / Strands / OpenAI Agents SDK / Claude Agent SDK) as a generator input WS-D (FWK-1)
    will populate; the generated block and drill note are updated (#454).
  - SYS-1: opt-in Linux system-effects ingest (`agentwatch.system_ingest`) — AgentSight/Tracee-shaped
    process-exec/network-connect events are joined to sessions by process lineage/time-window (±300 s), every
    record is labeled `source: system-ingest`, an unowned/ambiguous/out-of-window lineage is filed under
    `unjoined:system-ingest` (never guessed), `classify`/`impact` extend to syscall truth, and the
    synthetic-corpus false-join precision is published (1.00/1.00); `ingest --format system-ingest --consent`;
    no probes built; macOS/Windows declared not-covered (#366).
  - ACS-1: ACS Guardian audit-trail ingest (`agentwatch.acs`) — a Guardian's ACS v0.1.0 JSON-RPC decisions map
    to `denied`/`policy-fired` with AAT `record_phase: pre_execution`; monitor-only (a decision is never
    executed), the revision is pinned with a drift check (AAT-5 pattern), and an unknown revision/method/
    decision is quarantined; `ingest --format acs`; the emit-side spike is deferred (#367).
- v0.2.0 Trust, Identity & Governance (M29):
  - APV-1: authorization provenance v2 (`authz-v2`, PRD 49) — an additive metadata-only `authorization`
    object (`source`/`deny`/`evidence`) on records, with the legacy S14 five-value `approval` mapped at read
    time by `effective_authorization` and never written back; a classifier-approved call is `classifier` and
    a bypass-mode call is `bypass`, and `unknown` is never inferred from `outcome=ok` (#438).
  - APV-2: permission mode is a first-class, time-varying fact — an additive `permission_mode` on every
    call plus `permission-mode-changed` transition observations; `search --mode bypass` works, a
    default→bypass→default session reconstructs, `impact` flags the bypass interval, and a missing mode is
    `unknown` counted in `coverage` (#439).
  - APV-3: the `agentwatch oversight` report — authorization mix (shares with denominators), sessions
    by start/end mode, human-prompt approve/reject + time-to-decision (latency only with paired
    timestamps, else "n/a (n calls)"), and a cls1 destructive/network/credential-adjacent ×
    authorization cross-tab; deterministic, offline, version-stamped; surfaced in `digest` and the
    compliance report as `eu-ai-act-art14` (Art. 14 / ASI09) (#440).
  - CCO-1: Claude Code native OTel ingest (`ingest --format claude-otel`) maps `tool_decision`
    (`decision_source`), `permission_mode_changed`, `api_request`/`tool_result` (exact vendor cost) and
    `user_prompt`/`mcp_server_connection`; joins to hook records by `tool_use_id` with disagreements recorded
    as classified discrepancies; `coverage` reports "N joined, M hook-only, K otel-only, D discrepancies
    (classified)"; redaction runs on ingest and unmappable input is quarantined (B4) (#444).
  - CCO-2: the Claude Agent SDK / headless runs land through the same native path as
    `source: sdk-native` (producer `kind=sdk`) with identity from resource attributes; a CI-executed
    gallery recipe (`examples/claude_agent_sdk_otel.py`) and a framework-matrix row (#445).
- v0.2.0 Expanded I — Trust, Identity & Governance (M29):
  - ACC-1: a documented, enforceable fleet **role × data-class** read-access model
    (`agentwatch.access`) — roles `self` / `team-reviewer` / `security-auditor` / `admin`
    against `metadata` / `identity-hashed` / `identity-resolved` / `content` / `evidence`.
    A cross-role read returns nothing and is appended as a `store-access` record; the owner
    sees who read their records via `agentwatch access log --owner ID`; identity resolution
    is an explicit, recorded action; the default fleet profile is least-privileged
    (metadata-only, hashed identity). `agentwatch access check`/`matrix` publish the model.
    ADR-0040 (#448).
  - ACC-2: `agentwatch governance notice` renders what is recorded/not, who can see it,
    retention, and erasure **from the live effective config**; every statement maps to a
    config key or documented guarantee and unbackable claims are omitted and listed as
    refused ("not legal advice" banner). A DPIA starter (`docs/compliance/dpia-starter.md`)
    carries the counsel-review banner and embeds the notice command (#449).
  - HLD-1: legal holds suspend retention and purge. `agentwatch hold add/list/release`
    places a hold on a session/project/time/principal scope; while active, retention
    **skips** held records (`retention apply --dry-run` lists them + hold IDs) and `purge`
    **fails closed** with the hold ref. An explicit `--override-reason` records a
    session-scoped override that is conspicuous in an evidence bundle and the compliance
    report's retention row (`holds`/`overrides`). Holds/releases/refusals/overrides are
    hash-chain records; D-K tombstones are preserved. Derived-index propagation is
    declared blocked on 30.EXT-5. ADR-0041 (#450).
- v0.2.0 Expanded I (M29):
  - FWK-1: certified framework recipes (Google ADK, Strands Agents, OpenAI Agents SDK via
    OpenInference, Claude Agent SDK) route native/community OTel into the **shared**
    `agentwatch ingest --format otel` path. `agentwatch.ingest` now maps OTel GenAI **and**
    OpenInference attributes with an explicit, sorted `unmapped` bucket (also surfaced on
    `IngestStats.unmapped`), takes run identity from resource attributes, and stamps the
    ingestion `source` on the record's `producer`. Recipes are pinned, held to O1 conformance
    packs, and carry a `modeled` compatibility-matrix row; the frameworks are not installable
    in the CI sandbox so the live run is **BLOCKED** (never faked). New:
    `agentwatch/frameworks.py`, `docs/reference/framework-recipes.md`,
    `examples/framework_recipes.py`, `scripts/check_framework_drift.py` +
    `.github/workflows/framework-drift.yml` (#446).
  - FWK-2: `agentwatch.instrument()` auto-detect — one call detects installed supported
    frameworks, wires their OTel to the local collector (standard OTLP env + the OpenInference
    instrumentor for the OpenAI Agents SDK), takes identity from the environment, and prints what
    it instrumented **and what it could not** (no silent partial instrumentation). No-op safe when
    the recorder is not running, single flush-on-exit, idempotent (no double spans).
    `agentwatch/instrument` is a callable module; the implementation is `agentwatch.autoinstrument`
    (#447).
- v0.2.0 Expanded I (M29):
  - ASI-1: `compliance report --framework owasp-asi-2026` renders a coverage map with one row per OWASP Top 10
    for Agentic Applications 2026 risk (ASI01–ASI10) plus an Agentic Skills Top-10 (AST01–AST10) section. Each row
    states what the record evidences, the regenerating command (or `not evidenced`, naming the owning dependency
    29.APV-3/29.A2A-1-2/30.CAP-1-2/30.SBX-1), what it cannot evidence, and a fidelity tier; every evidenced row's
    command runs in the executable-docs gate and nothing claims prevention or certification (#451).
  - STD-1: the standards participation plan is published (`docs/reference/standards-participation.md`) with an
    owner, five target specs (OTel GenAI semconv, IETF AAT, Agent Trace, OCSF, OWASP Agentic), what is proposed
    (event vocabulary, authorization taxonomy v2, `capability-changed`), a quarterly re-pin/engagement cadence, and
    an external-adopter count. **DD-05 is closed by ADR-0045**; each spec has ≥1 contribution tracked in the claims
    ledger as **"submitted"** — never "adopted" (#452).
- v0.2.0 Depth (M28):
  - CMP-4: ed25519 checkpoint signing graduates to a supported posture — `checkpoint rotate` replaces the key
    and records the rotation as a metadata-only `key-rotation` chain event; the posture is folded into
    `verify-store`/evidence/AAT and surfaced in `doctor`/`/healthz`; a key we no longer hold reports "signed by
    key id X, key unavailable" (#361).
  - IDN-4: the credential *class* is exported as `agentwatch.credential_class` and the deterministic
    `credential-hygiene` detector flags a run that acted under a shared/ambient credential (observation, not a
    verdict); AIMS/WIMSE/NCCoE mapping published in `docs/reference/identity-mapping.md` (#363).
  - CMP-3: policy-driven retention profiles — `retention apply --profile high-risk-12mo` (365d, AAT §9) /
    `general-6mo` (180d) / `custom`; the policy change is recorded (S5), `doctor` warns on an unapplied window,
    and the compliance report cites the active profile (#360).
  - GOV-1: the adapter plugin contract is a public semver-guaranteed extension surface
    (`docs/reference/backwards-compatibility-policy.md`); the `agent_exec_trace` → `agentwatch` codemod
    (`scripts/codemod_agent_exec_trace.py`), a `CONTRIBUTING.md`, and ADR-0046..0048 (#369).
  - MIG-1: a v0.1.0 → v0.2.0 migration guide (`docs/release/v0.2.0/migration-guide.md`) and a frozen-store
    upgrade test (#436).
  - DATA-1: the derived Postgres index DDL (`schema/derived-index.sql`) — every table carries `source_seq` /
    `source_hash` back-references to the chain, so the index is derived-only and rebuildable; documented in
    `docs/design/data-dictionary.md` (#435).
  - TSS-1: the TypeScript-SDK decision (ADR-0049) — directionally accepted for v0.3.0, **not shipped** in
    v0.2.0 — with a schema-portability spike (`scripts/generate_ts_types.py` + a round-trip contract test)
    proving the JSON Schema generates usable TS types (#368).
- v0.2.0 Surfaces (M27):
  - WIN-1 (partial): Windows service supervision — `render_unit("win32")` generates a **Task Scheduler XML**
    (logon trigger, least privilege, restart-on-failure) and a `windows-latest` **CI leg**
    (`.github/workflows/windows.yml`) exercises the platform-independent SDK subset; runbook added. Named-pipe
    transport + an end-to-end CUJ-1 Windows timing run are declared unverified here (#350).
  - CCA-1: `ingest --format claude-compliance` reads an Anthropic Compliance API export **consent-first**
    (refuses without `--consent`), maps the actor email to a hashed principal (IDN-1), records the pull as a
    metadata-only `store-access` record, and classifies feed-vs-hook mismatches as `compliance-discrepancy`
    observations (never silently merged) (#341).
  - LG-1: the LangGraph SDK path registers an **O1 SDK conformance pack** (`conformance.SdkSpec`) — the pack
    drives the real `_NodeCallbackHandler`, exports spans, and transcodes them to records; the runner holds it to
    fixture replay + record validation + replay idempotency, with a negative control (#348).
  - LOG-1: an OpenCode transcript **reader** (`agentwatch ingest --agent opencode`) for the MIT SDK-documented
    storage tree (`session/part/**`: `ToolPart` with `callID`/`tool`/`state.status`/`input`/`output`/`error`),
    paired ACT/OBSERVE records, dangling `running`/`pending` parts flagged, read-only with `producer: import`
    (the `log-read` capture level) (#340).
  - XHT-3: the Codex rollout reader is cross-validated against **two independent, commit-pinned OSS parsers**
    (kvsankar/agent-history Python; kylesnowschwartz/agent-ouija Go) on a golden fixture via
    `scripts/xht3_cross_validate.py` + `.github/workflows/xht3-cross-parser.yml`; a divergence fails the job,
    and both pins/licenses are recorded in `THIRD_PARTY_NOTICES.md` (#352).
  - COD-1: a Codex CLI rollout **reader** (`agentwatch ingest --agent codex`) for `~/.codex/sessions/**`
    `rollout-*.jsonl(.zst)` — pairs `function_call`/`function_call_output` (+ custom/shell/web-search),
    parses the JSON-string arguments, dedups repeated plaintext (F2), marks an unanswered call as an inferred
    `crashed` end-state (S33), and never executes foreign content (ADR-0024). Python 3.14 stdlib `compression.zstd`
    or the new `agentwatch[codex]` extra (#339).
  - DET-4: the 6 LLM-augmented detectors run through the shared offline eval harness (`run_eval(..., llm_client=…)`
    + `create_llm_detectors(client)`), local-model-first and strictly additive; all detectors now run in one event
    loop (an async LLM client is loop-bound). Numbers published in `docs/reference/detector-llm-numbers.json`
    (local `Qwen3.5-9B-MLX-4bit`: `semantic_loop` and `quality_degradation` 1.0/1.0; `output_drift` needs an
    embeddings endpoint). The rule trust path is unchanged (#343).
  - UI-2: an **Operator** console view rendering identity/attribution (IDN-1/S14), SIEM sink health
    (targets + `degraded`), and content-free detector telemetry, backed by read-only endpoints
    `GET /api/v1/attribution`, `/siem-health`, `/detector-telemetry` (openapi + typed client regenerated).
  - A11Y-1: axe coverage for the new Operator view (unit + Playwright incl. contrast) and a keyboard-only
    journey extension; the accessibility reference gains the Operator row (#431, #432).
  - TUT-1: tutorials for recording Cursor, recording Gemini via telemetry, AAT mapping, and cross-harness
    testing (`docs/tutorials/07–10`, indexed) (#434).
  - RUN-1: runbooks for Cursor, Gemini, Codex (reader pending), OCSF/SIEM export, and the MCP full surface
    (`docs/runbooks/`, indexed) (#433).
  - EXA-1: an indexed `examples/` gallery (`examples/README.md`) with CI-executed recipes
    (`security_event_consumer.py`, `ocsf_consumer.py`) and explicitly illustrative ones; the index is enforced by
    `tests/test_examples_gallery.py` (#351).
  - DET-5: opt-in, local-only, content-free detector telemetry (`agentwatch.detector_telemetry`) — fired/
    suppressed/false-positive markers as bounded NDJSON, feedable to a SIEM sink; off by default (#344).
  - SIEM-2: the opt-in Syslog sink is verified — the S10 redaction self-test gate applies, a delivery failure
    surfaces `degraded` with a bounded queue (never a silent drop); `tests/test_siem_syslog.py` (#347).
  - SIEM-1: an OCSF 1.5.0 reference consumer (`examples/ocsf_consumer.py`) with a CI test
    (`tests/test_siem_consumers.py`); events-only, bounded, no store access (#346).
  - COR-2: `agentwatch.incident_taxonomy` maps every security-event type to the AIR schema fields
    (architecture/mechanism/control/agency/outcome) and the AIID GMF taxonomy — each event has a
    correspondent or an explicit `None`; `annotate --incident-tag` stores optional registry tags
    metadata-only (secret-scrubbed) (#345).
  - GEM-2: the Gemini CLI adapter maps native OTel attributes — `active_approval_mode`→approval provenance
    (S14), `user.email`→a hashed on-behalf-of principal (IDN-1), `installation.id`→identity and
    `session.id`→session correlation (#342).
  - MCP-6: `agentwatch.mcp_protocol` is the protocol-revision→surface matrix (2025-06-18 / 2025-11-25 /
    2026-07-28); the proxy's tested range tracks the newest revision (drift fails CI) and the compatibility
    table gains a **Protocol** column (#338).
  - MCP-5: the MCP proxy records the `tasks/*` lifecycle (and task-augmented tool results) with the task id as
    metadata (SEP-2663); Roots/Sampling/Logging are marked **closed-by-spec** (SEP-2577) in known-limitations
    (#337).
  - MCP-4: the MCP proxy records server-issued `elicitation/create` request/response and links the human-input
    answer to approval provenance (S14): `accept`→`user`, `decline`→`denied`, otherwise honest `unknown`
    (#336).
  - MCP-3: the MCP proxy records `prompts/get` request/response; the prompt name is metadata in
    `tool.arguments['name']`. The `mcp-prompts` gap is closed; capability/gap sets and the conformance
    pack move together (#335).
  - MCP-2: the MCP proxy records `resources/read` request/response and every `resource_link` in a tool
    result (`resources/link` observation); the resource URI is metadata in `tool.arguments['uri']` and
    `agentwatch search --mcp-resource <uri>` finds each access. The `mcp-resources` gap is closed; the
    adapter's capability/gap sets and the conformance pack move together (#334).
  - MCP-1: the MCP interposition proxy now speaks **Streamable HTTP** as its default transport
    (`agentwatch mcp-proxy --http --transport streamable-http`); it is **stateless** (sessions removed in
    2026-07-28 — `Mcp-Session-Id` is neither required, forwarded, nor emitted) and relays
    `MCP-Protocol-Version` unchanged. The legacy HTTP/SSE relay is kept verbatim
    (`--transport http-sse`) and marked deprecated-in-spec (#333).
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
