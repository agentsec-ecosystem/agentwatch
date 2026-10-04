"""Dependency egress-audit tests (M12 K2, R6/NFR-9)."""

from __future__ import annotations

from pathlib import Path

from agentwatch.egress_audit import audit, third_party_roots

SRC = Path(__file__).resolve().parents[1] / "src" / "agentwatch"


def test_sdk_source_is_egress_clean() -> None:
    assert audit(SRC) == []


def test_audit_flags_banned_imports(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text(
        "import requests\nfrom aiohttp import ClientSession\n", encoding="utf-8"
    )

    findings = audit(tmp_path)

    assert len(findings) == 2
    assert any("requests" in finding for finding in findings)
    assert any("aiohttp" in finding for finding in findings)


def test_audit_ignores_allowed_and_relative_imports(tmp_path: Path) -> None:
    (tmp_path / "ok.py").write_text(
        "import opentelemetry\nfrom . import sibling\n", encoding="utf-8"
    )

    assert audit(tmp_path) == []


def test_third_party_roots_excludes_stdlib_and_first_party() -> None:
    roots = third_party_roots(SRC)
    assert "opentelemetry" in roots
    assert "json" not in roots
    assert "agentwatch" not in roots
