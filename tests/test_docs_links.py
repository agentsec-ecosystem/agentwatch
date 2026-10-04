"""Link-check the documentation (issue #116).

Walks ``docs/**/*.md`` and the top-level ``README.md`` and fails on any relative
link whose target does not exist. External URLs and pure anchors are ignored.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]

# Inline links: [text](target) and reference definitions: [label]: target
_INLINE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_REFERENCE = re.compile(r"^\s*\[[^\]]+\]:\s*(\S+)", re.MULTILINE)


def _markdown_files() -> list[Path]:
    files = sorted((ROOT / "docs").rglob("*.md"))
    files.append(ROOT / "README.md")
    return files


def _link_targets(text: str) -> list[str]:
    return _INLINE.findall(text) + _REFERENCE.findall(text)


def _is_external(target: str) -> bool:
    return (
        target.startswith(("http://", "https://", "mailto:", "tel:", "#", "/"))
        or "://" in target
    )


def test_relative_doc_links_resolve() -> None:
    missing: list[str] = []

    for md in _markdown_files():
        base = md.parent
        for raw_target in _link_targets(md.read_text(encoding="utf-8")):
            target = raw_target.split("#", 1)[0].strip("<>")
            if not target or _is_external(target):
                continue
            resolved = (base / unquote(target)).resolve()
            if not resolved.exists():
                missing.append(f"{md.relative_to(ROOT)} -> {target}")

    assert not missing, "broken relative links:\n" + "\n".join(missing)
