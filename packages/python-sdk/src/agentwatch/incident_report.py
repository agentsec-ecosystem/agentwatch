"""Registry-shaped incident report (M28 COR-3, PRD 43 §COR-3).

A voluntary, redacted export emitted *alongside* an evidence bundle so a local
investigation can be shared with a registry (AIR/AIID-shaped). It is
**manual**: the report is written into the local bundle and nowhere else — there
is no auto-egress path. Findings carry the registry fields and the tool name, but
never tool arguments, content, or raw principals.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agentwatch.incident_taxonomy import air_mapping, gmf_mapping
from agentwatch.records import Outcome, SecurityEventType
from agentwatch.store import RecordStore

INCIDENT_REPORT_SCHEMA = "agentwatch.incident-report/1"
INCIDENT_REPORT_FILENAME = "incident-report.json"
OPERATOR_NOTE_TOOL = "operator-note"


def build_incident_report(
    store: RecordStore, session_id: str, *, now: datetime | None = None
) -> dict[str, Any]:
    """Build the registry-shaped, redacted report for one session."""
    moment = now or datetime.now(timezone.utc)
    records = [
        entry.record
        for entry in store.entries()
        if entry.record is not None and entry.record.session_id == session_id
    ]

    findings: list[dict[str, Any]] = []
    arguments_withheld = 0
    for record in records:
        if record.tool.arguments:
            arguments_withheld += 1
        if record.outcome == Outcome.DENIED:
            findings.append(
                {
                    "event": SecurityEventType.DENIED.value,
                    "at": record.started_at.isoformat(),
                    "tool": record.tool.name,
                    "air": air_mapping(SecurityEventType.DENIED),
                    "gmf": gmf_mapping(SecurityEventType.DENIED),
                }
            )

    annotations: list[dict[str, Any]] = []
    for record in records:
        if record.tool.name != OPERATOR_NOTE_TOOL:
            continue
        arguments = record.tool.arguments or {}
        raw_tags = arguments.get("incident_tags")
        tags = [str(tag) for tag in raw_tags] if isinstance(raw_tags, list) else []
        annotations.append(
            {
                "at": record.started_at.isoformat(),
                "tag": arguments["tag"] if isinstance(arguments.get("tag"), str) else None,
                "incident_tags": tags,
            }
        )

    return {
        "schema": INCIDENT_REPORT_SCHEMA,
        "generated_at": moment.isoformat(),
        "session_id": session_id,
        "submission": {"mode": "manual-voluntary", "endpoint": None, "auto_egress": False},
        "findings": findings,
        "annotations": annotations,
        "redaction": {
            "mode": "metadata-only",
            "content_included": False,
            "arguments_included": False,
            "principals_hashed": True,
            "receipts": {
                "records": len(records),
                "tool_arguments_withheld": arguments_withheld,
            },
        },
    }


__all__ = [
    "INCIDENT_REPORT_FILENAME",
    "INCIDENT_REPORT_SCHEMA",
    "build_incident_report",
]
