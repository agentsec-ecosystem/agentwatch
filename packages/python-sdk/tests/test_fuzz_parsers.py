"""Fuzz harnesses for the untrusted-input parsers (PRD 38 §Q3, issue #220).

Every untrusted-input surface already exists in v0.1.0: hook JSON, daemon socket
frames, store lines, transcripts, NDJSON/OTel ingest, and MCP JSON-RPC. These
harnesses feed arbitrary input and assert the parser either *contains* it
(rejects / quarantines / returns an empty result) or raises its documented error
type — never an unhandled crash.

A committed seed corpus is expressed with ``@example`` decorators (regression
cases for previously-seen shapes). Run with more examples nightly:

    FUZZ_PROFILE=fuzz pytest tests/test_fuzz_parsers.py
"""

from __future__ import annotations

import contextlib
import io
import itertools
import os
import tempfile
from pathlib import Path
from typing import Any

from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from agentwatch import hook as hook_module
from agentwatch import mcp_proxy, session_export, transcript
from agentwatch.daemon import Daemon
from agentwatch.ingest import transcode_ndjson
from agentwatch.records import RecordValidationError, validate_event, validate_record
from agentwatch.store import RecordStore

settings.register_profile(
    "agentwatch_fuzz",
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
settings.register_profile(
    "fuzz",
    max_examples=1000,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
settings.load_profile(os.environ.get("FUZZ_PROFILE", "agentwatch_fuzz"))

_FUZZ_DIR = Path(tempfile.mkdtemp(prefix="agentwatch-fuzz-"))
_counter = itertools.count()

_JSON = st.recursive(
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(),
    lambda children: st.lists(children, max_size=4)
    | st.dictionaries(st.text(max_size=8), children, max_size=4),
    max_leaves=8,
)

_PHASES = (
    "pre",
    "post",
    "denied",
    "prompt",
    "session-start",
    "session-end",
    "event",
    "mcp",
    "hook-error",
    "unknown-phase",
)

_MESSAGES = st.one_of(
    _JSON,
    st.fixed_dictionaries(
        {"phase": st.sampled_from(_PHASES), "event": _JSON, "harness": st.text(max_size=12)}
    ),
)


def _fresh_dir() -> Path:
    path = _FUZZ_DIR / f"case-{next(_counter)}"
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# MCP JSON-RPC relay frames
# ---------------------------------------------------------------------------


@given(st.binary(max_size=512))
@example(b'{"jsonrpc":"2.0","id":1')
@example(b"")
@example(b"\xff\xfe\x00")
def test_mcp_parse_contains_every_frame(payload: bytes) -> None:
    # ``_parse`` is the relay's containment boundary: malformed frames become None.
    mcp_proxy._parse(payload)


# ---------------------------------------------------------------------------
# Hook stdin JSON
# ---------------------------------------------------------------------------


@given(st.text(max_size=512))
@example('{"session_id": "s", "tool_name": "Bash"}')
@example("{not json")
@example("")
def test_hook_never_crashes_and_always_exits_zero(text: str) -> None:
    socket_path = str(_fresh_dir() / "hook.sock")
    exit_code = hook_module.main(["pre"], stdin=io.StringIO(text), socket_path=socket_path)

    assert exit_code == 0


# ---------------------------------------------------------------------------
# Transcript usage extraction
# ---------------------------------------------------------------------------


@given(st.text(max_size=1024))
@example('{"message": {"usage": {"input_tokens": 5}, "model": "claude"}}')
@example("not json\n{bad}\n")
def test_transcript_usage_extraction_never_crashes(text: str) -> None:
    path = _fresh_dir() / "transcript.jsonl"
    path.write_text(text, encoding="utf-8")

    summary = transcript.extract_usage(path)

    assert summary.tokens >= 0


# ---------------------------------------------------------------------------
# Session-export NDJSON
# ---------------------------------------------------------------------------


@given(st.text(max_size=1024))
@example("")
@example("0")  # regression: valid JSON scalar crashed the object check (Q3 fuzz)
@example("[1, 2]")
@example("{not json}\n")
@example('{"schema": "agentwatch.export/0.1.0", "session_id": "s"}\n')
def test_session_export_parse_rejects_or_parses(text: str) -> None:
    with contextlib.suppress(ValueError):
        # json.JSONDecodeError is a ValueError: a controlled rejection.
        session_export.parse_ndjson(text)


# ---------------------------------------------------------------------------
# OTel / NDJSON ingest
# ---------------------------------------------------------------------------


@given(st.text(max_size=1024))
@example('{"resourceSpans": []}')
@example('{"not": "otlp"}\n[1, 2, 3]\n')
def test_ndjson_ingest_never_crashes(text: str) -> None:
    records, problems = transcode_ndjson(text)

    assert isinstance(records, list)
    assert isinstance(problems, list)


# ---------------------------------------------------------------------------
# Record / security-event validation (strict, reject-never-coerce)
# ---------------------------------------------------------------------------


@given(_JSON)
@example({"session_id": "s"})
@example({"unknown": True})
@example([])
def test_validate_record_rejects_or_accepts(value: Any) -> None:
    with contextlib.suppress(RecordValidationError):
        validate_record(value)


@given(_JSON)
@example({"kind": "secret-detected"})
@example(None)
def test_validate_event_rejects_or_accepts(value: Any) -> None:
    with contextlib.suppress(RecordValidationError):
        validate_event(value)


# ---------------------------------------------------------------------------
# Daemon socket frames
# ---------------------------------------------------------------------------


@given(_MESSAGES)
@example({"phase": "pre", "event": {"session_id": "s", "tool_name": "Bash"}})
@example({"phase": "event", "event": {"kind": "weird"}})
@example({"phase": "mcp", "event": {"jsonrpc": "2.0"}})
def test_daemon_handle_message_never_crashes(message: Any) -> None:
    root = _fresh_dir()
    daemon = Daemon(
        socket_path=root / "d.sock",
        store=RecordStore(root / "records.jsonl", durability="none"),
        records_path=root / "records.jsonl",
    )

    daemon.handle_message(message)


# ---------------------------------------------------------------------------
# Store lines
# ---------------------------------------------------------------------------


@given(st.lists(st.text(max_size=200), min_size=1, max_size=6))
@example(['{"seq": 0, "prev_hash": "x", "hash": "y", "record": {}}'])
@example(["not json", "{}", "[]"])
def test_store_loading_arbitrary_lines_is_contained(lines: list[str]) -> None:
    path = _fresh_dir() / "records.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    store = RecordStore(path, durability="none")
    status = store.verify()

    # Never crashes. A store of arbitrary lines either verifies as empty or is
    # reported not-ok; it is never silently reported as a valid chain.
    if status.ok:
        assert store.records() == []
