# M4 — Local Store + Redaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden redaction into secret/PII detection and add a local, append-only, hash-chained,
retention-bounded JSONL store that replaces the M3 plain sink, with `verify-store` and an export gate.

**Architecture:** A new `agentwatch.secrets` detects and masks secret/PII classes before anything is
stored. A new `agentwatch.store.RecordStore` wraps each validated `AgentRecord` in a hash-chained JSONL
envelope (`seq`, `prev_hash`, `hash`, `record`), verifies the chain, and tombstones entries past retention.
The daemon writes through the store; the CLI exposes `verify-store`; a self-test corpus gates export.

**Tech Stack:** Python 3.10+, stdlib only (`hashlib`, `json`, `re`, `os`, `datetime`); pytest.

**Spec:** [WBS Part 3 — M4](../wbs/v0.1.0/wbs-v0.1.0-part3-store-export.md),
[storage design](../design/storage-design.md), [redaction rules](../design/redaction-rules.md),
[privacy-mode transforms](../design/privacy-mode-transforms.md),
[PRD 15](../prd/15-data-model.md), [PRD 17](../prd/17-error-handling.md) (F3/F4/F6),
[ADR-0007](../adr/0007-hash-chain.md), [ADR-0008](../adr/0008-jsonl-store.md), [ADR-0009](../adr/0009-export-gating.md).

## Global Constraints

- No new runtime dependency; stdlib only (matches M2/M3 and NFR-5 footprint).
- Fail closed, never coerce: invalid records raise; store-full raises; a broken chain is surfaced
  (`F3`, `F4`, `F8`).
- No network I/O (R6). Redaction happens before storage (DD-06).
- Strict quality gates: `ruff` zero, `mypy --strict` clean, coverage ≥ 95%.
- Conventional, signed-off commits (`git commit -s`).
- **Ruling (R1):** keep the **shipped** transforms in `agentwatch.redact` (truncated `value[:N] + "[...]"`,
  hashed = 64-char salted SHA-256). The draft design's `sha256[:16]`/hash-suffix variant is not adopted for
  v0.1.0 (WBS 4.1 acceptance is "4 modes behave as shipped"). 4.1 adds the missing `FULL` mode only.
- **Ruling (R2):** secret/PII scanning runs on the raw hook event even in `metadata-only` (so
  `secret-detected` fires); storage still follows the mode.
- **Ruling (R3):** the store envelope is `{"seq", "prev_hash", "hash", "record"}` and tombstone entries are
  `{"seq", "prev_hash", "hash", "tombstone": true, "purged_at"}`. Chain verification recomputes `hash` for
  live entries and checks links for tombstones (tombstone payload is a declared, documented gap).

## Review Focus

1. **Non-string / nested secret values** — secrets embedded in dict values, numbers-as-strings, or arrays
   must still redact; a value that is a `dict`/`list` recurses.
2. **Crash mid-append** — a truncated final JSONL line must not make `records()`/`verify()` crash; it is
   surfaced, not silently skipped.
3. **Retention with future/clock-skewed timestamps** — entries with a future `started_at` must not be
   purged and must not corrupt ordering.
4. **Concurrent appends** — two writers to the same store must not interleave a partial line; append is
   serialized with a file lock.
5. **False positives in detection** — benign strings that merely resemble a prefix (`sk-` inside a word,
   `AKIA` without the 16-char body) must not be redacted.

---

### Task 1: Secret/PII detection engine (`4.2`)

**Files:**
- Create: `packages/python-sdk/src/agentwatch/secrets.py`
- Test: `packages/python-sdk/tests/test_secrets.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `SECRET_KINDS: tuple[str, ...]` — kind ids, priority order.
  - `detect(text: str) -> list[SecretMatch]` — `SecretMatch(kind: str, start: int, end: int)`.
  - `redact_secrets(text: str) -> tuple[str, tuple[str, ...]]` — masked text and the kinds found
    (deduped, in `SECRET_KINDS` order).
  - `redact_mapping(value: Any) -> tuple[Any, tuple[str, ...]]` — recursive over dict/list/str.

- [ ] **Step 1: Write failing tests** `tests/test_secrets.py` covering, per the redaction-rules table:
  `sk-`, `ghp_`, `github_pat_`, `AKIA` + 16 chars, `xoxb-`, `AIza`, `Bearer <token>`,
  `-----BEGIN ... PRIVATE KEY-----`, a three-segment JWT, email, E.164 phone, SSN, a Luhn-valid card,
  `postgres://user:pass@host/db`, and a `*_TOKEN`/`*_KEY`/`*_SECRET`/`*_PASSWORD` key name. Assert
  `redact_secrets("token sk-abc123")` → `("token <REDACTED:api-key>", ("api-key",))` and that
  `redact_secrets("sk-")`, `redact_secrets("AKIA short")`, and `redact_secrets("hello world")` return no
  kinds (Review Focus 5). Assert a card fails Luhn when one digit is changed.

