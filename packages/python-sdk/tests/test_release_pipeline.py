"""Release pipeline signing + ``agentwatch verify-release`` (PRD 38 §Q13, #230)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from agentwatch import errors
from agentwatch.cli import main as cli
from agentwatch.release_verify import verify_release

REPO = Path(__file__).resolve().parents[3]
WORKFLOWS = REPO / ".github" / "workflows"
CHECKSUMS = REPO / "scripts" / "release" / "checksums.py"
_SHA_PIN = re.compile(r"^[0-9a-f]{40}$")


def _write_checksums(dist: Path) -> None:
    subprocess.run(
        [sys.executable, str(CHECKSUMS), "--dist", str(dist)],
        check=True,
        capture_output=True,
    )


def _good_release(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "agentwatch-0.1.0.tar.gz").write_bytes(b"sdist-bytes")
    (dist / "agentwatch-0.1.0-py3-none-any.whl").write_bytes(b"wheel-bytes")
    (dist / "sbom.cdx.json").write_text(
        json.dumps(
            {"bomFormat": "CycloneDX", "specVersion": "1.5", "components": [{"name": "aw"}]}
        ),
        encoding="utf-8",
    )
    _write_checksums(dist)
    return dist


class _Result:
    def __init__(self, returncode: int, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr


def _which(name: str) -> str | None:
    return "/usr/bin/cosign" if name == "cosign" else None


# --- verify_release --------------------------------------------------------


def test_accepts_a_good_unsigned_release_when_explicitly_allowed(tmp_path: Path) -> None:
    report = verify_release(_good_release(tmp_path), allow_unsigned=True)

    assert report.ok, report.to_dict()


def test_rejects_a_tampered_artifact(tmp_path: Path) -> None:
    dist = _good_release(tmp_path)
    (dist / "agentwatch-0.1.0-py3-none-any.whl").write_bytes(b"tampered!")

    report = verify_release(dist, allow_unsigned=True)

    assert not report.ok
    checksums = next(check for check in report.checks if check.name == "checksums")
    assert not checksums.ok and "mismatch" in checksums.detail


def test_requires_a_signature_by_default(tmp_path: Path) -> None:
    report = verify_release(_good_release(tmp_path))

    assert not report.ok
    signature = next(check for check in report.checks if check.name == "signature")
    assert "unsigned" in signature.detail


def test_rejects_a_missing_sbom(tmp_path: Path) -> None:
    dist = _good_release(tmp_path)
    (dist / "sbom.cdx.json").unlink()
    _write_checksums(dist)

    report = verify_release(dist, allow_unsigned=True)

    assert not report.ok
    assert any(check.name == "sbom" and not check.ok for check in report.checks)


def test_verifies_cosign_bundles(tmp_path: Path) -> None:
    dist = _good_release(tmp_path)
    (dist / "agentwatch-0.1.0-py3-none-any.whl.sigstore.json").write_text("{}", encoding="utf-8")
    calls: list[list[str]] = []

    def run(command: list[str], **kwargs: Any) -> _Result:
        calls.append(command)
        return _Result(0)

    report = verify_release(dist, which=_which, run=run)  # type: ignore[arg-type]

    assert report.ok, report.to_dict()
    assert calls and calls[0][1] == "verify-blob"
    assert calls[0][0].endswith("cosign")


def test_rejects_a_bad_cosign_bundle(tmp_path: Path) -> None:
    dist = _good_release(tmp_path)
    (dist / "agentwatch-0.1.0-py3-none-any.whl.sigstore.json").write_text("{}", encoding="utf-8")

    report = verify_release(dist, which=_which, run=lambda *a, **k: _Result(1, "bad signature"))  # type: ignore[arg-type]

    assert not report.ok
    assert any("cosign rejected" in check.detail for check in report.checks)


def test_bundles_without_cosign_fail_closed(tmp_path: Path) -> None:
    dist = _good_release(tmp_path)
    (dist / "agentwatch-0.1.0-py3-none-any.whl.sigstore.json").write_text("{}", encoding="utf-8")

    report = verify_release(dist, which=lambda name: None)

    assert not report.ok
    assert any("cosign is not installed" in check.detail for check in report.checks)


# --- CLI -------------------------------------------------------------------


def test_cli_verify_release_json(tmp_path: Path, capsys: Any) -> None:
    dist = _good_release(tmp_path)

    code = cli(["verify-release", str(dist), "--allow-unsigned", "--json"])

    assert code == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_cli_verify_release_fails_on_tamper_with_envelope(tmp_path: Path, capsys: Any) -> None:
    dist = _good_release(tmp_path)
    (dist / "agentwatch-0.1.0-py3-none-any.whl").write_bytes(b"tampered!")

    code = cli(["verify-release", str(dist), "--allow-unsigned"])

    err = capsys.readouterr().err
    assert code != 0
    assert "invalid release" in err
    envelope = json.loads([line for line in err.splitlines() if line.startswith("{")][-1])
    assert envelope["error"]["code"] == errors.ErrorCode.INVALID_INPUT


# --- workflow hardening ----------------------------------------------------


def test_release_workflow_builds_signs_and_verifies() -> None:
    text = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")

    assert "scripts/release/generate_sbom.py" in text
    assert "scripts/release/checksums.py" in text
    assert "requirements-build.txt" in text and "--require-hashes" in text
    assert "python -m build --no-isolation" in text
    assert "cosign sign-blob" in text
    assert "slsa-github-generator/.github/workflows/generator_generic_slsa3.yml" in text
    assert "agentwatch verify-release dist" in text


def test_build_lock_pins_versions_and_hashes() -> None:
    lock = REPO / "scripts" / "release" / "requirements-build.txt"
    entries = [
        line
        for line in lock.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]

    assert entries
    for line in entries:
        assert "==" in line, line
        assert "--hash=sha256:" in line, line


def test_every_workflow_action_is_pinned_by_a_commit_sha() -> None:
    offenders: list[str] = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        for line in path.read_text(encoding="utf-8").splitlines():
            match = re.search(r"uses:\s*(\S+)", line)
            if match is None or match.group(1).startswith("./"):
                continue
            ref = match.group(1)
            _, _, pin = ref.rpartition("@")
            if not _SHA_PIN.match(pin):
                offenders.append(f"{path.name}: {ref}")

    assert not offenders, "unpinned actions:\n" + "\n".join(offenders)
