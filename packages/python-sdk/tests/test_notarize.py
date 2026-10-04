"""Checkpoint notarization + signing tests (M22 W7/W9, #276/#278)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.notarize import (
    TimestampResult,
    build_timestamp_request,
    export_checkpoint,
    request_timestamp,
    verify_checkpoint,
)
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, StepType, ToolCall
from agentwatch.signing import (
    KEY_FILENAME,
    generate_key,
    load_or_create_key,
    sign_digest,
    verify_digest,
)
from agentwatch.store import RecordStore

AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _store(path: Path) -> RecordStore:
    store = RecordStore(path)
    store.append(
        AgentRecord(
            session_id="s1",
            agent=AgentIdentity(identity="a"),
            tool=ToolCall(name="Bash"),
            outcome=Outcome.OK,
            started_at=AT,
            step_type=StepType.ACT,
        )
    )
    return store


# --------------------------------------------------------------------------- W9 signing


def test_signature_roundtrip() -> None:
    key = generate_key()
    signature = sign_digest(key, "abc123")
    assert verify_digest(key.public_bytes, "abc123", signature) is True


def test_tampered_digest_fails() -> None:
    key = generate_key()
    signature = sign_digest(key, "abc123")
    assert verify_digest(key.public_bytes, "abc124", signature) is False


# --------------------------------------------------------------------------- W7 notarize


def test_timestamp_request_is_der_sequence() -> None:
    request = build_timestamp_request("ab" * 32)
    assert request[:1] == b"\x30"
    assert len(request) > 10


def test_export_unsigned_is_digest_only(tmp_path: Path) -> None:
    store = _store(tmp_path / "records.jsonl")

    export = export_checkpoint(store)

    assert export.digest
    assert export.signature is None
    assert export.note == "digest-only"


def test_signed_checkpoint_verifies(tmp_path: Path) -> None:
    store = _store(tmp_path / "records.jsonl")
    key = generate_key()

    export = export_checkpoint(store, signer=key)

    assert export.key_id == key.key_id
    assert verify_checkpoint(export, key.public_bytes) is True


def test_timestamp_attached(tmp_path: Path) -> None:
    store = _store(tmp_path / "records.jsonl")

    export = export_checkpoint(store, timestamp=lambda digest: TimestampResult(token="tok"))

    assert export.timestamp_token == "tok"
    assert export.note is None


def test_tsa_failure_still_exports_digest(tmp_path: Path) -> None:
    store = _store(tmp_path / "records.jsonl")

    export = export_checkpoint(
        store, timestamp=lambda digest: TimestampResult(error="TSA unreachable: down")
    )

    assert export.digest
    assert export.timestamp_token is None
    assert export.note and "TSA unreachable" in export.note


def test_request_timestamp_success() -> None:
    result = request_timestamp("ab" * 32, "https://tsa.invalid", poster=lambda req, t: b"TOKEN")

    assert result.ok
    assert result.token is not None


def test_request_timestamp_failure_is_reported() -> None:
    def boom(request: object, timeout: float) -> bytes:
        raise OSError("refused")

    result = request_timestamp("ab" * 32, "https://tsa.invalid", poster=boom)

    assert result.ok is False
    assert result.error and "unreachable" in result.error


# --------------------------------------------------------------------------- CLI


def test_cli_checkpoint_export_and_verify(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir / "records.jsonl")

    rc = main(["--set", f"store.path={store_dir}", "checkpoint", "export", "--sign", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["signature"]

    export_file = tmp_path / "checkpoint.json"
    export_file.write_text(json.dumps(payload), encoding="utf-8")
    key = load_or_create_key(store_dir / KEY_FILENAME)
    pub = tmp_path / "signing.pub"
    pub.write_bytes(key.public_bytes)

    rc = main(["checkpoint", "verify", str(export_file), "--public-key", str(pub), "--json"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
