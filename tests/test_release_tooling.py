"""Release tooling tests (M13 13.1/13.5): SBOM, checksums, release workflow."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "scripts" / "release"
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
SDK_PYPROJECT = ROOT / "packages" / "python-sdk" / "pyproject.toml"
SDK_INIT = ROOT / "packages" / "python-sdk" / "src" / "agentwatch" / "__init__.py"
CLI_PACKAGE = ROOT / "packages" / "cli" / "package.json"
CHANGELOG = ROOT / "CHANGELOG.md"


def test_sbom_is_valid_cyclonedx(tmp_path: Path) -> None:
    output = tmp_path / "sbom.cdx.json"
    result = subprocess.run(
        [sys.executable, str(RELEASE / "generate_sbom.py"), "--output", str(output)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    sbom = json.loads(output.read_text(encoding="utf-8"))
    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.5"
    assert sbom["metadata"]["component"]["name"] == "agentsec-agentwatch"
    names = {component["name"] for component in sbom["components"]}
    assert "opentelemetry-api" in names
    # Versions are resolved from the installed environment, not left blank.
    api = next(c for c in sbom["components"] if c["name"] == "opentelemetry-api")
    assert api["version"] not in ("", "unspecified")
    assert api["purl"].endswith(f"@{api['version']}")


def test_checksums_match_artifact_bytes(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "agentwatch-0.1.0-py3-none-any.whl").write_bytes(b"wheel-bytes")
    (dist / "agentwatch-0.1.0.tar.gz").write_bytes(b"sdist-bytes")

    result = subprocess.run(
        [sys.executable, str(RELEASE / "checksums.py"), "--dist", str(dist)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    sums = dict(
        line.split("  ", 1)[::-1]
        for line in (dist / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    )
    expected = hashlib.sha256(b"wheel-bytes").hexdigest()
    assert sums["agentwatch-0.1.0-py3-none-any.whl"] == expected


def test_release_workflow_builds_and_attests() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python -m build" in text
    assert "scripts/release/generate_sbom.py" in text
    assert "scripts/release/checksums.py" in text
    assert "attest-build-provenance" in text
    assert 'tags: ["v*"]' in text


def test_versions_are_consistent_across_surfaces() -> None:
    """M24 24.6 — the released version is identical everywhere it is declared."""
    match = re.search(r'^version = "([^"]+)"', SDK_PYPROJECT.read_text(encoding="utf-8"), re.M)
    assert match is not None, "no version in packages/python-sdk/pyproject.toml"
    version = match.group(1)

    assert f'__version__ = "{version}"' in SDK_INIT.read_text(encoding="utf-8")
    assert json.loads(CLI_PACKAGE.read_text(encoding="utf-8"))["version"] == version
    assert re.search(
        rf"^## \[{re.escape(version)}\]", CHANGELOG.read_text(encoding="utf-8"), re.M
    ), f"CHANGELOG.md has no '## [{version}]' entry"
