"""``agentwatch search``: filter stored records (M8 addition H3).

A small, pipe-friendly filter over the local store: records in, records out.
Accepts ``--tool``, ``--outcome``, ``--session``, and ``--since`` (relative like
``2d``/``12h``/``30m`` or an ISO timestamp). Read-only.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from agentwatch.records import AgentRecord
from agentwatch.store import RecordStore

_RELATIVE = re.compile(r"^(\d+)([smhd])$")
_UNIT = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def since_cutoff(since: str, *, now: datetime | None = None) -> datetime:
    """Resolve a relative (``2d``) or ISO-8601 ``since`` value to a UTC cutoff."""
    moment = now or datetime.now(timezone.utc)
    match = _RELATIVE.match(since.strip())
    if match:
        amount = int(match.group(1))
        return moment - timedelta(seconds=amount * _UNIT[match.group(2)])
    return datetime.fromisoformat(since)


def search(
    store: RecordStore,
    *,
    tool: str | None = None,
    outcome: str | None = None,
    session_id: str | None = None,
    since: str | None = None,
    project: str | None = None,
) -> list[AgentRecord]:
    """Return stored records matching every supplied filter, in store order."""
    cutoff = since_cutoff(since) if since is not None else None
    result: list[AgentRecord] = []
    for record in store.records():
        if tool is not None and record.tool.name != tool:
            continue
        if outcome is not None and record.outcome.value != outcome:
            continue
        if session_id is not None and record.session_id != session_id:
            continue
        if project is not None and record.project != project:
            continue
        if cutoff is not None and record.started_at < cutoff:
            continue
        result.append(record)
    return result
