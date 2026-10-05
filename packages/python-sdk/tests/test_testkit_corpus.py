"""Cross-harness golden corpus replay (XHT-1, PRD 47; adopted via 25.CUR-1).

Real, licensed corpora: Claude Code transcripts and Codex rollouts (MIT,
agent-ouija) and Cursor session traces (MIT, cursor-session-tracer), plus
Cursor's vendor-documented native-hook payloads. Every corpus is provenance
tagged, secret-scanned, and replayed/contained — never executed.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from agentwatch import transcript
from agentwatch.adapters import cursor
from agentwatch.records import validate_record
from agentwatch.secrets import detect

KIT = Path(__file__).resolve().parent / "testkit"
MANIFESTS = sorted(KIT.rglob("manifest.json"))
LOCK = KIT / "checksums.json"
_NON_CORPUS = {"checksums.json", "PROVENANCE.md", "README.md"}


def _manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _files(manifest_path: Path, manifest: dict[str, Any]) -> list[Path]:
    if manifest["kind"] == "payload":
        base = (manifest_path.parent / str(manifest["payloads_dir"])).resolve()
        return sorted(base.glob("*.json"))
    return [manifest_path.parent / str(name) for name in manifest["files"]]


def _corpus() -> list[tuple[dict[str, Any], list[Path]]]:
    return [(_manifest(path), _files(path, _manifest(path))) for path in MANIFESTS]


def _for(harness: str, kind: str | None = None) -> list[Path]:
    out: list[Path] = []
    for manifest, files in _corpus():
        if manifest["harness"] == harness and (kind is None or manifest["kind"] == kind):
            out.extend(files)
    return out


def test_manifest_set_is_populated() -> None:
    assert MANIFESTS


def test_corpus_is_pinned_by_checksums() -> None:
    # The lock records every staged byte so the corpus can be reproduced and
    # verified without network access (scripts/fetch-testkit-corpus.py --check).
    locked = json.loads(LOCK.read_text(encoding="utf-8"))["files"]
    seen: set[str] = set()
    for path in sorted(KIT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(KIT).as_posix()
        if rel in _NON_CORPUS or path.name == "manifest.json":
            continue
        seen.add(rel)
        assert rel in locked, f"untracked corpus file: {rel}"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == locked[rel]["sha256"], rel
    assert seen == set(locked), "checksums.json has entries with no file"


@pytest.mark.parametrize("path", MANIFESTS, ids=lambda p: str(p.parent.relative_to(KIT)))
def test_manifest_records_provenance(path: Path) -> None:
    manifest = _manifest(path)
    for key in ("harness", "version", "kind", "source", "license", "captured_from_real_harness"):
        assert key in manifest, f"{path.parent.name} manifest missing {key}"
    assert _files(path, manifest), f"{path.parent.name} corpus is empty"


@pytest.mark.parametrize("path", MANIFESTS, ids=lambda p: str(p.parent.relative_to(KIT)))
def test_corpus_files_are_secret_free(path: Path) -> None:
    manifest = _manifest(path)
    leaks = [
        f.name
        for f in _files(path, manifest)
        if detect(f.read_text(encoding="utf-8", errors="replace"))
    ]
    assert not leaks, f"{manifest['harness']} corpus contains secrets: {leaks}"


def test_claude_code_rollouts_replay_through_the_reader() -> None:
    files = _for("claude-code", "rollout")
    assert files
    for path in files:
        summary = transcript.extract_usage(path)
        assert summary.tokens >= 0


def test_codex_rollouts_are_wellformed_jsonl() -> None:
    files = _for("codex", "rollout")
    assert files
    for path in files:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                json.loads(line)


def test_cursor_session_traces_are_structured() -> None:
    files = _for("cursor", "trace")
    assert files
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert "session" in data and "events" in data


def test_cursor_vendor_payloads_replay_through_the_adapter() -> None:
    files = _for("cursor", "payload")
    assert files
    for path in files:
        fixture = json.loads(path.read_text(encoding="utf-8"))
        records = cursor.normalize(fixture["message"])
        assert [record.to_dict() for record in records] == fixture["expected"], path.name
        for record in records:
            validate_record(record.to_dict())


def test_corpus_parsers_never_spawn_a_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("corpus content reached a shell")

    for name in ("system", "popen"):
        monkeypatch.setattr(os, name, _boom)
    for name in ("Popen", "run", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, _boom)

    for path in _for("claude-code"):
        transcript.extract_usage(path)
    for path in _for("codex"):
        path.read_text(encoding="utf-8")
    for path in _for("cursor", "trace"):
        json.loads(path.read_text(encoding="utf-8"))
    for path in _for("cursor", "payload"):
        cursor.normalize(json.loads(path.read_text(encoding="utf-8"))["message"])
