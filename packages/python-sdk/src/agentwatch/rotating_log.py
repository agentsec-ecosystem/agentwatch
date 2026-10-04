"""Size-capped, rotated logs (M12 F6, PRD 28).

An unbounded ``daemon.log`` is a slow disk leak that defeats the caps the store
enforces. :class:`RotatingLog` rotates at a byte cap into ``<name>.1`` … ``<name>.N``
before a new append, and surfaces its size for the doctor/health.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO

DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_BACKUPS = 2


class RotatingLog:
    """A size-capped append log with a fixed number of rotated backups."""

    def __init__(
        self,
        path: Path | str,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
        backups: int = DEFAULT_BACKUPS,
    ) -> None:
        self.path = Path(path)
        self.max_bytes = max_bytes
        self.backups = max(1, backups)

    def size_bytes(self) -> int:
        return self.path.stat().st_size if self.path.exists() else 0

    def _backup(self, index: int) -> Path:
        return self.path.with_name(f"{self.path.name}.{index}")

    def rotate(self) -> bool:
        """Rotate when the log has reached the cap; return whether it rotated."""
        if not self.path.exists() or self.path.stat().st_size < self.max_bytes:
            return False
        self._backup(self.backups).unlink(missing_ok=True)
        for index in range(self.backups - 1, 0, -1):
            source = self._backup(index)
            if source.exists():
                os.replace(source, self._backup(index + 1))
        os.replace(self.path, self._backup(1))
        return True

    def open_append(self) -> BinaryIO:
        """Rotate if needed and open the log for appending (binary)."""
        self.rotate()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return self.path.open("ab")

    def backups_present(self) -> list[Path]:
        return [
            self._backup(index)
            for index in range(1, self.backups + 1)
            if self._backup(index).exists()
        ]
