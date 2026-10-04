"""``agentwatch demo`` tests (M19 S31, #259)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentwatch.cli.main import main
from agentwatch.coverage import is_tool_call_record
from agentwatch.demo import purge_demo, render_demo, run_demo
from agentwatch.records import ProducerKind, effective_producer
from agentwatch.store import RecordStore

# Built at runtime so no provider-shaped literal sits in the source.
SECRET = "sk-" + "abcdefghijklmnop"


def test_run_demo_records_chain_and_redaction(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")

    result = run_demo(store, cwd=str(tmp_path))

    assert result.chain_ok is True
    assert result.records
    assert all(effective_producer(record).kind is ProducerKind.DEMO for record in result.records)
    assert "api-key" in result.redaction_kinds
    assert result.denied == 1
    assert result.errored == 1
    # The synthetic secret is redacted before storage.
    assert SECRET not in store.path.read_text(encoding="utf-8")


def test_purge_removes_only_demo_records(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    run_demo(store, cwd=str(tmp_path))
    assert any(effective_producer(r).kind is ProducerKind.DEMO for r in store.records())

    purged = purge_demo(store)

    assert purged > 0
    assert not any(effective_producer(r).kind is ProducerKind.DEMO for r in store.records())
    assert store.verify().ok is True


def test_run_demo_replaced_on_rerun(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    run_demo(store, cwd=str(tmp_path))
    first = sum(1 for r in store.records() if effective_producer(r).kind is ProducerKind.DEMO)

    run_demo(store, cwd=str(tmp_path))
    second = sum(1 for r in store.records() if effective_producer(r).kind is ProducerKind.DEMO)

    assert first == second


def test_demo_records_are_excluded_from_coverage(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    result = run_demo(store, cwd=str(tmp_path))

    assert result.records
    assert all(not is_tool_call_record(record) for record in result.records)


def test_demo_excluded_from_evidence_bundle(tmp_path: Path) -> None:
    from agentwatch.evidence import build_bundle

    store = RecordStore(tmp_path / "records.jsonl")
    run_demo(store, cwd=str(tmp_path))

    bundle = build_bundle(store, store.path, "demo")

    # Every demo row is dropped: the records member holds no rows.
    assert bundle.members["records.ndjson"] == b"\n"


def test_render_demo_has_no_secret(tmp_path: Path) -> None:
    store = RecordStore(tmp_path / "records.jsonl")
    result = run_demo(store, cwd=str(tmp_path))

    text = render_demo(result)

    assert "pipeline proof" in text
    assert "chain: intact" in text
    assert SECRET not in text


def test_cli_demo_runs_then_purges(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()

    rc = main(["--set", f"store.path={store_dir}", "demo", "--json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["chain"]["ok"] is True
    assert payload["redaction_kinds"] == ["api-key"]

    rc = main(["--set", f"store.path={store_dir}", "demo", "--purge", "--json"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["purged"] > 0

    store = RecordStore(store_dir / "records.jsonl")
    assert not any(
        effective_producer(record).kind is ProducerKind.DEMO for record in store.records()
    )
