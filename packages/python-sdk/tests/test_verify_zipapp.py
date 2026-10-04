"""Standalone verifier tests (M15 S12, #232).

The shipped stdlib zipapp and the published doc reference implementation agree on
the same bundle vectors and the Q6 store vectors; a tampered vector fails both.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

from agentwatch.evidence import EvidenceBundle, build_bundle
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, ToolCall
from agentwatch.store import RecordStore

REPO = Path(__file__).resolve().parents[3]
VERIFY_DIR = REPO / "scripts" / "agentwatch_verify"
VECTORS = REPO / "schema" / "vectors" / "store"
START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _shipped() -> ModuleType:
    return _load("agentwatch_verify_main", VERIFY_DIR / "__main__.py")


def _reference() -> ModuleType:
    return _load("agentwatch_verify_reference", VERIFY_DIR / "reference.py")


def _record() -> AgentRecord:
    return AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name="Bash", arguments={"cmd": "ls"}),
        outcome=Outcome.OK,
        started_at=START,
        harness="claude-code",
        project="/repo",
    )


def _bundle(tmp_path: Path) -> Path:
    store_path = tmp_path / "records.jsonl"
    store = RecordStore(store_path)
    store.append(_record())
    store.append(_record())
    bundle = build_bundle(store, store_path, "s1")
    out = tmp_path / "bundle.zip"
    bundle.write(out)
    return out


def _tampered_bundle(tmp_path: Path) -> Path:
    store_path = tmp_path / "records.jsonl"
    store = RecordStore(store_path)
    store.append(_record())
    bundle = build_bundle(store, store_path, "s1")
    members = dict(bundle.members)
    members["records.ndjson"] = members["records.ndjson"] + b"{}"
    out = tmp_path / "tampered.zip"
    EvidenceBundle(session_id="s1", members=members).write(out)
    return out


def test_both_verifiers_accept_a_valid_bundle(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)

    shipped = _shipped().verify_bundle(bundle)
    reference = _reference().verify_bundle(bundle)

    assert shipped["ok"] and shipped["intact"] and shipped["complete"] and shipped["leak_free"]
    assert reference["ok"] and reference["intact"] and reference["complete"]
    assert shipped["intact"] == reference["intact"]
    assert shipped["leak_free"] == reference["leak_free"]


def test_both_verifiers_reject_a_tampered_bundle(tmp_path: Path) -> None:
    bundle = _tampered_bundle(tmp_path)

    shipped = _shipped().verify_bundle(bundle)
    reference = _reference().verify_bundle(bundle)

    assert not shipped["ok"] and not shipped["intact"]
    assert not reference["ok"] and not reference["intact"]
    assert any("tampered" in p for p in shipped["problems"])
    assert any("hash mismatch" in p for p in reference["problems"])


def test_unknown_bundle_format_is_named_by_both(tmp_path: Path) -> None:
    import zipfile

    out = tmp_path / "weird.zip"
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("manifest.json", json.dumps({"bundle_format": "agentwatch-evidence/999"}))

    for module in (_shipped(), _reference()):
        report = module.verify_bundle(out)
        assert not report["ok"]
        assert any("999" in problem for problem in report["problems"])


def test_both_verifiers_match_the_store_vector_table() -> None:
    table = json.loads((VECTORS / "expected-verdicts.json").read_text(encoding="utf-8"))
    shipped = _shipped()
    reference = _reference()

    for vector in table["vectors"]:
        path = VECTORS / vector["file"]
        expected = (vector["ok"], vector["broken_at"], vector["line"])
        for module in (shipped, reference):
            verdict = module.verify_store(path)
            actual = (verdict["ok"], verdict["broken_at"], verdict["line"])
            assert actual == expected, f"{vector['id']} diverged for {module.__name__}: {actual}"


def test_zipapp_builds_and_runs(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    pyz = tmp_path / "agentwatch-verify.pyz"

    build = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "build_verify_zipapp.py"), "--output", str(pyz)],
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr
    assert pyz.exists()

    good = subprocess.run([sys.executable, str(pyz), str(bundle)], capture_output=True, text=True)
    assert good.returncode == 0, good.stdout + good.stderr
    assert json.loads(good.stdout)["ok"] is True

    tampered = subprocess.run(
        [sys.executable, str(pyz), str(_tampered_bundle(tmp_path))],
        capture_output=True,
        text=True,
    )
    assert tampered.returncode == 1


def test_shipped_verifier_table_mode_matches_vectors() -> None:
    assert _shipped()._check_table(VECTORS) == 0
