#!/usr/bin/env python3
"""Measure the zero-code-change first-run path (M13 13.2, R2/NFR-4).

Times the post-install path: configure a local store, normalize one Claude Code
tool call through the adapter, append it, verify the chain, and run the redaction
self-test. The ``pip install`` step (network-bound) is measured separately by the
operator; this is the code-change-free recording path agentwatch owns.
"""

from __future__ import annotations

import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SDK = REPO / "packages" / "python-sdk"
sys.path.insert(0, str(SDK / "src"))

from agentwatch.adapters import claude_code  # noqa: E402
from agentwatch.selftest import run_redaction_self_test  # noqa: E402
from agentwatch.store import RecordStore  # noqa: E402


def main() -> int:
    started = time.perf_counter()
    with tempfile.TemporaryDirectory() as directory:
        store = RecordStore(Path(directory) / "records.jsonl")
        message = {
            "phase": "pre",
            "harness": "claude-code",
            "event": {
                "session_id": "first-run",
                "tool_name": "Bash",
                "tool_input": {"command": "ls"},
                "tool_use_id": "first-1",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }
        for record in claude_code.normalize(message):
            store.append(record)
        ok = store.verify().ok and run_redaction_self_test().passed
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    print(f"first-run record path: {elapsed_ms:.1f} ms (ok={ok})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
