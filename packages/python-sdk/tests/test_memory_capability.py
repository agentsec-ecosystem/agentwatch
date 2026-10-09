"""Memory stores as capabilities (M30 MEM-1, #461; PRD 52).

Persistent memory is a cross-session poisoning path (OWASP ASI06). A memory
store is inventoried like any other capability — **digest** (content, never
stored), size, last-changed — and each change is attributed to the session that
recorded the write. A change no recorded session wrote is flagged
**unattributed**. A per-harness memory-exposure matrix is published.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agentwatch.capabilities import (
    CAP_KIND_MEMORY,
    COVERAGE_NONE,
    COVERAGE_PARTIAL,
    discover_capabilities,
)
from agentwatch.memory import (
    MEMORY_CHANGE_CHANGED,
    MEMORY_EXPOSURE,
    attribute_memory_store,
    detect_memory_changes,
    discover_memory_capabilities,
    discover_memory_stores,
    memory_exposure_matrix,
    record_memory,
)
from agentwatch.query import search
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _home_with_memory(tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "home"
    memory = home / ".claude" / "memory"
    memory.mkdir(parents=True)
    (memory / "notes.md").write_text("remember the milk\n")
    return home, memory


def test_discover_memory_stores_digest_size_last_changed(tmp_path) -> None:  # type: ignore[no-untyped-def]
    home, _memory = _home_with_memory(tmp_path)
    stores = discover_memory_stores(home=home, project=None)

    assert len(stores) == 1
    store = stores[0]
    assert store.name == "notes"
    assert store.scope == "user"
    assert len(store.digest) == 64
    assert store.size == len("remember the milk\n")
    assert isinstance(store.last_changed, datetime)


def test_memory_store_is_a_capability(tmp_path) -> None:  # type: ignore[no-untyped-def]
    home, _memory = _home_with_memory(tmp_path)
    capabilities = discover_memory_capabilities(home=home, project=None)
    assert [cap.kind for cap in capabilities] == [CAP_KIND_MEMORY]
    assert capabilities[0].name == "notes"


def test_memory_stores_appear_in_the_capability_inventory(tmp_path) -> None:  # type: ignore[no-untyped-def]
    home, _memory = _home_with_memory(tmp_path)
    inventory = discover_capabilities(project=tmp_path / "absent", home=home)
    assert CAP_KIND_MEMORY in {cap.kind for cap in inventory.capabilities}


def test_change_attributes_to_the_writer_session(tmp_path) -> None:  # type: ignore[no-untyped-def]
    home, memory = _home_with_memory(tmp_path)
    before = discover_memory_stores(home=home, project=None)

    store = RecordStore(tmp_path / "records.jsonl")
    record_memory(store, "s1", "write", key=str(memory / "notes.md"), now=START)
    (memory / "notes.md").write_text("remember the milk and eggs\n")
    after = discover_memory_stores(home=home, project=None)

    changes = detect_memory_changes(before, after, store.records())
    assert len(changes) == 1
    assert changes[0].change == MEMORY_CHANGE_CHANGED
    assert changes[0].attributed_session == "s1"
    assert changes[0].is_unattributed() is False


def test_out_of_band_edit_is_flagged_unattributed(tmp_path) -> None:  # type: ignore[no-untyped-def]
    home, memory = _home_with_memory(tmp_path)
    before = discover_memory_stores(home=home, project=None)
    (memory / "notes.md").write_text("poisoned out of band\n")
    after = discover_memory_stores(home=home, project=None)

    changes = detect_memory_changes(before, after, records=[])
    assert changes[0].attributed_session is None
    assert changes[0].is_unattributed() is True


def test_attribute_memory_store_matches_a_write(tmp_path) -> None:  # type: ignore[no-untyped-def]
    home, memory = _home_with_memory(tmp_path)
    mem_store = discover_memory_stores(home=home, project=None)[0]
    store = RecordStore(tmp_path / "records.jsonl")
    record_memory(store, "s1", "write", key="notes", now=START)

    assert attribute_memory_store(mem_store, store.records()) == "s1"
    assert attribute_memory_store(mem_store, []) is None


def test_search_memory_store_returns_the_following_session(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = RecordStore(tmp_path / "records.jsonl")
    store.append(_tool("s1", "Read", minute=0))
    record_memory(store, "s1", "write", key="notes", now=START.replace(minute=5))
    store.append(_tool("s1", "Write", minute=10))
    store.append(_tool("s2", "Read", minute=20))

    results = search(store, memory_store="notes")

    names = [(record.session_id, record.tool.name) for record in results]
    assert ("s1", "memory") in names
    assert ("s1", "Write") in names
    assert ("s1", "Read") not in names
    assert all(session != "s2" for session, _ in names)


def test_exposure_matrix_is_published_and_honest() -> None:
    matrix = memory_exposure_matrix()
    assert {row.harness for row in matrix} == {"claude-code", "cursor", "codex-cli", "gemini-cli"}
    assert next(row for row in matrix if row.harness == "claude-code").status == COVERAGE_PARTIAL
    assert next(row for row in matrix if row.harness == "cursor").status == COVERAGE_NONE

    from pathlib import Path

    doc = (
        Path(__file__).resolve().parents[3] / "docs" / "design" / "capability-supply-chain.md"
    ).read_text(encoding="utf-8")
    assert "Memory exposure" in doc
    for row in MEMORY_EXPOSURE:
        assert row.harness in doc
        assert row.status in doc


def test_memory_content_is_never_stored(tmp_path) -> None:  # type: ignore[no-untyped-def]
    home, memory = _home_with_memory(tmp_path)
    secret = "SUPERSECRET-MEMORY-TOKEN"
    (memory / "notes.md").write_text(f"payload {secret}\n")

    capabilities = discover_memory_capabilities(home=home, project=None)
    rendered = json.dumps([cap.to_dict() for cap in capabilities])
    assert secret not in rendered


def _tool(session: str, name: str, *, minute: int) -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name=name),
        outcome=Outcome.OK,
        started_at=START.replace(minute=minute),
    )
