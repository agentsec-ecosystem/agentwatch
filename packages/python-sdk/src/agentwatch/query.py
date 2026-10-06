"""``agentwatch search``: filter stored records (M8 addition H3).

A small, pipe-friendly filter over the local store: records in, records out.
Accepts ``--tool``, ``--outcome``, ``--session``, and ``--since`` (relative like
``2d``/``12h``/``30m`` or an ISO timestamp). Read-only.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone, tzinfo

from agentwatch.identity import identity_handles
from agentwatch.records import AgentRecord, effective_approval, effective_producer
from agentwatch.store import RecordStore

_RELATIVE = re.compile(r"^(\d+)([smhd])$")
_UNIT = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def _system_local_tz() -> tzinfo:
    """The machine's local timezone (with DST rules when the platform provides them)."""
    return datetime.now().astimezone().tzinfo or timezone.utc


def since_cutoff(
    since: str,
    *,
    now: datetime | None = None,
    local_tz: tzinfo | None = None,
) -> datetime:
    """Resolve a relative (``2d``) or ISO-8601 ``since`` value to an aware cutoff.

    - Relative values (``30s``/``15m``/``12h``/``2d``) are exact durations subtracted
      from ``now`` (UTC by default), so they are DST-safe: a day is 24 hours.
    - ISO-8601 values with an offset (or a trailing ``Z``) are used as given.
    - ISO-8601 values **without** an offset are interpreted in the local timezone
      (``local_tz``, or the system zone) and returned aware, so a naive value never
      gets compared against a UTC record by accident.
    """
    moment = now or datetime.now(timezone.utc)
    text = since.strip()
    match = _RELATIVE.match(text)
    if match:
        amount = int(match.group(1))
        return moment - timedelta(seconds=amount * _UNIT[match.group(2)])
    # ``Z`` is only accepted by datetime.fromisoformat on 3.11+; normalize it so
    # the CLI behaves the same on 3.10 and 3.12.
    normalized = text[:-1] + "+00:00" if text[-1:] in {"Z", "z"} else text
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=local_tz or _system_local_tz())
    return parsed


def search(
    store: RecordStore,
    *,
    tool: str | None = None,
    outcome: str | None = None,
    session_id: str | None = None,
    since: str | None = None,
    project: str | None = None,
    producer: str | None = None,
    approval: str | None = None,
    identity: str | None = None,
    records: Iterable[AgentRecord] | None = None,
) -> list[AgentRecord]:
    """Return stored records matching every supplied filter, in store order.

    ``records`` overrides the source (M16 S28), so a caller can include archived
    segments in the search.
    """
    cutoff = since_cutoff(since) if since is not None else None
    result: list[AgentRecord] = []
    for record in records if records is not None else store.records():
        if tool is not None and record.tool.name != tool:
            continue
        if outcome is not None and record.outcome.value != outcome:
            continue
        if session_id is not None and record.session_id != session_id:
            continue
        if project is not None and record.project != project:
            continue
        if producer is not None and effective_producer(record).kind.value != producer:
            continue
        if approval is not None and effective_approval(record).value != approval:
            continue
        if identity is not None:
            needle = identity.strip().lower()
            if not needle or not any(
                needle in handle.lower() for handle in identity_handles(record.agent)
            ):
                continue
        if cutoff is not None and record.started_at < cutoff:
            continue
        result.append(record)
    return result
