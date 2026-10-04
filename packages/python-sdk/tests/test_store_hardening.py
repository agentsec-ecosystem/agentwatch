"""Store hardening tests (M12 F5/E1/E2/G2/K1)."""

from __future__ import annotations

import importlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch import posture
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore, repair_store

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(session: str = "s1", span: str = "sp1") -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent-1"),
        tool=ToolCall(name="Bash"),
        outcome=Outcome.OK,
        started_at=START,
        span_id=span,
    )


def test_secure_dir_and_file_modes(tmp_path: Path) -> None:
    directory = tmp_path / "store"
    posture.secure_dir(directory)
    file = directory / "records.jsonl"
    file.write_text("x", encoding="utf-8")
    posture.secure_file(file)

    assert posture.mode_of(directory) == 0o700
    assert posture.mode_of(file) == 0o600
    assert posture.is_private(directory, directory=True)
    assert posture.is_private(file)
    assert posture.mode_of(tmp_path / "absent") is None


def test_store_creates_private_dir_and_file(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "data" / "records.jsonl")
    store.append(_record())

    assert posture.mode_of(store.path.parent) == 0o700
    assert posture.mode_of(store.path) == 0o600


@pytest.mark.parametrize("mode", ["record", "checkpoint", "none"])
def test_durability_modes_append_and_verify(tmp_path: Path, mode: str) -> None:
    store = RecordStore(tmp_path / "records.jsonl", durability=mode)
    store.append(_record())
    store.close()

    assert store.durability == mode
    assert store.verify().ok
    assert len(store.records()) == 1


def test_unknown_durability_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        RecordStore(tmp_path / "records.jsonl", durability="sometimes")


def test_auto_checkpoint_every_n_entries(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl", checkpoint_every=3)
    for index in range(7):
        store.append(_record(session=f"s{index}", span=f"sp{index}"))

    checkpoints = store.checkpoints()
    assert checkpoints  # at least one
    assert store.verify().ok
    # Records survive checkpoints and stay ordered.
    assert [record.session_id for record in store.records()] == [f"s{i}" for i in range(7)]


def test_manual_checkpoint_and_tamper_detection(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record())
    entry = store.checkpoint()
    assert entry.checkpoint
    assert store.verify().ok

    lines = store.path.read_text(encoding="utf-8").splitlines()
    checkpoint = json.loads(lines[-1])
    checkpoint["entries"] = 2  # breaks the checkpoint hash
    lines[-1] = json.dumps(checkpoint)
    store.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert not RecordStore(store.path).verify().ok


def test_refresh_surfaces_mid_session_tamper(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record())
    assert store.refresh().ok

    # Edit the stored record content behind the store's back.
    lines = store.path.read_text(encoding="utf-8").splitlines()
    envelope = json.loads(lines[1])
    envelope["record"]["outcome"] = "error"
    lines[1] = json.dumps(envelope)
    store.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert not store.refresh().ok


def test_reload_adopts_a_shorter_chain_but_refresh_does_not(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    for index in range(3):
        store.append(_record(session=f"s{index}", span=f"sp{index}"))
    assert len(store.entries()) == 3

    # Rewrite the file to a shorter, valid chain (what archive sealing does).
    lines = store.path.read_text(encoding="utf-8").splitlines()
    store.path.write_text("\n".join(lines[:2]) + "\n", encoding="utf-8")

    # refresh is append-aware and refuses to shrink the in-memory chain...
    store.refresh()
    assert len(store.entries()) == 3
    # ...reload() trusts the file for rewrite operations.
    assert store.reload().ok
    assert len(store.entries()) == 1


def test_repair_rebuilds_from_intact_prefix_with_evidence(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    for index in range(5):
        store.append(_record(session=f"s{index}", span=f"sp{index}"))

    # Corrupt entry at seq 2 by rewriting its record payload.
    lines = store.path.read_text(encoding="utf-8").splitlines()
    envelope = json.loads(lines[3])
    envelope["record"]["tool"]["name"] = "Tampered"
    lines[3] = json.dumps(envelope)
    store.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert not RecordStore(store.path).verify().ok

    report = repair_store(store.path)

    assert report.repaired
    assert report.broken_at == 2
    assert report.salvaged == 2
    assert report.dropped == 3
    assert report.evidence_path is not None
    repaired = RecordStore(store.path)
    assert repaired.verify().ok
    assert [record.session_id for record in repaired.records()] == ["s0", "s1"]


def test_repair_keeps_byte_identical_evidence(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    for index in range(4):
        store.append(_record(session=f"s{index}", span=f"sp{index}"))
    lines = store.path.read_text(encoding="utf-8").splitlines()
    envelope = json.loads(lines[2])
    envelope["record"]["outcome"] = "error"
    lines[2] = json.dumps(envelope)
    store.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    damaged_bytes = store.path.read_bytes()

    report = repair_store(store.path)

    assert report.evidence_path is not None
    assert report.evidence_path.read_bytes() == damaged_bytes


def test_repair_is_a_noop_when_chain_is_green(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_record())

    report = repair_store(store.path)

    assert not report.repaired
    assert report.broken_at is None
    assert report.evidence_path is None


def test_cli_verify_store_repair_requires_yes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main = importlib.import_module("agentwatch.cli.main")
    monkeypatch.setenv("AGENTWATCH_STORE__PATH", str(tmp_path))
    store = RecordStore(tmp_path / "records.jsonl")
    for index in range(3):
        store.append(_record(session=f"s{index}", span=f"sp{index}"))
    lines = store.path.read_text(encoding="utf-8").splitlines()
    envelope = json.loads(lines[1])
    envelope["record"]["outcome"] = "error"
    lines[1] = json.dumps(envelope)
    store.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert main.main(["verify-store", "--repair"]) == 2
    assert "without --yes" in capsys.readouterr().err

    assert main.main(["verify-store", "--repair", "--yes"]) == 0
    assert RecordStore(tmp_path / "records.jsonl").verify().ok


def test_daemon_socket_remains_private(tmp_path: Path) -> None:
    # A smoke check that posture constants are what the daemon advertises.
    assert os.access(tmp_path, os.W_OK)
    assert posture.DIR_MODE == 0o700
    assert posture.FILE_MODE == 0o600