- [ ] **Step 2: Run** `pytest tests/test_secrets.py -q` — Expected: FAIL (module missing).

- [ ] **Step 3: Implement `secrets.py`.** One compiled regex per class; `detect` walks matches in priority
  order and returns `SecretMatch` objects; `redact_secrets` replaces each match with `<REDACTED:kind>` and
  returns deduped kinds. Card detection includes a Luhn check.

- [ ] **Step 4: Run** `pytest tests/test_secrets.py -q` — Expected: PASS.

- [ ] **Step 5: Commit** `feat(secrets): secret/PII detection and <REDACTED:kind> (M4)`.

---

### Task 2: Add `FULL` privacy mode (`4.1`)

**Files:**
- Modify: `packages/python-sdk/src/agentwatch/redact.py`
- Modify: `packages/python-sdk/tests/test_redact.py`

**Interfaces:**
- Consumes: existing `RedactionConfig.apply`.
- Produces: `PrivacyMode.FULL = "full"`; `apply(value, allowed=True)` returns `value` unchanged in `FULL`
  mode (upstream secret masking still applies — enforced in Task 3).

- [ ] **Step 1: Write failing test** in `test_redact.py`:
  `test_full_mode_returns_value_unchanged` — `RedactionConfig(mode=PrivacyMode.FULL).apply("raw", allowed=True) == "raw"`;
  and `test_full_mode_still_respects_field_opt_in` — `apply("raw", allowed=False) is None`.

- [ ] **Step 2: Run** `pytest tests/test_redact.py -q` — Expected: FAIL (`PrivacyMode.FULL` missing).

- [ ] **Step 3: Implement** `FULL` in `PrivacyMode` and an early `return value` branch after the
  metadata-only/`allowed` short-circuit.

- [ ] **Step 4: Run** `pytest tests/test_redact.py -q` — Expected: PASS (existing transform tests unchanged).

- [ ] **Step 5: Commit** `feat(redact): add explicit full privacy mode (M4)`.

---

### Task 3: Adapter applies secret masking and emits `secret-detected` (`4.2`)

**Files:**
- Modify: `packages/python-sdk/src/agentwatch/adapters/claude_code.py`
- Modify: `packages/python-sdk/tests/test_claude_code_adapter.py`
- Create: `packages/python-sdk/tests/fixtures/claude-code/secret_args.json`

**Interfaces:**
- Consumes: `secrets.redact_mapping`, `records.SecurityEvent`, `SecurityEventType.SECRET_DETECTED`.
- Produces: `normalize` returns records whose stored `tool.arguments` are secret-masked and which carry a
  `SecurityEvent(type=secret-detected, emitter="agentwatch", tool=<name>, evidence={"kinds": [...]})`
  when any kind is found; detection runs even in `metadata-only`.

- [ ] **Step 1: Write failing tests.** In `test_claude_code_adapter.py`: a `pre` event whose `tool_input`
  contains `sk-live` and a card yields a record with `tool.arguments in (None, {...})` containing no
  plaintext, and `record.security_event.type is SecurityEventType.SECRET_DETECTED` with
  `evidence["kinds"]`; under `metadata-only` arguments stay `None` but the event still fires. Add
  `secret_args.json` fixture so `test_conformance.py` picks it up.

- [ ] **Step 2: Run** `pytest tests/test_claude_code_adapter.py tests/test_conformance.py -q` — Expected: FAIL.

- [ ] **Step 3: Implement.** In `normalize`, run `redact_mapping(event.get("tool_input"))` to get kinds;
  pass the masked mapping into `_arguments` (which applies the mode); attach the event when kinds exist.
  Add `FULL` to `_PRIVACY_MAP`.

- [ ] **Step 4: Run** `pytest tests/test_claude_code_adapter.py tests/test_conformance.py -q` — Expected: PASS.

- [ ] **Step 5: Commit** `feat(adapters): mask secrets and emit secret-detected (M4, R5)`.

---

### Task 4: Append-only JSONL store (`4.3`)

**Files:**
- Create: `packages/python-sdk/src/agentwatch/store.py`
- Test: `packages/python-sdk/tests/test_store.py`

**Interfaces:**
- Consumes: `records.AgentRecord`, `records.validate_record`.
- Produces:
  - `GENESIS_HASH = "0" * 64`.
  - `@dataclass(frozen=True) ChainEntry: seq: int; prev_hash: str; hash: str; record: AgentRecord | None; tombstone: bool`.
  - `class RecordStore:` `__init__(self, path: Path | str, *, max_size_mb: int | None = None)`,
    `append(self, record: AgentRecord) -> ChainEntry`, `entries(self) -> list[ChainEntry]`,
    `records(self) -> list[AgentRecord]`, `size_bytes(self) -> int`.
  - `_entry_hash(prev_hash: str, record: dict[str, Any]) -> str` (module-private helper reused by `verify`).

