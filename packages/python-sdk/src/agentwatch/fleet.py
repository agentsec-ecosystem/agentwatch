"""Fleet aggregation over multiple hosts (M11 R13).

Opt-in, self-hosted, local-first: a host's local record store is ingested into a
self-hosted aggregate store, each record tagged with its ``host``. Aggregation
then rolls records up by host/agent/version. Nothing leaves the machine (R6); no
enforcement, only observation (PRD 14/30).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentwatch.records import AgentRecord, Outcome
from agentwatch.store import RecordStore


@dataclass(frozen=True)
class FleetSource:
    """One host's local record store to ingest."""

    host: str
    records_path: Path


@dataclass(frozen=True)
class FleetIngestStats:
    """Outcome of ingesting one host (missing/duplicates are reported, never silent)."""

    host: str
    records: int
    skipped: int
    duplicates: int
    missing: bool = False


@dataclass(frozen=True)
class FleetRollup:
    """Aggregate over records sharing host/agent/version."""

    host: str | None
    agent: str
    version: str | None
    total: int
    ok: int
    error: int
    denied: int
    security_events: int
    avg_duration_ms: float | None


@dataclass(frozen=True)
class FleetSnapshot:
    """A fleet's hosts, total record count, and rollups."""

    hosts: tuple[str, ...]
    total_records: int
    rollups: tuple[FleetRollup, ...]


def parse_sources(specs: Iterable[str]) -> list[FleetSource]:
    """Parse ``HOST=PATH`` specs into :class:`FleetSource` values."""
    sources: list[FleetSource] = []
    for spec in specs:
        host, sep, path = spec.partition("=")
        host = host.strip()
        path = path.strip()
        if not sep or not host or not path:
            raise ValueError(f"invalid fleet source {spec!r}; expected HOST=PATH")
        sources.append(FleetSource(host=host, records_path=Path(path).expanduser()))
    return sources


def _dedup_key(record: AgentRecord) -> tuple[Any, ...]:
    if record.span_id is not None:
        return ("span", record.host, record.session_id, record.span_id)
    return (
        "record",
        record.host,
        record.session_id,
        record.started_at.isoformat(),
        record.tool.name,
    )


def ingest_host(source: FleetSource, store: RecordStore) -> FleetIngestStats:
    """Ingest one host store into ``store``, tagging records and deduping.

    Idempotent on ``(host, session_id, span_id)`` so re-ingesting a host does not
    inflate the aggregate. A record already carrying a different host is
    re-tagged to the source host.
    """
    if not source.records_path.exists():
        return FleetIngestStats(source.host, 0, 0, 0, missing=True)
    existing = {_dedup_key(record) for record in store.records()}
    records = skipped = duplicates = 0
    for record in RecordStore(source.records_path).records():
        tagged = (
            record if record.host == source.host else dataclasses.replace(record, host=source.host)
        )
        key = _dedup_key(tagged)
        if key in existing:
            duplicates += 1
            continue
        try:
            store.append(tagged)
        except ValueError:
            skipped += 1
        else:
            records += 1
            existing.add(key)
    return FleetIngestStats(source.host, records, skipped, duplicates)


def aggregate(records: Iterable[AgentRecord], *, group_by_host: bool = True) -> list[FleetRollup]:
    """Roll records up by host/agent/version, deterministically ordered."""
    buckets: dict[tuple[Any, ...], dict[str, Any]] = {}
    for record in records:
        key = (
            record.host if group_by_host else None,
            record.agent.identity,
            record.agent.version,
        )
        bucket = buckets.setdefault(
            key, {"total": 0, "ok": 0, "error": 0, "denied": 0, "events": 0, "durations": []}
        )
        bucket["total"] += 1
        if record.outcome is Outcome.OK:
            bucket["ok"] += 1
        elif record.outcome is Outcome.ERROR:
            bucket["error"] += 1
        elif record.outcome is Outcome.DENIED:
            bucket["denied"] += 1
        if record.security_event is not None:
            bucket["events"] += 1
        if record.duration_ms is not None:
            bucket["durations"].append(record.duration_ms)

    rollups: list[FleetRollup] = []
    for (host, agent, version), bucket in sorted(
        buckets.items(), key=lambda item: (str(item[0][0]), item[0][1], str(item[0][2]))
    ):
        durations = bucket["durations"]
        avg = sum(durations) / len(durations) if durations else None
        rollups.append(
            FleetRollup(
                host=host,
                agent=agent,
                version=version,
                total=bucket["total"],
                ok=bucket["ok"],
                error=bucket["error"],
                denied=bucket["denied"],
                security_events=bucket["events"],
                avg_duration_ms=avg,
            )
        )
    return rollups


def build_fleet(store: RecordStore, *, group_by_host: bool = True) -> FleetSnapshot:
    """Build a fleet snapshot from an aggregate store."""
    records = list(store.records())
    hosts = tuple(sorted({record.host for record in records if record.host is not None}))
    return FleetSnapshot(
        hosts=hosts,
        total_records=len(records),
        rollups=tuple(aggregate(records, group_by_host=group_by_host)),
    )


def render_fleet(snapshot: FleetSnapshot) -> str:
    """Render a snapshot as a tab-separated table."""
    lines = [
        f"fleet: {len(snapshot.hosts)} host(s), {snapshot.total_records} record(s)",
        "HOST\tAGENT\tVERSION\tTOTAL\tOK\tERROR\tDENIED\tSECURITY\tAVG_MS",
    ]
    for rollup in snapshot.rollups:
        avg = "-" if rollup.avg_duration_ms is None else f"{rollup.avg_duration_ms:.1f}"
        lines.append(
            f"{rollup.host or '-'}\t{rollup.agent}\t{rollup.version or '-'}\t"
            f"{rollup.total}\t{rollup.ok}\t{rollup.error}\t{rollup.denied}\t"
            f"{rollup.security_events}\t{avg}"
        )
    return "\n".join(lines)


def fleet_to_json(snapshot: FleetSnapshot) -> dict[str, Any]:
    """Serialize a snapshot for ``--json`` output."""
    return {
        "hosts": list(snapshot.hosts),
        "total_records": snapshot.total_records,
        "rollups": [
            {
                "host": rollup.host,
                "agent": rollup.agent,
                "version": rollup.version,
                "total": rollup.total,
                "ok": rollup.ok,
                "error": rollup.error,
                "denied": rollup.denied,
                "security_events": rollup.security_events,
                "avg_duration_ms": rollup.avg_duration_ms,
            }
            for rollup in snapshot.rollups
        ],
    }
