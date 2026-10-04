# Reference — Time (v0.1.0)

**BLUF:** Times are **stored and compared in UTC**; times are **rendered in local time with an explicit UTC
offset**. `--since` accepts exact relative durations (`2d` = 24 h, DST-safe) or ISO-8601. This rule is
property-tested across DST boundaries and a non-UTC default zone
(`packages/python-sdk/tests/test_time_properties.py`, PRD 38 §Q12, issue #229).

## Rule

| Concern | Rule |
|---|---|
| Storage | `AgentRecord.started_at` is normalized to UTC (`records._iso` / `records._parse_iso`). |
| Comparison | Filters and retention compare aware UTC instants; no naive/aware comparison. |
| Relative `--since` | `30s`/`15m`/`12h`/`2d` are exact durations subtracted from now (UTC) — a day is 24 h, never a local calendar day. |
| Absolute `--since` | ISO-8601 with an offset or `Z` is used as given; ISO-8601 **without** an offset is interpreted in the local zone and returned aware. |
| Local rendering | `HH:MM:SS+HHMM` (e.g. `14:03:12-0700`), so a line read in another zone is unambiguous. |
| Machine-readable output | ISO-8601 with an offset (`…+00:00`), e.g. `--json`, exports, fleet/drift signals. |

## Why it matters

The PRD's edge cases are the ones that bite silently: DST spring-forward/fall-back, `--since` straddling
midnight, and a bundle produced in one timezone and read in another. Treating a naive timestamp as UTC, or
rendering local time without an offset, turns those into off-by-a-day or off-by-an-hour bugs that only an
auditor notices. Storing UTC and attaching an offset on render makes every timestamp self-describing.

## Pinned by

`packages/python-sdk/tests/test_time_properties.py` (Hypothesis properties over `since_cutoff`, hour
bucketing, and retention across DST), `tests/test_search_diff_alerts.py`, `tests/test_tail.py`.
