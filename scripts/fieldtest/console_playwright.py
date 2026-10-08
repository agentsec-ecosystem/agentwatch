#!/usr/bin/env python3
"""M31 31.3 — run the local-console Playwright spec against a live console (LUI-1).

Starts `agentwatch ui` (loopback, per-launch token), parses its URL from stdout,
runs `apps/web/tests/e2e/console.spec.ts` with `FT_CONSOLE_URL` set, then stops
the console. Exit code is the Playwright result, so a red console spec fails the
case rather than passing silently.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PORT = int(os.environ.get("FT_CONSOLE_PORT", "8765"))
URL_RE = re.compile(r"http://127\.0\.0\.1:\d+/\?token=[A-Za-z0-9_-]+")


def main() -> int:
    proc = subprocess.Popen(
        ["agentwatch", "ui", "--host", "127.0.0.1", "--port", str(PORT), "--no-open"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    url: str | None = None
    deadline = time.time() + 20
    try:
        while time.time() < deadline:
            line = proc.stdout.readline() if proc.stdout else ""
            if not line and proc.poll() is not None:
                break
            match = URL_RE.search(line or "")
            if match:
                url = match.group(0)
                break
        if not url:
            print("console did not start", file=sys.stderr)
            return 1
        env = dict(
            os.environ,
            FT_CONSOLE_URL=url,
            FT_SCREENSHOT_DIR=str(REPO / "docs/assets/screenshots"),
        )
        return subprocess.call(
            ["npx", "--prefix", str(REPO / "apps/web"), "playwright", "test",
             "tests/e2e/console.spec.ts"],
            cwd=str(REPO),
            env=env,
        )
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:  # noqa: BLE001 - best-effort cleanup
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