- [ ] **Step 1: Write failing tests** `test_store.py`: append two records then `records()` equals them and
  `entries()` has `seq` 0,1 with `entries[0].prev_hash == GENESIS_HASH` and
  `entries[1].prev_hash == entries[0].hash`; the file has one JSON object per line; a truncated final line
  is reported by `verify()` without raising from `records()` (Review Focus 2); reloading a new `RecordStore`
  on the same path returns the same records.

- [ ] **Step 2: Run** `pytest tests/test_store.py -q` — Expected: FAIL.

- [ ] **Step 3: Implement** the envelope append (serialize `record.to_dict()`, compute hash over
  `prev_hash + canonical json`, append with `\n`, `fsync`), `entries`/`records` parsing, and `size_bytes`.

- [ ] **Step 4: Run** `pytest tests/test_store.py -q` — Expected: PASS.

- [ ] **Step 5: Commit** `feat(store): append-only hash-chained JSONL store (M4)`.

---

### Task 5: Chain verification + `verify-store` (`4.4`)

**Files:**
- Modify: `packages/python-sdk/src/agentwatch/store.py`
- Modify: `packages/python-sdk/src/agentwatch/cli/main.py`
- Modify: `packages/python-sdk/tests/test_store.py`, `packages/python-sdk/tests/test_cli.py`

**Interfaces:**
- Consumes: `RecordStore`.
- Produces:
  - `class ChainError(Exception)`.
  - `@dataclass(frozen=True) ChainStatus: ok: bool; checked: int; broken_at: int | None`.
  - `RecordStore.verify(self) -> ChainStatus` — recomputes each live entry's hash and checks every
    `prev_hash` link; a mismatch yields `ok=False` with `broken_at=seq` (no raise).
  - CLI: `agentwatch verify-store` prints `chain ok (N entries)` and exits 0, or names the broken seq and
    exits 1.

- [ ] **Step 1: Write failing tests:** flip one character in a stored record, `verify().ok is False` and
  `broken_at` is the edited seq (F4); deleting a middle line breaks the link and is reported; CLI
  `main(["verify-store"])` returns 0 on a clean store and 1 on a tampered store (use `--set store.path=` to
  point at a temp store). Remove `verify-store` from `DEFERRED` and the npm-launcher deferred example.

- [ ] **Step 2: Run** `pytest tests/test_store.py tests/test_cli.py -q` — Expected: FAIL.

- [ ] **Step 3: Implement** `verify` and dispatch `verify-store` in the CLI.

- [ ] **Step 4: Run** those tests — Expected: PASS.

- [ ] **Step 5: Commit** `feat(store): hash-chain verification and verify-store CLI (M4, DD-07)`.

---

### Task 6: Retention + size cap (`4.5`, `4.7` F3)

**Files:**
- Modify: `packages/python-sdk/src/agentwatch/store.py`
- Modify: `packages/python-sdk/tests/test_store.py`

**Interfaces:**
- Consumes: `RecordStore`.
- Produces:
  - `class StoreFullError(Exception)`.
  - `@dataclass(frozen=True) RetentionReport: purged: int; kept: int`.
  - `RecordStore.append` raises `StoreFullError` when `size_bytes()` exceeds `max_size_mb` (F3, fail
    closed, no overwrite).
  - `RecordStore.apply_retention(self, *, retention_days: int, now: datetime | None = None) -> RetentionReport`
    — rewrites entries older than the window as tombstones (record payload dropped, `hash`/`seq`/`prev_hash`
    preserved) and never removes a line silently; entries with future timestamps are kept (Review Focus 3).

- [ ] **Step 1: Write failing tests:** with `max_size_mb` set tiny, `append` raises `StoreFullError` and the
  file is unchanged (F3); `apply_retention(retention_days=30)` tombstones an old entry, keeps a fresh one,
  and leaves `verify().ok is True`; a future-dated entry is kept.

- [ ] **Step 2: Run** `pytest tests/test_store.py -q` — Expected: FAIL.

- [ ] **Step 3: Implement** size check + retention rewrite.

- [ ] **Step 4: Run** — Expected: PASS.

- [ ] **Step 5: Commit** `feat(store): retention tombstones and size-cap fail-closed (M4, F3)`.

---

### Task 7: Redaction self-test and export gate (`4.6`)

**Files:**
- Create: `packages/python-sdk/src/agentwatch/selftest.py`
- Test: `packages/python-sdk/tests/test_selftest.py`

