"""Session-start recorder attestation tests (M29 DEP-2, #442; PRD 50).

The hash chain proves stored records were not altered; it cannot prove recording
was *on*. A session-start attestation fact (effective hook sources, a keyed
config digest, managed-policy status, permission mode) plus a
``recorder-config-changed`` observation when that digest changes answers "was
recording active at 14:03?". Digests/booleans only — never config values or
secrets — and a session with no attestation is ``attestation:absent``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from agentwatch.attestation import (
    ATTESTATION_ABSENT,
    ATTESTATION_PRESENT,
    attest_session,
    attestation_status,
    config_digest,
    last_attestation,
)
from agentwatch.coverage import build_coverage
from agentwatch.recorder_state import (
    MARKER_TOOLS,
    RECORDER_ATTESTED_TOOL,
    RECORDER_CONFIG_CHANGED_TOOL,
)
from agentwatch.store import RecordStore

AT = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _store(tmp_path: Path) -> RecordStore:
    return RecordStore(tmp_path / "records.jsonl")


def _markers(store: RecordStore) -> list[str]:
    return [r.tool.name for r in store.records() if r.tool.name in MARKER_TOOLS]


def test_marker_tools_registered() -> None:
    assert RECORDER_ATTESTED_TOOL in MARKER_TOOLS
    assert RECORDER_CONFIG_CHANGED_TOOL in MARKER_TOOLS


def test_config_digest_is_stable_and_changes_with_inputs() -> None:
    sources = {"managed": False, "user": True, "project": False, "plugin": False}
    first = config_digest(
        hook_sources=sources, managed_policy=False, permission_mode="default", key=b"k"
    )

    assert first == config_digest(
        hook_sources=dict(sources), managed_policy=False, permission_mode="default", key=b"k"
    )
    # A different key, a changed source, or a changed permission mode changes it.
    assert first != config_digest(
        hook_sources=sources, managed_policy=False, permission_mode="default", key=b"other"
    )
    assert first != config_digest(
        hook_sources={**sources, "user": False},
        managed_policy=False,
        permission_mode="default",
        key=b"k",
    )
    assert first != config_digest(
        hook_sources=sources, managed_policy=False, permission_mode="bypass", key=b"k"
    )


def test_attest_session_appends_boolean_only_marker(tmp_path: Path) -> None:
    store = _store(tmp_path)

    report = attest_session(
        store,
        user=True,
        permission_mode="default",
        recorder_version="0.1.0",
        key=b"k",
        now=AT,
    )

    assert report.marker.seq is not None
    assert report.config_changed is None
    marker = store.records()[0]
    assert marker.tool.name == RECORDER_ATTESTED_TOOL
    arguments = marker.tool.arguments
    assert arguments is not None
    assert arguments["attestation"] == ATTESTATION_PRESENT
    assert arguments["hook_sources"] == {
        "managed": False,
        "user": True,
        "project": False,
        "plugin": False,
    }
    assert arguments["managed_policy"] is False
    assert arguments["permission_mode"] == "default"
    assert arguments["recorder_version"] == "0.1.0"
    assert len(arguments["config_digest"]) == 16
    assert store.verify().ok


def test_stripped_hooks_raise_recorder_config_changed(tmp_path: Path) -> None:
    store = _store(tmp_path)
    attest_session(store, user=True, permission_mode="default", key=b"k", now=AT)

    # Hooks are stripped between the two sessions: the effective sources change.
    report = attest_session(store, user=False, permission_mode="default", key=b"k", now=AT)

    assert report.config_changed is not None
    assert report.marker.seq is not None
    changed_marker = [
        r for r in store.records() if r.tool.name == RECORDER_CONFIG_CHANGED_TOOL
    ][0]
    arguments = changed_marker.tool.arguments
    assert arguments is not None
    assert arguments["old_digest"] != arguments["new_digest"]
    assert arguments["changed"] == {"user": True}
    assert _markers(store) == [
        RECORDER_ATTESTED_TOOL,
        RECORDER_CONFIG_CHANGED_TOOL,
        RECORDER_ATTESTED_TOOL,
    ]


def test_identical_attestation_is_coalesced(tmp_path: Path) -> None:
    store = _store(tmp_path)
    attest_session(store, user=True, permission_mode="default", key=b"k", now=AT)

    report = attest_session(store, user=True, permission_mode="default", key=b"k", now=AT)

    assert report.marker.coalesced is True
    assert report.config_changed is None
    assert _markers(store) == [RECORDER_ATTESTED_TOOL]


def test_last_attestation_round_trips(tmp_path: Path) -> None:
    store = _store(tmp_path)
    assert last_attestation(store) is None
    assert attestation_status(store) == ATTESTATION_ABSENT

    attest_session(
        store, managed=True, plugin=True, managed_policy=True, permission_mode="bypass", now=AT
    )

    latest = last_attestation(store)
    assert latest is not None
    assert latest.hook_sources == {
        "managed": True,
        "user": False,
        "project": False,
        "plugin": True,
    }
    assert latest.managed_policy is True
    assert latest.permission_mode == "bypass"
    assert attestation_status(store) == ATTESTATION_PRESENT


def test_coverage_and_evidence_surface_the_attestation(tmp_path: Path) -> None:
    store = _store(tmp_path)
    without = build_coverage(store, transcripts={}, transcripts_present=False)
    assert without.attestation == ATTESTATION_ABSENT
    assert without.to_dict()["attestation"] == ATTESTATION_ABSENT

    attest_session(store, user=True, now=AT)
    with_attestation = build_coverage(store, transcripts={}, transcripts_present=False)
    assert with_attestation.attestation == ATTESTATION_PRESENT


def test_daemon_attests_once_per_session(tmp_path: Path) -> None:
    from agentwatch.daemon import Daemon

    store = RecordStore(tmp_path / "records.jsonl", durability="none")
    daemon = Daemon(
        socket_path=tmp_path / "d.sock",
        store=store,
        records_path=tmp_path / "records.jsonl",
    )
    message = {
        "phase": "session-start",
        "harness": "claude-code",
        "event": {"session_id": "sess-attest", "timestamp": "2026-01-02T03:04:00+00:00"},
    }

    daemon.handle_message(message)
    daemon.handle_message(message)  # a re-delivered SessionStart must not double-attest

    assert attestation_status(store) == ATTESTATION_PRESENT
    attested = [r for r in store.records() if r.tool.name == RECORDER_ATTESTED_TOOL]
    assert len(attested) == 1


@settings(max_examples=25, deadline=None)
@given(secret=st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", min_size=12, max_size=24))
def test_attestation_never_stores_config_values(secret: str) -> None:
    # A managed settings document carrying an arbitrary "secret" value; the
    # attestation digest is over booleans/mode only, so the value never enters.
    import tempfile

    from agentwatch.managed_policy import detect_managed_policy

    base = Path(tempfile.mkdtemp(prefix="aw-attest-"))
    settings_path = base / "managed.json"
    settings_path.write_text(
        json.dumps(
            {
                "allowManagedHooksOnly": False,
                "apiKey": secret,
                "hooks": {"PreToolUse": [{"matcher": "*", "hooks": []}]},
            }
        ),
        encoding="utf-8",
    )
    policy = detect_managed_policy([settings_path])

    store = RecordStore(base / "records.jsonl")
    attest_session(store, user=True, managed_policy=policy.blocks_user_hooks, now=AT)

    arguments = store.records()[0].tool.arguments
    assert arguments is not None
    assert secret not in json.dumps(arguments)
    assert set(arguments) == {
        "attestation",
        "config_digest",
        "hook_sources",
        "managed_policy",
        "permission_mode",
        "recorder_version",
    }
