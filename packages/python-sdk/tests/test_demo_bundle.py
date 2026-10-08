"""Static synthetic demo bundle (M30 DEMO-1, #480).

The bundle is a committed, offline artifact: synthetic data only (never evidence),
carrying no network reference, and clean under an independent secret scan. The
browser (VFY-1) rendering is deferred to 30.VFY-1; this test proves the artifact
itself opens offline with zero network requests.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from _secret_oracle import EXPECTED_GAPS, ORACLE_RULES

from agentwatch.secrets import detect

REPO = Path(__file__).resolve().parents[3]
BUNDLE = REPO / "examples" / "demo-bundle"
BUNDLE_JSON = BUNDLE / "bundle.json"

# Tokens that would cause a browser to open a connection (egress or asset load).
_NETWORK_RE = re.compile(
    r"https?://|ftp://|wss?://|\bfetch\s*\(|XMLHttpRequest|sendBeacon|"
    r"new\s+WebSocket|EventSource|<script[^>]+src=|<link[^>]+href=",
    re.IGNORECASE,
)


def _bundle_text_files() -> list[Path]:
    return sorted(path for path in BUNDLE.rglob("*") if path.is_file())


def test_bundle_exists_and_is_self_contained() -> None:
    assert BUNDLE.is_dir(), "examples/demo-bundle/ is missing"
    assert BUNDLE_JSON.is_file()
    files = _bundle_text_files()
    assert files, "the demo bundle has no files"
    # Static, synthetic data only: no scripts, no archives, no binaries.
    allowed = {".json", ".md", ".txt", ".ndjson"}
    assert all(path.suffix in allowed for path in files), sorted(
        path.name for path in files if path.suffix not in allowed
    )
    json.loads(BUNDLE_JSON.read_text(encoding="utf-8"))


def test_bundle_makes_zero_network_references() -> None:
    for path in _bundle_text_files():
        text = path.read_text(encoding="utf-8")
        match = _NETWORK_RE.search(text)
        assert match is None, f"{path.name} carries a network reference: {match.group(0)!r}"


def test_bundle_is_synthetic_and_not_evidence() -> None:
    bundle = json.loads(BUNDLE_JSON.read_text(encoding="utf-8"))
    assert bundle["synthetic"] is True
    assert bundle["session"]["producer"]["kind"] == "demo"
    assert bundle["session"]["session_id"].startswith("demo")
    for step in bundle["replay"]["timeline"]:
        assert step["outcome"] in {"ok", "error", "denied"}


def test_bundle_is_secret_scanned_by_two_independent_scanners() -> None:
    for path in _bundle_text_files():
        text = path.read_text(encoding="utf-8")
        assert detect(text) == [], f"{path.name} tripped the product secret scanner"
        for rule in ORACLE_RULES:
            if rule.id in EXPECTED_GAPS:  # documented recall gaps, not the demo's concern
                continue
            assert rule.pattern.search(text) is None, (
                f"{path.name} matched oracle rule {rule.id}"
            )


def test_bundle_shows_replay_impact_oversight_and_provenance() -> None:
    bundle = json.loads(BUNDLE_JSON.read_text(encoding="utf-8"))
    assert bundle["replay"]["timeline"]
    assert bundle["impact"]["facts"]
    assert bundle["impact"]["widest_action"]
    assert bundle["oversight"]["authorization_mix"]
    assert bundle["provenance"]["sessions"]
    assert bundle["verdicts"] == {"intact": True, "complete": True, "leak_free": True}


def test_bundle_is_linked_from_readme_and_gtm() -> None:
    for doc in (REPO / "README.md", REPO / "docs" / "gtm.md"):
        text = doc.read_text(encoding="utf-8")
        assert "examples/demo-bundle" in text, f"{doc} does not link the demo bundle"