**Interfaces:**
- Consumes: `secrets.redact_mapping`, `redact.RedactionConfig`.
- Produces:
  - `SELF_TEST_CORPUS: tuple[dict[str, str], ...]` — fixed secret-bearing argument dicts.
  - `@dataclass(frozen=True) SelfTestResult: passed: bool; checked: int; leaks: tuple[str, ...]`.
  - `run_redaction_self_test(cfg: RedactionConfig | None = None) -> SelfTestResult` — runs each corpus item
    through masking + mode and asserts no raw secret substring survives.
  - `export_allowed(cfg: RedactionConfig | None = None) -> bool` — `run_redaction_self_test(cfg).passed`.

- [ ] **Step 1: Write failing tests:** a default run passes with `checked == len(SELF_TEST_CORPUS)` and
  `passed is True`; a deliberately broken pipeline (monkeypatched `redact_mapping` returning input
  unchanged) yields `passed is False` with the leaked value named, and `export_allowed` is False (F6/DD-09).

- [ ] **Step 2: Run** `pytest tests/test_selftest.py -q` — Expected: FAIL.

- [ ] **Step 3: Implement** the corpus and run/ gate.

- [ ] **Step 4: Run** — Expected: PASS.

- [ ] **Step 5: Commit** `feat(selftest): redaction self-test gates export (M4, DD-09)`.

---

### Task 8: Daemon writes through the store (`4.3`, `4.7`)

**Files:**
- Modify: `packages/python-sdk/src/agentwatch/daemon.py`
- Modify: `packages/python-sdk/tests/test_daemon.py`

**Interfaces:**
- Consumes: `RecordStore`, `StoreFullError`.
- Produces: `Daemon(..., store: RecordStore | None = None)` persists via the store; on startup it runs
  `store.verify()` and logs a warning naming a broken seq (F4); a `StoreFullError` during append is caught
  per message, surfaced to stderr/log, and does not overwrite or kill the daemon (F3); `handle_message`
  returns the persisted records.

- [ ] **Step 1: Write failing tests** (update existing daemon tests to read via `RecordStore(path).records()`
  instead of raw `records.jsonl`): round-trip still yields valid records; a tampered store file makes the
  daemon surface a chain warning; a full store does not drop previously written records.

- [ ] **Step 2: Run** `pytest tests/test_daemon.py -q` — Expected: FAIL (envelope format changed).

- [ ] **Step 3: Implement** store-backed sink + verify-on-start + F3 handling.

- [ ] **Step 4: Run** — Expected: PASS.

- [ ] **Step 5: Commit** `feat(daemon): persist via the hash-chained store (M4)`.

---

### Task 9: `sessions` reads through the store (`4.3`)

**Files:**
- Modify: `packages/python-sdk/src/agentwatch/cli/main.py`
- Modify: `packages/python-sdk/tests/test_cli_init.py`

**Interfaces:**
- Consumes: `RecordStore`.
- Produces: `agentwatch sessions` lists distinct `session_id`s with record counts by reading the envelope
  store; a missing/tampered store still prints `no sessions recorded` and exits 0.

- [ ] **Step 1: Write failing test** updating the `_write_records` helper to write envelope lines, then
  assert `sessions` output.

- [ ] **Step 2: Run** `pytest tests/test_cli_init.py -q` — Expected: FAIL.

- [ ] **Step 3: Implement** `sessions` over `RecordStore.records()`.

- [ ] **Step 4: Run** — Expected: PASS.

- [ ] **Step 5: Commit** `feat(cli): sessions reads the hash-chained store (M4)`.

---

### Task 10: Docs, CHANGELOG, WBS (`4.8`, `4.D`)

**Files:**
- Modify: `docs/design/storage-design.md` (status → shipped; envelope, tombstones, F3/F4),
  `docs/design/redaction-rules.md` (shipped; kind list), `docs/design/privacy-mode-transforms.md` (FULL),
  `docs/prd/15-data-model.md`, `docs/prd/17-error-handling.md` (point F3/F4/F6 at the shipped behavior),
  `CHANGELOG.md`, `docs/wbs/v0.1.0/wbs-v0.1.0-part3-store-export.md` (M4 ✅), `docs/wbs/v0.1.0/wbs-v0.1.0-index.md`.

**Interfaces:** none.

- [ ] **Step 1:** Update each doc's status to shipped and describe the envelope/chain/tombstone, secret
  kinds, FULL mode, and the self-test gate.
- [ ] **Step 2:** Add CHANGELOG bullets and mark M4 ✅ in the WBS (exit criteria).
- [ ] **Step 3:** Run `python3 -m pytest tests -q` (repo docs link-check) — Expected: PASS.
- [ ] **Step 4:** Commit `docs(m4): document the hash-chained store and redaction (M4)`.

---

## Execution

Native (implement in-session via superpowers:executing-plans). Tasks are sequential: each depends on the
previous task's exported signatures (`secrets` → adapter; `store` → daemon/CLI).
