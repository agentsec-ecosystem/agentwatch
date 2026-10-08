"""Offline browser evidence verifier (M30 VFY-1, #475).

PRD 57 §VFY-1, design ``docs/design/browser-verifier.md``. A static, self-contained
page must open from ``file://`` with **zero network requests**, load a bundle, and
re-verify it (chain / completeness / leak-scan / attestation) with the **same
verdicts as the CLI**. The verifier core is a JS module embedded inline; the
differential test drives it under a JS engine and compares byte-for-byte verdicts
to ``agentwatch.evidence.verify_bundle``.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentwatch.evidence import build_bundle, verify_bundle
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore

REPO = Path(__file__).resolve().parents[3]
ARTIFACT_DIR = REPO / "docs" / "release" / "verifier"
HTML = ARTIFACT_DIR / "agentwatch-verify.html"
CHECKSUMS = ARTIFACT_DIR / "SHA256SUMS"
RELEASE_EVIDENCE = ARTIFACT_DIR / "README.md"

START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _record(session: str = "s1", tool: str = "Bash") -> AgentRecord:
    return AgentRecord(
        session_id=session,
        agent=AgentIdentity(identity="agent"),
        tool=ToolCall(name=tool, arguments={"cmd": "ls"}),
        outcome=Outcome.OK,
        started_at=START,
        harness="claude-code",
        project="/repo",
    )


def _bundle(tmp_path: Path) -> Path:
    path = tmp_path / "records.jsonl"
    store = RecordStore(path)
    store.append(_record())
    store.append(_record(tool="Read"))
    bundle = build_bundle(store, path, "s1")
    out = tmp_path / "clean.evidence.zip"
    bundle.write(out)
    return out


def _read_members(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def _write_members(path: Path, members: dict[str, bytes], *, rehash: bool) -> None:
    if rehash:
        # Recompute the manifest member hashes so a test isolates the check it means.
        manifest = json.loads(members["manifest.json"])
        manifest["members"] = {
            name: hashlib.sha256(data).hexdigest()
            for name, data in members.items()
            if name != "manifest.json"
        }
        members["manifest.json"] = (
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        ).encode("utf-8")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(members):
            archive.writestr(name, members[name])


def _mutate(src: Path, dst: Path, mutate, *, rehash: bool = True) -> Path:  # type: ignore[no-untyped-def]
    members = _read_members(src)
    mutate(members)
    _write_members(dst, members, rehash=rehash)
    return dst


# --------------------------------------------------------------------------- artifact


def _core_script() -> str:
    html = HTML.read_text(encoding="utf-8")
    match = re.search(
        r'<script id="agentwatch-verify-core">(.*?)</script>', html, re.DOTALL
    )
    assert match is not None, "verifier core script not found"
    return match.group(1)


def test_html_artifact_exists() -> None:
    assert HTML.is_file()
    assert CHECKSUMS.is_file()
    assert RELEASE_EVIDENCE.is_file()


def test_html_is_self_contained_and_has_no_network_surface() -> None:
    html = HTML.read_text(encoding="utf-8")
    forbidden = (
        "http://",
        "https://",
        "fetch(",
        "XMLHttpRequest",
        "WebSocket",
        "sendBeacon",
        "import(",
        "<script src",
        "<link ",
    )
    for token in forbidden:
        assert token not in html, f"self-contained page must not contain {token!r}"
    assert _core_script().strip()


def test_checksum_matches_the_artifact_and_is_listed_in_release_evidence() -> None:
    digest = hashlib.sha256(HTML.read_bytes()).hexdigest()
    checksums = CHECKSUMS.read_text(encoding="utf-8")
    assert digest in checksums
    assert HTML.name in checksums
    evidence = RELEASE_EVIDENCE.read_text(encoding="utf-8")
    assert digest in evidence


# --------------------------------------------------------------------------- differential


def _node_verify(path: Path, tmp_path: Path) -> dict[str, object]:
    node = shutil.which("node")
    if node is None:  # pragma: no cover - node is present in CI
        pytest.skip("node is required for the browser-verifier differential test")
    core = tmp_path / "core.js"
    core.write_text(
        _core_script() + "\nglobalThis.__aw = AgentwatchVerify;\n", encoding="utf-8"
    )
    driver = tmp_path / "driver.js"
    driver.write_text(
        "const fs = require('fs');\n"
        "require(" + json.dumps(str(core)) + ");\n"
        "(async () => {\n"
        "  const bytes = fs.readFileSync(process.argv[2]);\n"
        "  const result = await globalThis.__aw.verifyBundle(bytes);\n"
        "  process.stdout.write(JSON.stringify(result));\n"
        "})().catch((err) => { console.error(err); process.exit(2); });\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [node, str(driver), str(path)], capture_output=True, text=True, check=True
    )
    return json.loads(proc.stdout)


def _fixture_set(tmp_path: Path) -> list[Path]:
    clean = _bundle(tmp_path)
    fixtures = [clean]

    def incomplete(members: dict[str, bytes]) -> None:
        coverage = json.loads(members["coverage.json"])
        coverage["complete"] = False
        coverage["gaps"] = [1]
        members["coverage.json"] = json.dumps(coverage, indent=2, sort_keys=True).encode()

    def leaky(members: dict[str, bytes]) -> None:
        privacy = json.loads(members["privacy.json"])
        privacy["leak_free"] = False
        privacy["leaks"] = ["argument.secret"]
        members["privacy.json"] = json.dumps(privacy, indent=2, sort_keys=True).encode()

    fixtures.append(_mutate(clean, tmp_path / "incomplete.zip", incomplete))
    fixtures.append(_mutate(clean, tmp_path / "leaky.zip", leaky))
    return fixtures


def test_differential_verdicts_match_the_cli_on_every_fixture(tmp_path: Path) -> None:
    for bundle in _fixture_set(tmp_path):
        cli = verify_bundle(bundle)
        js = _node_verify(bundle, tmp_path)
        assert js["intact"] == cli.intact, bundle.name
        assert js["complete"] == cli.complete, bundle.name
        assert js["leak_free"] == cli.leak_free, bundle.name


def test_missing_member_fails_in_both(tmp_path: Path) -> None:
    clean = _bundle(tmp_path)

    def drop(members: dict[str, bytes]) -> None:
        del members["verify.json"]

    # Keep the manifest listing verify.json while dropping it from the zip.
    broken = _mutate(clean, tmp_path / "missing.zip", drop, rehash=False)
    assert verify_bundle(broken).intact is False
    js = _node_verify(broken, tmp_path)
    assert js["intact"] is False
    assert any("verify.json" in problem for problem in js["problems"])


def test_tampered_bundle_names_the_first_broken_link(tmp_path: Path) -> None:
    clean = _bundle(tmp_path)

    def tamper_chain(members: dict[str, bytes]) -> None:
        lines = members["records.ndjson"].decode("utf-8").splitlines()
        row = json.loads(lines[1])
        row["record"]["tool"]["name"] = "Tampered"
        lines[1] = json.dumps(row, sort_keys=True, ensure_ascii=False)
        members["records.ndjson"] = ("\n".join(lines) + "\n").encode("utf-8")

    broken = _mutate(clean, tmp_path / "chain.zip", tamper_chain)
    assert verify_bundle(broken).intact is False
    js = _node_verify(broken, tmp_path)
    assert js["intact"] is False
    assert js["first_broken"] == 1


def test_unreadable_bundle_never_raises_in_the_browser_core(tmp_path: Path) -> None:
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    js = _node_verify(bad, tmp_path)
    assert js["intact"] is False
    assert js["problems"]
