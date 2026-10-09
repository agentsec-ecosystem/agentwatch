"""Capability drift + ``capability-changed`` event (M30 CAP-2, #459; PRD 52).

Generalizes the S4 tool-surface snapshot/diff to every capability kind. The
headline shape is **Plugin4Shell**: same name and declared version, different
content → a new digest. Wording is factual ("content changed, version
unchanged"), never a verdict.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agentwatch.capabilities import (
    CAP_KIND_HOOK,
    CAP_KIND_PLUGIN,
    CAP_KIND_SKILL,
    CAPABILITY_SNAPSHOT_TOOL,
    CHANGE_ADDED,
    CHANGE_REMOVED,
    CHANGE_VERSION_CHANGED,
    CHANGE_VERSION_UNCHANGED,
    SCOPE_PROJECT,
    SCOPE_USER,
    Capability,
    detect_capability_changes,
    record_capability_snapshot,
    render_capability_changes,
    snapshot_records,
)
from agentwatch.cli.main import main
from agentwatch.ocsf import ocsf_target
from agentwatch.records import SecurityEventType
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _cap(
    kind: str,
    name: str,
    digest: str,
    *,
    version: str | None = None,
    scope: str = SCOPE_USER,
) -> Capability:
    return Capability(
        kind=kind,
        name=name,
        scope=scope,
        digest=digest,
        size=10,
        declared_version=version,
    )


def _store(tmp_path: Path) -> RecordStore:
    return RecordStore(tmp_path / "records.jsonl")


def test_plugin4shell_shape_is_content_changed_version_unchanged(tmp_path: Path) -> None:
    """Same name + version, swapped content → distinct factual change class."""
    store = _store(tmp_path)
    record_capability_snapshot(
        store, "s1", [_cap(CAP_KIND_PLUGIN, "demo", "a" * 64, version="1.2.3")], now=START
    )
    changes = record_capability_snapshot(
        store,
        "s2",
        [_cap(CAP_KIND_PLUGIN, "demo", "b" * 64, version="1.2.3")],
        now=START + timedelta(hours=1),
    )

    assert len(changes) == 1
    change = changes[0]
    assert change.name == "demo"
    assert change.change == CHANGE_VERSION_UNCHANGED
    assert change.declared_version == "1.2.3"
    assert change.prev_digest == "a" * 64
    assert change.digest == "b" * 64


def test_version_change_is_a_distinct_class(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record_capability_snapshot(
        store, "s1", [_cap(CAP_KIND_PLUGIN, "demo", "a" * 64, version="1.0.0")], now=START
    )
    changes = record_capability_snapshot(
        store,
        "s2",
        [_cap(CAP_KIND_PLUGIN, "demo", "b" * 64, version="2.0.0")],
        now=START + timedelta(hours=1),
    )
    assert changes[0].change == CHANGE_VERSION_CHANGED


def test_new_capability_and_removal_are_reported(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record_capability_snapshot(
        store, "s1", [_cap(CAP_KIND_SKILL, "pdf", "a" * 64)], now=START
    )
    added = record_capability_snapshot(
        store,
        "s2",
        [
            _cap(CAP_KIND_SKILL, "pdf", "a" * 64),
            _cap(CAP_KIND_SKILL, "code", "c" * 64, scope=SCOPE_PROJECT),
        ],
        now=START + timedelta(hours=1),
    )
    assert [c.change for c in added] == [CHANGE_ADDED]
    assert added[0].name == "code"

    removed = record_capability_snapshot(
        store, "s3", [_cap(CAP_KIND_SKILL, "pdf", "a" * 64)], now=START + timedelta(hours=2)
    )
    assert [c.change for c in removed] == [CHANGE_REMOVED]
    assert removed[0].name == "code"


def test_new_hook_is_surfaced(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record_capability_snapshot(store, "s1", [], now=START)
    changes = record_capability_snapshot(
        store,
        "s2",
        [_cap(CAP_KIND_HOOK, "PreToolUse:Bash", "h" * 64)],
        now=START + timedelta(hours=1),
    )
    assert [c.kind for c in changes] == [CAP_KIND_HOOK]
    assert changes[0].change == CHANGE_ADDED


def test_first_snapshot_emits_no_change(tmp_path: Path) -> None:
    store = _store(tmp_path)
    changes = record_capability_snapshot(
        store, "s1", [_cap(CAP_KIND_SKILL, "pdf", "a" * 64)], now=START
    )
    assert changes == []


def test_snapshot_records_are_metadata_only(tmp_path: Path) -> None:
    records = snapshot_records(
        "s1", [_cap(CAP_KIND_PLUGIN, "demo", "a" * 64, version="1.2.3")], at=START
    )
    assert len(records) == 1
    record = records[0]
    assert record.tool.name == CAPABILITY_SNAPSHOT_TOOL
    arguments = record.tool.arguments or {}
    entries = arguments["capabilities"]
    assert entries[0]["digest"] == "a" * 64
    assert entries[0]["declared_version"] == "1.2.3"
    assert "content" not in json.dumps(arguments)


def test_detect_capability_changes_reads_carriers(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record_capability_snapshot(store, "s1", [_cap(CAP_KIND_SKILL, "pdf", "a" * 64)], now=START)
    record_capability_snapshot(
        store, "s2", [_cap(CAP_KIND_SKILL, "pdf", "b" * 64)], now=START + timedelta(hours=1)
    )
    changes = detect_capability_changes(store.records())
    assert [c.change for c in changes] == [CHANGE_VERSION_UNCHANGED]


def test_event_is_the_existing_capability_changed_type(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record_capability_snapshot(store, "s1", [_cap(CAP_KIND_SKILL, "pdf", "a" * 64)], now=START)
    record_capability_snapshot(
        store, "s2", [_cap(CAP_KIND_SKILL, "pdf", "b" * 64)], now=START + timedelta(hours=1)
    )
    events = [
        record
        for record in store.records()
        if record.security_event is not None
        and record.security_event.type is SecurityEventType.CAPABILITY_CHANGED
    ]
    assert len(events) == 1
    event = events[0].security_event
    assert event is not None and event.evidence is not None
    assert event.evidence["digest"] == "b" * 64
    assert event.evidence["change"] == CHANGE_VERSION_UNCHANGED
    # The vocabulary already ships from M29 EXT-3; it must map in OCSF.
    assert ocsf_target("capability-changed") is not None


def test_wording_is_factual_never_a_verdict(tmp_path: Path) -> None:
    store = _store(tmp_path)
    record_capability_snapshot(store, "s1", [_cap(CAP_KIND_PLUGIN, "demo", "a" * 64)], now=START)
    changes = record_capability_snapshot(
        store, "s2", [_cap(CAP_KIND_PLUGIN, "demo", "b" * 64)], now=START + timedelta(hours=1)
    )
    rendered = render_capability_changes(changes).lower()
    for verdict in ("malicious", "malware", "suspicious", "caused", "attack"):
        assert verdict not in rendered


def test_cli_capabilities_snapshot_then_diff(tmp_path: Path, monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    home = tmp_path / "home"
    claude = home / ".claude"
    (claude / "skills" / "pdf").mkdir(parents=True)
    (claude / "skills" / "pdf" / "SKILL.md").write_text("v1\n")
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)

    base = ["--set", f"store.path={store_dir}", "inventory", "--capabilities"]
    assert main([*base, "--snapshot", "--session-id", "s1"]) == 0

    (claude / "skills" / "pdf" / "SKILL.md").write_text("v2 changed\n")
    assert main([*base, "--snapshot", "--session-id", "s2"]) == 0

    capsys.readouterr()
    assert main([*base, "--diff", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out
    assert out[0]["name"] == "pdf"
    assert out[0]["change"] == CHANGE_VERSION_UNCHANGED


def test_cli_capabilities_diff_since_filters(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    store = RecordStore(store_dir / "records.jsonl")
    record_capability_snapshot(store, "s1", [_cap(CAP_KIND_SKILL, "pdf", "a" * 64)], now=START)
    record_capability_snapshot(
        store, "s2", [_cap(CAP_KIND_SKILL, "pdf", "b" * 64)], now=START + timedelta(hours=1)
    )

    rc = main(
        [
            "--set",
            f"store.path={store_dir}",
            "inventory",
            "--capabilities",
            "--diff",
            "--since",
            "2099-01-01T00:00:00+00:00",
            "--json",
        ]
    )
    assert rc == 0
    assert json.loads(capsys.readouterr().out) == []
