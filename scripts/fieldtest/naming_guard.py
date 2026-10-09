#!/usr/bin/env python3
"""NAM-1 guard (FT-ENV-0): the namesake warning must fire for a foreign
``agentwatch`` distribution and must NOT fire for ours (no false positive)."""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _cand in (
    "/work/packages/python-sdk/src",
    os.path.join(_HERE, "..", "..", "packages", "python-sdk", "src"),
):
    if os.path.isdir(_cand):
        sys.path.insert(0, _cand)

from agentwatch import naming  # noqa: E402


def main() -> int:
    foreign = naming.distribution_warning({naming.IMPORT_NAME: ["some-namesake"]})
    assert foreign == naming.NAMESAKE_WARNING, "a foreign distribution must warn"
    assert naming.FULL_INSTALL in (foreign or ""), "warning must name the qualified install"

    ours = naming.distribution_warning({naming.IMPORT_NAME: [naming.DISTRIBUTION_NAME]})
    assert ours is None, "our own distribution must not warn"

    missing = naming.distribution_warning({})
    assert missing is None, "a missing mapping entry must never warn (no false positive)"

    fired: list[str] = []
    assert naming.install_guard(fired.append, detector=lambda: naming.NAMESAKE_WARNING) is True
    assert fired == [naming.NAMESAKE_WARNING], "install_guard must emit the loud warning"
    print("ok: namesake warning fires for a foreign distribution; no false positive for ours")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
