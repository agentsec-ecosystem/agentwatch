#!/usr/bin/env python3
"""DEP-1: ``doctor`` must never claim hooks are 'installed' when managed policy
blocks them; it must report blocked / yes / unknown honestly."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
for _cand in (
    "/work/packages/python-sdk/src",
    os.path.join(_HERE, "..", "..", "packages", "python-sdk", "src"),
):
    if os.path.isdir(_cand):
        sys.path.insert(0, _cand)

from agentwatch.doctor import _check_hooks  # noqa: E402
from agentwatch.managed_policy import ManagedPolicy  # noqa: E402

_SETTINGS = {"user": Path("/nonexistent/user-settings.json"),
             "project": Path("/nonexistent/project-settings.json")}


def main() -> int:
    blocked = _check_hooks(
        _SETTINGS,
        ManagedPolicy(present=True, managed_hooks_only=True,
                      blocking_flags=("allowManagedHooksOnly",)),
    )
    detail = blocked.detail.lower()
    assert detail.startswith("hooks effective: blocked"), blocked.detail
    assert "installed" not in detail, f"claims 'installed' while blocked: {blocked.detail}"

    allowed = _check_hooks(
        _SETTINGS,
        ManagedPolicy(present=True, managed_hooks_only=True, managed_agentwatch=True),
    )
    assert allowed.detail.startswith("hooks effective: yes"), allowed.detail

    unknown = _check_hooks(_SETTINGS, ManagedPolicy(present=True, error="unreadable"))
    assert unknown.detail.startswith("hooks effective: unknown"), unknown.detail

    print("ok: doctor reports blocked / yes / unknown honestly, never 'installed' while blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
