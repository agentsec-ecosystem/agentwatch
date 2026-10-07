"""CMP-4 — ed25519 signed default posture (M28, #361; PRD 44 §CMP-4).

Signing graduates from an unreleased experiment (G8) to a supported posture:
the key *rotates* and the rotation is a recorded chain event; verification is
folded into ``verify-store``/``evidence``/AAT; the posture is surfaced in
``doctor``/``/healthz``; and a key we no longer hold reports
"signed by key id X, key unavailable" rather than passing silently.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agentwatch import doctor
from agentwatch.aat import export_aat
from agentwatch.cli.main import main
from agentwatch.configuration import (
    AgentwatchConfig,
    ExportSection,
    HealthSection,
    LogSection,
    PrivacySection,
    RedactionSection,
    StoreSection,
)
from agentwatch.evidence import build_bundle
from agentwatch.health import HealthSnapshot
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, RecordPrivacyMode, ToolCall
from agentwatch.session_export import export_session
from agentwatch.signing import (
    KEY_FILENAME,
    KEY_ROTATION_TOOL,
    generate_key,
    key_rotations,
    load_or_create_key,
    record_key_rotation,
    rotate_key,
    sign_digest,
    signing_status,
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
        )
    )
    return store


def _cfg(store_dir: Path) -> AgentwatchConfig:
    return AgentwatchConfig(
        store=StoreSection(path=str(store_dir), retention_days=30, max_size_mb=1024),
        privacy=PrivacySection(mode="metadata-only"),
        redaction=RedactionSection(self_test="enabled"),
        export=ExportSection(enabled=False, otlp_endpoint=None, format="otel-genai"),
        health=HealthSection(endpoint="127.0.0.1:9100"),
        log=LogSection(level="info"),
    )


# --------------------------------------------------------------------------- rotation


def test_rotate_key_starts_a_new_epoch(tmp_path: Path) -> None:
    path = tmp_path / KEY_FILENAME
    old = load_or_create_key(path)
    old_signature = sign_digest(old, "digest-1")

    result = rotate_key(path)

    assert result.previous_key_id == old.key_id
    assert result.key.key_id != old.key_id
    # The old public key still verifies what the old key signed.
    assert verify_digest(old.public_bytes, "digest-1", old_signature) is True
    # The new key is what is now on disk.
    assert load_or_create_key(path).key_id == result.key.key_id


def test_rotation_is_a_recorded_metadata_only_chain_event(tmp_path: Path) -> None:
    store = _store(tmp_path / "records.jsonl")

    seq = record_key_rotation(store, "old-key", "new-key", now=AT)

    assert store.verify().ok is True
    rotations = key_rotations(store)
    assert len(rotations) == 1
    assert rotations[0].seq == seq
    assert rotations[0].previous_key_id == "old-key"
    assert rotations[0].new_key_id == "new-key"
    assert rotations[0].at == AT

    entry = next(e for e in store.entries() if e.seq == seq)
    assert entry.record is not None
    assert entry.record.tool.name == KEY_ROTATION_TOOL
    assert entry.record.tool.privacy_mode == RecordPrivacyMode.METADATA_ONLY


# --------------------------------------------------------------------------- posture


def test_signing_status_reports_held_key(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = _store(store_dir / "records.jsonl")
    key = load_or_create_key(store_dir / KEY_FILENAME)

    status = signing_status(store, store_dir)

    assert status.key_id == key.key_id
    assert status.key_present is True
    assert status.epoch == 1
    assert key.key_id in status.summary


def test_missing_key_reports_signed_but_unavailable(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = _store(store_dir / "records.jsonl")
    old = load_or_create_key(store_dir / KEY_FILENAME)
    result = rotate_key(store_dir / KEY_FILENAME)
    record_key_rotation(store, old.key_id, result.key.key_id)

    # The epoch key is gone: we can still say what signed, not verify it.
    (store_dir / KEY_FILENAME).unlink()
    status = signing_status(store, store_dir)

    assert status.key_id == result.key.key_id
    assert status.key_present is False
    assert status.summary == f"signed by key id {result.key.key_id}, key unavailable"


def test_signing_status_unconfigured(tmp_path: Path) -> None:
    store = _store(tmp_path / "records.jsonl")

    status = signing_status(store, tmp_path)

    assert status.key_id is None
    assert status.key_present is False
    assert "not configured" in status.summary


# --------------------------------------------------------------------------- surfaces


def test_cli_checkpoint_rotate_records_event(tmp_path: Path, capsys) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = _store(store_dir / "records.jsonl")
    old = load_or_create_key(store_dir / KEY_FILENAME)

    rc = main(["--set", f"store.path={store_dir}", "checkpoint", "rotate", "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["previous_key_id"] == old.key_id
    assert payload["key_id"] != old.key_id
    assert payload["seq"] >= 1

    reloaded = RecordStore(store_dir / "records.jsonl")
    rotations = key_rotations(reloaded)
    assert [r.new_key_id for r in rotations] == [payload["key_id"]]
    assert reloaded.verify().ok is True


def test_verify_store_reports_signing_posture(tmp_path: Path, capsys) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir / "records.jsonl")
    key = load_or_create_key(store_dir / KEY_FILENAME)

    rc = main(["--set", f"store.path={store_dir}", "verify-store"])

    out = capsys.readouterr().out
    assert rc == 0
    assert "signing:" in out
    assert key.key_id in out


def test_evidence_bundle_carries_signing_posture(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = _store(store_dir / "records.jsonl")
    key = load_or_create_key(store_dir / KEY_FILENAME)

    bundle = build_bundle(store, store_dir / "records.jsonl", "s1")

    assert "signing.json" in bundle.members
    payload = json.loads(bundle.members["signing.json"])
    assert payload["key_id"] == key.key_id
    assert payload["key_present"] is True


def test_aat_export_carries_signing_posture(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = _store(store_dir / "records.jsonl")
    key = load_or_create_key(store_dir / KEY_FILENAME)

    bundle = export_aat(
        export_session(store, "s1"),
        privacy_mode="metadata-only",
        signing=signing_status(store, store_dir).to_dict(),
    )

    assert bundle["coverage"]["signing"]["key_id"] == key.key_id


def test_doctor_has_signing_check(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    _store(store_dir / "records.jsonl")
    key = load_or_create_key(store_dir / KEY_FILENAME)

    results = doctor.run_checks(
        cfg=_cfg(store_dir),
        store_path=store_dir / "records.jsonl",
        socket_path=tmp_path / "d.sock",
        settings_paths={"project": tmp_path / "none.json", "user": tmp_path / "none2.json"},
    )

    statuses = {r.name: r for r in results}
    assert "signing" in statuses
    assert statuses["signing"].status == doctor.PASS
    assert key.key_id in statuses["signing"].detail


def test_healthz_reports_signing_state(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = _store(store_dir / "records.jsonl")
    key = load_or_create_key(store_dir / KEY_FILENAME)

    payload = HealthSnapshot(store_path=store.path).to_dict()

    assert payload["signing"]["configured"] is True
    assert payload["signing"]["key_id"] == key.key_id


# --------------------------------------------------------------------------- tamper


def test_tampered_signature_fails_end_to_end(tmp_path: Path) -> None:
    key = generate_key()
    signature = sign_digest(key, "digest-1")

    assert verify_digest(key.public_bytes, "digest-2", signature) is False
