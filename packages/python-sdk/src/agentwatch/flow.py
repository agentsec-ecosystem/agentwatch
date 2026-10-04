"""Untrusted content → argument flow capture (M18 S22, PRD 34).

When a captured tool *response* contains content that later reappears in a tool
*argument*, that is a deterministic data-flow fact: content entered at one record
and left as an instruction at a later one. This module fingerprints response
content in normalized word-n-gram shards with a **per-install keyed HMAC** and
matches later arguments against them.

It is a flow fact and nothing more: no "injection", no score, no block (PRD 14).
Fingerprints are keyed so the store holds no recovered content.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentwatch import posture
from agentwatch.records import (
    AgentIdentity,
    AgentRecord,
    Outcome,
    RecordPrivacyMode,
    ToolCall,
)
from agentwatch.store import MARKER_PRODUCER, RecordStore

FLOW_TOOL = "content-flow"
HMAC_KEY_ENV = "AGENTWATCH_HMAC_KEY"
KEY_FILENAME = "flow.key"

SHARD_WORDS = 5
MIN_SHARD_CHARS = 20
MAX_SHARDS_PER_TEXT = 256
MAX_RESPONSE_CHARS = 200_000
MAX_FANOUT = 8

_NON_WORD = re.compile(r"[^a-z0-9]+")

# None = not looked up yet; b"" = looked up, no key available.
_file_key: bytes | None = None
_file_key_loaded = False


# ---------------------------------------------------------------------------
# Per-install keyed HMAC
# ---------------------------------------------------------------------------


def default_key_path() -> Path:
    """The per-install key path under the configured store directory."""
    from agentwatch.configuration import load_config

    return Path(load_config().store.path).expanduser() / KEY_FILENAME


def _load_file_key(*, create: bool) -> bytes | None:
    global _file_key, _file_key_loaded
    if _file_key_loaded and not create:
        return _file_key or None
    path = default_key_path()
    if path.exists():
        try:
            data = path.read_bytes().strip()
        except OSError:  # pragma: no cover - unreadable key file
            data = b""
        if data:
            _file_key = data
            _file_key_loaded = True
            return data
    if not create:
        _file_key = None
        _file_key_loaded = True
        return None
    posture.secure_dir(path.parent)
    data = os.urandom(32)
    path.write_bytes(data)
    posture.secure_file(path)
    _file_key = data
    _file_key_loaded = True
    return data


def ensure_key() -> bytes:
    """Create/load the per-install HMAC key (owner-only)."""
    key = _load_file_key(create=True)
    assert key is not None
    return key


def ensure_key_at(path: Path) -> bytes:
    """Create/load a key at an explicit path (used by the CLI's resolved store)."""
    if path.exists():
        try:
            data = path.read_bytes().strip()
        except OSError:  # pragma: no cover - unreadable key file
            data = b""
        if data:
            return data
    posture.secure_dir(path.parent)
    data = os.urandom(32)
    path.write_bytes(data)
    posture.secure_file(path)
    return data


def hmac_key_or_none() -> bytes | None:
    """The per-install key if available, else ``None`` (never creates one here)."""
    env = os.environ.get(HMAC_KEY_ENV)
    if env:
        return env.encode("utf-8")
    return _load_file_key(create=False)


def fingerprint(value: str, *, key: bytes | None = None) -> str:
    """A stable keyed ``HMAC-SHA256`` hex prefix for ``value``, or "" if no key."""
    if not value:
        return ""
    resolved = key if key is not None else hmac_key_or_none()
    if not resolved:
        return ""
    return hmac.new(resolved, value.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Shards
# ---------------------------------------------------------------------------


def normalize_text(text: str) -> str:
    """Lowercase and collapse everything non-alphanumeric to single spaces."""
    return _NON_WORD.sub(" ", text.lower()).strip()


def shards(text: str) -> tuple[str, ...]:
    """Normalized word-n-gram shards (deterministic, capped, no content stored)."""
    words = normalize_text(text).split()
    if len(words) < SHARD_WORDS:
        return ()
    result: list[str] = []
    seen: set[str] = set()
    for index in range(len(words) - SHARD_WORDS + 1):
        shard = " ".join(words[index : index + SHARD_WORDS])
        if len(shard) < MIN_SHARD_CHARS or shard in seen:
            continue
        seen.add(shard)
        result.append(shard)
        if len(result) >= MAX_SHARDS_PER_TEXT:
            break
    return tuple(result)


def shard_fingerprints(text: str, *, key: bytes | None = None) -> tuple[tuple[str, int], ...]:
    """``(fingerprint, char_length)`` for each shard of ``text``."""
    result: list[tuple[str, int]] = []
    for shard in shards(text):
        shard_fp = fingerprint(shard, key=key)
        if shard_fp:
            result.append((shard_fp, len(shard)))
    return tuple(result)


def flatten_strings(value: Any) -> Iterator[str]:
    """Yield every string in a JSON-shaped value."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from flatten_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from flatten_strings(item)


def source_class(tool_name: str, server: str | None) -> str:
    """The provenance class of a response: web | file | mcp | tool-output."""
    if server is not None:
        return "mcp"
    name = tool_name.lower()
    if name in {"webfetch", "websearch"}:
        return "web"
    if name in {"read", "glob", "grep", "ls", "view"}:
        return "file"
    return "tool-output"


# ---------------------------------------------------------------------------
# Flow detection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContentFlow:
    """One content → argument edge (fingerprints only; never content)."""

    session_id: str
    source_index: int
    sink_index: int
    source_class: str
    source_tool: str
    sink_tool: str
    matched_len: int
    fingerprint: str
    matches: int = 1

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "source_index": self.source_index,
            "sink_index": self.sink_index,
            "source_class": self.source_class,
            "source_tool": self.source_tool,
            "sink_tool": self.sink_tool,
            "matched_len": self.matched_len,
            "fingerprint": self.fingerprint,
            "matches": self.matches,
        }


def detect_flows(
    records: Sequence[AgentRecord],
    *,
    key: bytes | None = None,
    fanout: int = MAX_FANOUT,
) -> tuple[ContentFlow, ...]:
    """Detect content → argument edges across an ordered record sequence."""
    index: dict[str, tuple[int, str, str, int]] = {}
    found: dict[tuple[int, int], dict[str, Any]] = {}
    fanout_used: dict[str, int] = {}

    for position, record in enumerate(records):
        if record.tool.arguments is not None:
            for text in flatten_strings(record.tool.arguments):
                for shard_fp, length in shard_fingerprints(text, key=key):
                    source = index.get(shard_fp)
                    if source is None:
                        continue
                    source_index, source_class_name, source_tool, source_len = source
                    if source_index >= position:
                        continue
                    if fanout_used.get(shard_fp, 0) >= fanout:
                        continue
                    fanout_used[shard_fp] = fanout_used.get(shard_fp, 0) + 1
                    pair = (source_index, position)
                    entry = found.get(pair)
                    if entry is None:
                        found[pair] = {
                            "source_class": source_class_name,
                            "source_tool": source_tool,
                            "sink_tool": record.tool.name,
                            "matched_len": min(length, source_len),
                            "fingerprint": shard_fp,
                            "matches": 1,
                        }
                    else:
                        entry["matches"] += 1
                        entry["matched_len"] = max(entry["matched_len"], min(length, source_len))

        if record.tool.response is not None:
            class_name = source_class(record.tool.name, record.tool.server)
            for text in flatten_strings(record.tool.response):
                capped = text[:MAX_RESPONSE_CHARS]
                for shard_fp, length in shard_fingerprints(capped, key=key):
                    index.setdefault(shard_fp, (position, class_name, record.tool.name, length))

    flows = [
        ContentFlow(
            session_id=records[pair[0]].session_id,
            source_index=pair[0],
            sink_index=pair[1],
            source_class=entry["source_class"],
            source_tool=entry["source_tool"],
            sink_tool=entry["sink_tool"],
            matched_len=entry["matched_len"],
            fingerprint=entry["fingerprint"],
            matches=entry["matches"],
        )
        for pair, entry in found.items()
    ]
    flows.sort(key=lambda flow: (flow.source_index, flow.sink_index))
    return tuple(flows)


def record_flow_observations(
    store: RecordStore,
    flows: Sequence[ContentFlow],
    *,
    now: datetime | None = None,
) -> int:
    """Append one metadata-only ``content-flow`` marker per edge (fingerprints only)."""
    moment = now or datetime.now(timezone.utc)
    count = 0
    for flow in flows:
        store.append(
            AgentRecord(
                session_id=flow.session_id,
                agent=AgentIdentity(identity="agentwatch"),
                tool=ToolCall(
                    name=FLOW_TOOL,
                    arguments={
                        "source_index": flow.source_index,
                        "sink_index": flow.sink_index,
                        "source_class": flow.source_class,
                        "source_tool": flow.source_tool,
                        "sink_tool": flow.sink_tool,
                        "matched_len": flow.matched_len,
                        "fingerprint": flow.fingerprint,
                        "matches": flow.matches,
                    },
                    privacy_mode=RecordPrivacyMode.METADATA_ONLY,
                ),
                outcome=Outcome.OK,
                started_at=moment,
                producer=MARKER_PRODUCER,
            )
        )
        count += 1
    return count


def content_flow_observations(store: RecordStore) -> list[ContentFlow]:
    """Every stored ``content-flow`` observation, in store order."""
    flows: list[ContentFlow] = []
    for entry in store.entries():
        record = entry.record
        if record is None or record.tool.name != FLOW_TOOL:
            continue
        arguments = record.tool.arguments or {}
        flows.append(
            ContentFlow(
                session_id=record.session_id,
                source_index=int(arguments.get("source_index", 0)),
                sink_index=int(arguments.get("sink_index", 0)),
                source_class=str(arguments.get("source_class", "")),
                source_tool=str(arguments.get("source_tool", "")),
                sink_tool=str(arguments.get("sink_tool", "")),
                matched_len=int(arguments.get("matched_len", 0)),
                fingerprint=str(arguments.get("fingerprint", "")),
                matches=int(arguments.get("matches", 1)),
            )
        )
    return flows


def render_flows(session_id: str, flows: Sequence[ContentFlow]) -> str:
    """Render a content-flow graph (fingerprints only; never content)."""
    lines = [f"agentwatch flow {session_id}"]
    if not flows:
        lines.append("  no content-flow edges (responses may be uncaptured)")
        return "\n".join(lines)
    for flow in flows:
        lines.append(
            f"  #{flow.source_index} {flow.source_class}:{flow.source_tool} "
            f"-> #{flow.sink_index} {flow.sink_tool} "
            f"({flow.matched_len} chars, {flow.matches} shard match(es), fp {flow.fingerprint})"
        )
    return "\n".join(lines)


__all__ = [
    "FLOW_TOOL",
    "HMAC_KEY_ENV",
    "ContentFlow",
    "content_flow_observations",
    "default_key_path",
    "detect_flows",
    "ensure_key",
    "ensure_key_at",
    "fingerprint",
    "flatten_strings",
    "hmac_key_or_none",
    "normalize_text",
    "record_flow_observations",
    "render_flows",
    "shard_fingerprints",
    "shards",
    "source_class",
]
