"""Claude Agent SDK / headless telemetry recipe (M29 CCO-2, PRD 51).

An Agent-SDK program runs the same CLI and emits the same OpenTelemetry as Claude
Code, so it lands through the same ingest path — only the producer is
``sdk-native`` and identity comes from the resource attributes. This recipe reads
a committed export and transcribes it, so the gallery proves the route in CI.

Run::

    python examples/claude_agent_sdk_otel.py examples/fixtures/claude_agent_sdk_otel.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from agentwatch.claude_otel import transcode_agent_sdk


def load_payload(path: str | Path) -> Any:
    """Read a JSON OTel export from disk."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def transcribe(payload: Any) -> list[dict[str, Any]]:
    """Transcode an Agent-SDK OTel payload to record dicts (source ``sdk-native``)."""
    records, problems = transcode_agent_sdk(payload, source="sdk-native")
    if problems:
        raise ValueError(f"unmappable Agent SDK telemetry: {problems[0].reason}")
    return [record.to_dict() for record in records]


def main(argv: list[str]) -> int:
    target = argv[1] if len(argv) > 1 else "examples/fixtures/claude_agent_sdk_otel.json"
    records = transcribe(load_payload(target))
    for record in records:
        producer = record.get("producer", {})
        print(f"{producer.get('name')} · {record['tool']['name']} · {record['outcome']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))