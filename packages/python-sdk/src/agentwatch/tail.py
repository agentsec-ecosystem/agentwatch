"""``agentwatch tail``: read-only record stream (M5 C2, #176).

Prints one line per stored record, most recent last, e.g.
``14:03:12 · sess-9f2 · observe · Bash · ok · 42ms``. ``-f`` follows (1 s poll)
until interrupted; ``--session-id`` filters. The reader is read-only, honors the
store's permissions, and displays only fields already stored under the privacy
mode -- it never re-reads raw transcripts.

It tolerates a store being written concurrently (a partial final line is held
back until completed), tombstones, and malformed lines, which are skipped with
an inline note rather than crashing the stream.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from agentwatch.records import AgentRecord, RecordValidationError, validate_record


@dataclass(frozen=True)
class TailLine:
    """One rendered stream line, or a note about skipped input."""

    text: str
    is_note: bool = False
    record: AgentRecord | None = None


def render_record(record: AgentRecord) -> str:
    """Render one record in the documented one-line shape.

    The timestamp is local wall-clock with an **explicit UTC offset** (``HH:MM:SS+HHMM``)
    so a line read in another timezone is unambiguous.
    """
    stamp = record.started_at.astimezone().strftime("%H:%M:%S%z")
    step = record.step_type.value if record.step_type is not None else "-"
    duration = f"{record.duration_ms:.0f}ms" if record.duration_ms is not None else "-"
    approval = f" · approval={record.approval.value}" if record.approval is not None else ""
    return (
        f"{stamp} · {record.session_id} · {step} · "
        f"{record.tool.name} · {record.outcome.value} · {duration}{approval}"
    )


class Tail:
    """Incremental JSONL envelope reader with a byte cursor."""

    def __init__(
        self,
        path: Path | str,
        *,
        session_id: str | None = None,
        project: str | None = None,
    ) -> None:
        self.path = Path(path)
        self.session_id = session_id
        self.project = project
        self._offset = 0
        self._buffer = ""
        self._line = 0

    def read_new(self) -> list[TailLine]:
        """Read complete lines appended since the last call.

        A trailing fragment (a write in progress) stays buffered until its
        newline arrives, so a concurrent writer never yields a parse error.
        """
        if not self.path.exists():
            return []
        try:
            with self.path.open("rb") as handle:
                handle.seek(self._offset)
                chunk = handle.read()
                self._offset = handle.tell()
        except OSError:
            return []
        self._buffer += chunk.decode("utf-8", errors="replace")
        complete = self._buffer.split("\n")
        self._buffer = complete.pop()
        result: list[TailLine] = []
        for raw in complete:
            self._line += 1
            item = self._parse(raw, self._line)
            if item is not None:
                result.append(item)
        return result

    def _parse(self, raw: str, number: int) -> TailLine | None:
        if not raw.strip():
            return None
        try:
            envelope = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return TailLine(f"skipped malformed line {number}", is_note=True)
        if not isinstance(envelope, dict):
            return TailLine(f"skipped malformed line {number}", is_note=True)
        if "format" in envelope and "seq" not in envelope:
            return None  # store format marker, not a record
        if "seq" not in envelope:
            return TailLine(f"skipped malformed line {number}", is_note=True)
        seq = envelope.get("seq")
        if envelope.get("tombstone"):
            return TailLine(f"skipped tombstone seq {seq}", is_note=True)
        data = envelope.get("record")
        if data is None:
            return TailLine(f"skipped tombstone seq {seq}", is_note=True)
        try:
            record = validate_record(data)
        except RecordValidationError:
            return TailLine(f"skipped invalid record seq {seq}", is_note=True)
        if self.session_id is not None and record.session_id != self.session_id:
            return None
        if self.project is not None and record.project != self.project:
            return None
        return TailLine(render_record(record), record=record)


def follow(
    tail: Tail,
    *,
    poll_seconds: float = 1.0,
    max_polls: int | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Iterator[TailLine]:
    """Yield newly-appended lines, polling until interrupted (or ``max_polls``)."""
    polls = 0
    while max_polls is None or polls < max_polls:
        sleep(poll_seconds)
        yield from tail.read_new()
        polls += 1
