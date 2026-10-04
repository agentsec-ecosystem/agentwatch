#!/usr/bin/env python3
"""Offline E2E proof (M12 K2, R6/NFR-9).

Records, verifies the chain, replays, and runs the redaction self-test with no
network access required. CI runs this inside ``unshare --net`` so a stray
phone-home fails the job.
"""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SDK = REPO / "packages" / "python-sdk"
sys.path.insert(0, str(SDK / "src"))

from agentwatch.adapters import claude_code  # noqa: E402
from agentwatch.replay import replay_session  # noqa: E402
from agentwatch.selftest import run_redaction_self_test  # noqa: E402
from agentwatch.store import RecordStore  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        store = RecordStore(Path(directory) / "records.jsonl")
        for index in range(5):
            message = {
                "phase": "pre",
                "harness": "claude-code",
                "event": {
                    "session_id": "offline",
                    "tool_name": "Bash",
                    "tool_input": {"command": "ls"},
                    "tool_use_id": f"c{index}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }
            for record in claude_code.normalize(message):
                store.append(record)

        if not store.verify().ok:
            print("offline e2e: chain did not verify", file=sys.stderr)
            return 1
        if not replay_session(store, "offline"):
            print("offline e2e: replay returned no records", file=sys.stderr)
            return 1
        if not run_redaction_self_test().passed:
            print("offline e2e: redaction self-test failed", file=sys.stderr)
            return 1

    print("offline e2e: ok (record -> verify -> replay; no network)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
