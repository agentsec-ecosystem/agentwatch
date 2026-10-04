"""Property tests for time correctness (PRD 38 §Q12, issue #229).

Times are stored and compared in UTC; relative ``--since`` values are exact
durations; naive ISO values are interpreted locally and returned aware; local
rendering carries an explicit offset. These properties hold across DST
boundaries and a non-UTC default zone.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from hypothesis import given, settings
from hypothesis import strategies as st

from agentwatch.drift import metric_series
from agentwatch.query import search, since_cutoff
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall, _iso, _parse_iso
from agentwatch.store import RecordStore
from agentwatch.tail import render_record

UTC = timezone.utc
NEW_YORK = ZoneInfo("America/New_York")
_UNIT = {"s": 1, "m": 60, "h": 3600, "d": 86400}

# A modern range avoids pre-1970 zones with sub-minute (LMT) offsets, which are
# real but not the failure modes this suite targets.
_MODERN_UTC = st.datetimes(
    min_value=datetime(2000, 1, 1), max_value=datetime(2030, 1, 1), timezones=st.just(UTC)
)
_MODERN_AWARE = st.datetimes(
    min_value=datetime(2000, 1, 1), max_value=datetime(2030, 1, 1), timezones=st.timezones()
)
_OFFSET = re.compile(r"^\d{2}:\d{2}:\d{2}[+-]\d{4,6}$")


def _record(when: datetime, name: str = "Bash", session: str = "s") -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name=name),
        outcome=Outcome.OK,
        started_at=when,
    )


# --- --since parsing -------------------------------------------------------


@given(
    st.integers(min_value=0, max_value=100_000),
    st.sampled_from("smhd"),
    _MODERN_UTC,
)
@settings(max_examples=200)
def test_relative_since_is_an_exact_utc_duration(
    amount: int, unit: str, now: datetime
) -> None:
    cutoff = since_cutoff(f"{amount}{unit}", now=now)

    assert cutoff == now - timedelta(seconds=amount * _UNIT[unit])
    assert cutoff.utcoffset() == timedelta(0)


@given(_MODERN_AWARE)
def test_iso_with_an_offset_is_the_same_instant(when: datetime) -> None:
    assert since_cutoff(when.isoformat()).astimezone(UTC) == when.astimezone(UTC)


def test_iso_z_suffix_is_utc() -> None:
    assert since_cutoff("2026-03-08T06:30:00Z") == datetime(2026, 3, 8, 6, 30, tzinfo=UTC)


def test_naive_iso_uses_the_local_zone() -> None:
    cutoff = since_cutoff("2026-07-15T12:00:00", local_tz=NEW_YORK)

    assert cutoff == datetime(2026, 7, 15, 12, 0, tzinfo=NEW_YORK)
    assert cutoff.utcoffset() == timedelta(hours=-4)  # EDT


def test_naive_local_day_boundaries_track_dst() -> None:
    winter = since_cutoff("2026-01-15", local_tz=NEW_YORK)
    summer = since_cutoff("2026-07-15", local_tz=NEW_YORK)

    assert winter.utcoffset() == timedelta(hours=-5)
    assert summer.utcoffset() == timedelta(hours=-4)


def test_relative_day_is_exactly_24_hours_across_dst() -> None:
    # 2026-03-08 is the US spring-forward; a relative day must not become 23 h.
    now = datetime(2026, 3, 9, 12, 0, tzinfo=UTC)
    assert since_cutoff("1d", now=now) == now - timedelta(hours=24)


def test_relative_default_now_is_utc() -> None:
    before = datetime.now(UTC)
    cutoff = since_cutoff("90m")
    after = datetime.now(UTC)

    assert cutoff.utcoffset() == timedelta(0)
    assert before - timedelta(minutes=90) <= cutoff <= after - timedelta(minutes=90)


def test_naive_iso_cutoff_is_aware_and_safe_to_compare() -> None:
    cutoff = since_cutoff("2026-01-02T00:00:00", local_tz=UTC)

    assert cutoff.tzinfo is not None
    assert (_record(datetime(2026, 1, 1, tzinfo=UTC)).started_at < cutoff) is True
    assert (_record(datetime(2026, 1, 3, tzinfo=UTC)).started_at < cutoff) is False


def test_search_since_boundary_keeps_the_cutoff_instant(tmp_path: Path) -> None:
    boundary = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    store = RecordStore(tmp_path / "records.jsonl", durability="none")
    store.append(_record(boundary - timedelta(seconds=1), name="before"))
    store.append(_record(boundary, name="at"))
    store.append(_record(boundary + timedelta(seconds=1), name="after"))

    found = search(store, since="2026-06-01T12:00:00+00:00")

    assert [record.tool.name for record in found] == ["at", "after"]


# --- storage and comparison are UTC ---------------------------------------


@given(_MODERN_AWARE)
def test_iso_storage_is_utc_and_round_trips(when: datetime) -> None:
    text = _iso(when)
    parsed = _parse_iso(text)

    assert text.endswith("+00:00")
    assert parsed.astimezone(UTC) == when.astimezone(UTC)
    assert parsed.utcoffset() == timedelta(0)


def test_records_persist_and_reload_as_utc(tmp_path: Path) -> None:
    when = datetime(2026, 7, 15, 12, 0, tzinfo=NEW_YORK)
    path = tmp_path / "records.jsonl"
    RecordStore(path, durability="none").append(_record(when))

    reloaded = RecordStore(path, durability="none").records()[0].started_at

    assert reloaded.utcoffset() == timedelta(0)
    assert reloaded == when


# --- bucketing and retention ----------------------------------------------


def test_hour_buckets_are_utc_hours_across_dst() -> None:
    # 06:30Z and 07:30Z straddle the US spring-forward in local time, but the
    # buckets are UTC hours and must stay distinct.
    samples = metric_series(
        [
            _record(datetime(2026, 3, 8, 6, 30, tzinfo=UTC)),
            _record(datetime(2026, 3, 8, 7, 30, tzinfo=UTC)),
        ],
        "records",
        bucket="hour",
    )

    keys = sorted(sample.at for sample in samples)
    assert keys == [
        datetime(2026, 3, 8, 6, 0, tzinfo=UTC),
        datetime(2026, 3, 8, 7, 0, tzinfo=UTC),
    ]
    assert all(key.utcoffset() == timedelta(0) for key in keys)


@given(_MODERN_UTC)
def test_hour_bucket_normalizes_to_the_top_of_the_utc_hour(when: datetime) -> None:
    sample = metric_series([_record(when)], "records", bucket="hour")[0]

    assert sample.at == when.replace(minute=0, second=0, microsecond=0)
    assert sample.at.utcoffset() == timedelta(0)


def test_retention_boundary_is_strict_and_utc(tmp_path: Path) -> None:
    now = datetime(2026, 3, 9, 12, 0, tzinfo=UTC)
    path = tmp_path / "records.jsonl"
    store = RecordStore(path, durability="none")
    store.append(_record(now - timedelta(days=30) - timedelta(seconds=1), name="old"))
    store.append(_record(now - timedelta(days=30), name="edge"))
    store.append(_record(now - timedelta(days=29), name="new"))

    report = store.apply_retention(retention_days=30, now=now)
    kept = [record.tool.name for record in RecordStore(path, durability="none").records()]

    assert report.purged == 1
    assert set(kept) == {"edge", "new"}


# --- rendering ------------------------------------------------------------


@given(_MODERN_AWARE)
def test_render_record_has_an_explicit_offset(when: datetime) -> None:
    stamp = render_record(_record(when)).split(" · ")[0]

    assert _OFFSET.match(stamp), stamp
