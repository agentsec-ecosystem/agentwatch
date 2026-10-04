"""Spool for hook frames when the daemon is down (M5 F1).

The hook is fire-and-forget; if the socket send fails (daemon down, upgrading,
machine asleep) the frame is appended here. The daemon drains the spool on
start, so an event that happened is an event that is stored — recorded late,
never lost. Owner-only; size-bounded (drops oldest).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class Spool:
    """Size-bounded, append-only spool of framed hook messages."""

    def __init__(self, path: Path | str, *, max_bytes: int = 1_000_000) -> None:
        self.path = Path(path)
        self.max_bytes = max_bytes

    def append(self, message: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(message, ensure_ascii=False)
        lines = self._lines()
        lines.append(line)
        while len("\n".join(lines).encode("utf-8")) > self.max_bytes and len(lines) > 1:
            lines.pop(0)
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.chmod(self.path, 0o600)

    def drain(self) -> list[str]:
        """Return the spooled lines and clear the spool."""
        lines = self._lines()
        if self.path.exists():
            self.path.write_text("", encoding="utf-8")
            os.chmod(self.path, 0o600)
        return lines

    def _lines(self) -> list[str]:
        if not self.path.exists():
            return []
        return [line for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def size_bytes(self) -> int:
        return self.path.stat().st_size if self.path.exists() else 0
