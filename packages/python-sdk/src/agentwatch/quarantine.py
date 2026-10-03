"""Quarantine log for undecodable events (M5 B4, F8).

Normalization failures must not drop the original bytes: they are preserved
verbatim here (owner-only) so the event can be diagnosed and, later, reprocessed.
The quarantine is evidence, not records — it is excluded from the store.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class QuarantineLog:
    """Append-only, owner-only log of raw frames that failed to normalize."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def add(self, raw: str | bytes, *, reason: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace")
        entry = {
            "at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "raw": text,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        os.chmod(self.path, 0o600)

    def entries(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        result: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                result.append(obj)
        return result

    def size_bytes(self) -> int:
        return self.path.stat().st_size if self.path.exists() else 0
