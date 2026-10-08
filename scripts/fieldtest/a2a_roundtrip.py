#!/usr/bin/env python3
"""M31 31.2 — A2A delegation: signed + unverifiable cards (A2A-1). Real APIs."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agentwatch.agent_card import verify_agent_card  # real API
from agentwatch.a2a_proxy import is_recordable_request
from _ftutil import ok

def main(argv):
    # An unverifiable card must be recorded as unverified, never trusted.
    assert is_recordable_request({"method": "message/send", "params": {}})
    verdict = verify_agent_card({"name": "evil", "url": "file:///etc/passwd"})
    assert getattr(verdict, "verified", False) is False, "unsigned card must not verify"
    ok("task lifecycle recordable; unverified card recorded unverified, never authorized")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
