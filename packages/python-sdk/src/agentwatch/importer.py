"""Import existing Claude Code transcripts (M8 addition H1).

Reads Claude Code's on-disk transcript JSONL (``~/.claude/projects/**/<id>.jsonl``)
and turns ``tool_use`` / ``tool_result`` pairs into records **through the same
adapter + redaction path** used for live hooks — so imported records obey the
configured privacy mode and secret masking before they ever touch the store
(DD-06). No egress; read-only on the transcript source.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from agentwatch.adapters.claude_code import HARNESS_ID, normalize
from agentwatch.records import AgentRecord, Producer, ProducerKind
from agentwatch.redact import RedactionConfig
from agentwatch.store import RecordStore

# Transcript import is weaker evidence than live capture (M15 S26).
IMPORT_PRODUCER = Producer(kind=ProducerKind.IMPORT, name="claude-code-transcript")


@dataclass(frozen=True)
class ImportStats:
    """Outcome of an import run (skips and duplicates are reported, never silent)."""

    files: int
    records: int
    skipped: int
    duplicates: int = 0


def _session_id(entry: Mapping[str, Any], fallback: str) -> str:
    for key in ("sessionId", "session_id"):
        value = entry.get(key)
        if isinstance(value, str) and value:
            return value
    return fallback


def _timestamp(entry: Mapping[str, Any]) -> str | None:
    value = entry.get("timestamp")
    return value if isinstance(value, str) else None


def _content(entry: Mapping[str, Any]) -> Any:
    message = entry.get("message")
    if isinstance(message, Mapping):
        return message.get("content")
    return entry.get("content")


def _pre_messages(entry: Mapping[str, Any], session_id: str) -> list[dict[str, Any]]:
    content = _content(entry)
    if not isinstance(content, list):
        return []
    messages: list[dict[str, Any]] = []
    for item in content:
        if not isinstance(item, Mapping) or item.get("type") != "tool_use":
            continue
        call_id = item.get("id") or item.get("tool_use_id")
        if not isinstance(call_id, str) or not call_id:
            call_id = f"toolu-{len(messages)}"
        messages.append(
            {
                "phase": "pre",
                "harness": HARNESS_ID,
                "event": {
                    "session_id": session_id,
                    "tool_name": item.get("name"),
                    "tool_input": item.get("input"),
                    "tool_use_id": call_id,
                    "timestamp": _timestamp(entry),
                },
            }
        )
    return messages


def _result_items(entry: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    content = _content(entry)
    if not isinstance(content, list):
        return []
    return [
        item for item in content if isinstance(item, Mapping) and item.get("type") == "tool_result"
    ]


def iter_records(
    paths: Iterable[Path],
    *,
    redaction: RedactionConfig | None = None,
) -> Iterator[AgentRecord]:
    """Yield records for ``tool_use`` / ``tool_result`` pairs across transcripts.

    A completed call yields one record (its result). A call with no result still
    yields its pre-record so no captured event is lost (PRD 17).
    """
    for path in paths:
        fallback = path.stem
        pending: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(entry, Mapping):
                    continue
                session_id = _session_id(entry, fallback)
                for message in _pre_messages(entry, session_id):
                    call_id = str(message["event"]["tool_use_id"])
                    pending[call_id] = message
                    order.append(call_id)
                for result in _result_items(entry):
                    result_call_id = result.get("tool_use_id")
                    if not isinstance(result_call_id, str) or result_call_id not in pending:
                        continue
                    pre = pending.pop(result_call_id)
                    event = dict(pre["event"])
                    response: dict[str, Any] = {"content": result.get("content")}
                    if result.get("is_error"):
                        response["is_error"] = True
                    event["tool_response"] = response
                    yield from (
                        replace(record, producer=IMPORT_PRODUCER)
                        for record in normalize(
                            {"phase": "post", "harness": HARNESS_ID, "event": event},
                            redaction=redaction,
                        )
                    )
        for call_id in order:
            if call_id in pending:
                yield from (
                    replace(record, producer=IMPORT_PRODUCER)
                    for record in normalize(pending[call_id], redaction=redaction)
                )


def import_transcripts(
    paths: Iterable[Path],
    store: RecordStore,
    *,
    redaction: RedactionConfig | None = None,
) -> ImportStats:
    """Import transcripts into ``store``; returns counts (skips/dupes reported).

    Idempotent: a record whose ``(session_id, span_id)`` is already stored is
    counted as a duplicate and not appended again, so re-importing a transcript
    does not inflate the store.
    """
    files = 0
    records = 0
    skipped = 0
    duplicates = 0
    existing = {(record.session_id, record.span_id) for record in store.records()}
    for path in paths:
        files += 1
        try:
            for record in iter_records([path], redaction=redaction):
                key = (record.session_id, record.span_id)
                if record.span_id is not None and key in existing:
                    duplicates += 1
                    continue
                try:
                    store.append(record)
                except ValueError:
                    skipped += 1
                else:
                    records += 1
                    existing.add(key)
        except OSError:
            skipped += 1
    return ImportStats(files=files, records=records, skipped=skipped, duplicates=duplicates)


def resolve_paths(target: Path) -> list[Path]:
    """Resolve a transcript file or a directory of ``*.jsonl`` files."""
    if target.is_dir():
        return sorted(target.rglob("*.jsonl"))
    return [target]
