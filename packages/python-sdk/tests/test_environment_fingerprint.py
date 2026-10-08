"""Environment fingerprint + delta (M30 ENV-1, #472; PRD 57).

Each session carries a content-free environment fingerprint (model, harness,
permission mode, capability digests, rules digest, MCP surface, config digest);
``diff`` shows the environment delta beside the behavior delta and ``drift``
annotates a shift with environment changes in the same window — wording
"coincides with", never "caused by". Absent facts are ``unknown``.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from agentwatch.capabilities import (
    CAP_KIND_SKILL,
    SCOPE_USER,
    Capability,
    snapshot_records,
)
from agentwatch.cli.main import main
from agentwatch.diff import diff_sessions
from agentwatch.env_fingerprint import (
    UNKNOWN,
    annotate_environment,
    environment_changes,
    environment_delta,
    environment_fingerprint,
    group_sessions_by_env,
    render_env_groups,
    session_environments,
)
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    StepType,
    ToolCall,
)
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _rec(
    session: str,
    *,
    model: str | None = None,
    harness: str | None = "claude-code",
    minute: int = 0,
    tool: str = "Read",
) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="a", model_version=model),
        tool=ToolCall(name=tool),
        outcome=Outcome.OK,
        started_at=START + timedelta(minutes=minute),
        harness=harness,
        step_type=StepType.ACT,
    )


def _cap(kind: str, name: str, digest: str) -> Capability:
    return Capability(kind=kind, name=name, scope=SCOPE_USER, digest=digest, size=1)


def test_fingerprint_is_stable_when_unchanged() -> None:
    first = environment_fingerprint([_rec("s1", model="claude-x-1")])
    second = environment_fingerprint([_rec("s1", model="claude-x-1")])
    assert first.digest() == second.digest()


def test_fingerprint_changes_on_a_component_change() -> None:
    a = environment_fingerprint([_rec("s1", model="claude-x-1")])
    b = environment_fingerprint([_rec("s1", model="claude-x-2")])
    assert a.digest() != b.digest()
    changes = environment_delta(a, b)
    assert changes[0].field == "model"
    assert (changes[0].a, changes[0].b) == ("claude-x-1", "claude-x-2")


def test_absent_facts_are_unknown_never_inferred() -> None:
    fingerprint = environment_fingerprint([_rec("s1", model=None, harness=None)])
    assert fingerprint.model == UNKNOWN
    assert fingerprint.harness == UNKNOWN
    assert fingerprint.permission_mode == UNKNOWN


def test_capability_digests_are_part_of_the_fingerprint() -> None:
    snapshot_a = snapshot_records("s1", [_cap(CAP_KIND_SKILL, "pdf", "a" * 64)], at=START)
    snapshot_b = snapshot_records("s1", [_cap(CAP_KIND_SKILL, "pdf", "b" * 64)], at=START)
    a = environment_fingerprint(snapshot_a)
    b = environment_fingerprint(snapshot_b)
    assert a.capabilities != UNKNOWN
    assert a.digest() != b.digest()


def test_diff_surfaces_environment_then_behavior(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_rec("a", model="claude-x-1", minute=0, tool="Read"))
    store.append(_rec("b", model="claude-x-2", minute=1, tool="Write"))

    result = diff_sessions(store, "a", "b")

    assert [change.field for change in result.environment_changes] == ["model"]
    rendered = result.render()
    assert "environment:" in rendered
    assert "model: claude-x-1 -> claude-x-2" in rendered
    # Environment delta is above the behavior delta.
    assert rendered.index("environment:") < rendered.index("records:")
    for verdict in ("caused", "because", "due to"):
        assert verdict not in rendered.lower()


def test_group_sessions_by_environment(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_rec("s1", model="claude-x-1", minute=0))
    store.append(_rec("s2", model="claude-x-1", minute=1))
    store.append(_rec("s3", model="claude-x-2", minute=2))

    groups = group_sessions_by_env(store)

    assert sorted(len(sessions) for sessions in groups.values()) == [1, 2]
    assert "ENV" in render_env_groups(groups)


def test_environment_changes_are_dated_for_drift_annotation(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_rec("s1", model="claude-x-1", minute=0))
    store.append(_rec("s2", model="claude-x-2", minute=10))

    environments = session_environments(store)
    dated = environment_changes(environments)

    assert dated and dated[0].change.field == "model"
    annotated = annotate_environment(
        signal_at=dated[-1].at, changes=dated, window_seconds=3600
    )
    assert [change.field for change in annotated] == ["model"]


def test_cli_sessions_group_by_env(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_rec("s1", model="claude-x-1", minute=0))
    store.append(_rec("s2", model="claude-x-2", minute=1))

    rc = main(["--set", f"store.path={tmp_path}", "sessions", "--group-by-env"])

    assert rc == 0
    assert "ENV" in capsys.readouterr().out


def test_cli_drift_annotates_coincident_environment(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    store = RecordStore(tmp_path / "records.jsonl")
    # A stable series (1/2 records per session), then a spike, with a model
    # change arriving in the spike session.
    for index in range(10):
        records = 1 if index % 2 == 0 else 2
        for _ in range(records):
            store.append(_rec(f"s{index}", model="claude-x-1", minute=index))
    for _ in range(20):
        store.append(_rec("spike", model="claude-x-2", minute=20))

    rc = main(
        [
            "--set",
            f"store.path={tmp_path}",
            "drift",
            "--metric",
            "records",
            "--json",
        ]
    )

    assert rc == 0
    document = json.loads(capsys.readouterr().out)
    assert document["signals"]

    rc = main(["--set", f"store.path={tmp_path}", "drift", "--metric", "records"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "coincides with" in out
    assert "caused" not in out.lower()
