"""``agentwatch verify-release``: verify a built release (PRD 38 §Q13, issue #230).

Given a directory of built artifacts (wheel/sdist, SBOM, checksums, and optional
cosign bundles or SLSA provenance), this checks that:

1. artifacts exist;
2. every artifact matches its SHA-256 in the checksums file (and vice versa);
3. a valid CycloneDX SBOM is present;
4. the release is signed or carries provenance — or ``--allow-unsigned`` is set.

It is the consumer-facing half of the release pipeline: a user can check what
they downloaded instead of trusting the download.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

_CHECKSUM_NAMES = ("SHA256SUMS", "checksums.txt", "sha256sums.txt")
_SBOM_NAMES = ("sbom.cdx.json", "bom.json")
_SIDECAR_SUFFIXES = (".sigstore.json", ".intoto.jsonl", ".sig", ".crt", ".pem", ".bundle")
_BUNDLE_SUFFIX = ".sigstore.json"

Runner = Callable[..., "subprocess.CompletedProcess[str]"]
Which = Callable[[str], "str | None"]


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


@dataclass
class VerifyReport:
    directory: Path
    checks: list[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.checks) and all(check.ok for check in self.checks)

    def to_dict(self) -> dict[str, object]:
        return {
            "directory": str(self.directory),
            "ok": self.ok,
            "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in self.checks],
        }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_sidecar(path: Path) -> bool:
    return any(path.name.endswith(suffix) for suffix in _SIDECAR_SUFFIXES)


def _find(directory: Path, explicit: Path | None, names: tuple[str, ...]) -> Path | None:
    if explicit is not None:
        return explicit
    for name in names:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def _artifacts(directory: Path, checksums: Path | None, sbom: Path | None) -> list[Path]:
    excluded = {checksums, sbom}
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path not in excluded and not _is_sidecar(path)
    )


def _check_artifacts(artifacts: list[Path]) -> Check:
    return Check("artifacts", bool(artifacts), f"{len(artifacts)} artifact(s)")


def _check_checksums(directory: Path, checksums: Path | None, artifacts: list[Path]) -> Check:
    if checksums is None or not checksums.is_file():
        return Check("checksums", False, "no checksums file (expected SHA256SUMS)")
    entries: dict[str, str] = {}
    for line in checksums.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            entries[parts[1].lstrip("*")] = parts[0].lower()
    if not entries:
        return Check("checksums", False, "checksums file is empty")

    problems: list[str] = []
    for artifact in artifacts:
        expected = entries.get(artifact.name)
        if expected is None:
            problems.append(f"{artifact.name} is not listed")
        elif _sha256(artifact) != expected:
            problems.append(f"{artifact.name} sha256 mismatch")
    for name in entries:
        if not (directory / name).is_file():
            problems.append(f"checksums lists a missing file: {name}")
    if problems:
        return Check("checksums", False, "; ".join(problems))
    return Check("checksums", True, f"{len(artifacts)} artifact(s) verified")


def _check_sbom(sbom: Path | None) -> Check:
    if sbom is None or not sbom.is_file():
        return Check("sbom", False, "no SBOM (expected sbom.cdx.json)")
    try:
        data = json.loads(sbom.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return Check("sbom", False, f"SBOM is not valid JSON: {exc}")
    if not isinstance(data, dict) or data.get("bomFormat") != "CycloneDX":
        return Check("sbom", False, "SBOM is not CycloneDX")
    components = data.get("components")
    if not isinstance(components, list):
        return Check("sbom", False, "SBOM has no components list")
    return Check(
        "sbom",
        True,
        f"CycloneDX {data.get('specVersion', '?')} with {len(components)} component(s)",
    )


def _check_signature(
    directory: Path,
    artifacts: list[Path],
    *,
    allow_unsigned: bool,
    which: Which,
    run: Runner,
    source_uri: str | None,
    cosign_identity: str | None,
    cosign_issuer: str | None,
) -> Check:
    if allow_unsigned:
        return Check("signature", True, "skipped (--allow-unsigned)")

    bundles = sorted(directory.glob(f"*{_BUNDLE_SUFFIX}"))
    if bundles:
        cosign = which("cosign")
        if cosign is None:
            return Check("signature", False, "cosign bundles present but cosign is not installed")
        for bundle in bundles:
            artifact = bundle.with_name(bundle.name[: -len(_BUNDLE_SUFFIX)])
            command = [cosign, "verify-blob", "--bundle", str(bundle)]
            if cosign_identity is not None:
                command += ["--certificate-identity-regexp", cosign_identity]
            if cosign_issuer is not None:
                command += ["--certificate-oidc-issuer", cosign_issuer]
            command.append(str(artifact))
            result = run(command, capture_output=True, text=True)
            if result.returncode != 0:
                return Check(
                    "signature", False, f"cosign rejected {artifact.name}: {result.stderr.strip()}"
                )
        return Check("signature", True, f"{len(bundles)} cosign bundle(s) verified")

    provenance = sorted(directory.glob("*.intoto.jsonl"))
    if provenance:
        verifier = which("slsa-verifier")
        if verifier is None:
            return Check(
                "signature", False, "SLSA provenance present but slsa-verifier is not installed"
            )
        for artifact in artifacts:
            command = [
                verifier,
                "verify-artifact",
                str(artifact),
                "--provenance-path",
                str(provenance[0]),
            ]
            if source_uri is not None:
                command += ["--source-uri", source_uri]
            result = run(command, capture_output=True, text=True)
            if result.returncode != 0:
                return Check(
                    "signature",
                    False,
                    f"slsa-verifier rejected {artifact.name}: {result.stderr.strip()}",
                )
        return Check(
            "signature", True, f"SLSA provenance verified for {len(artifacts)} artifact(s)"
        )

    return Check("signature", False, "no signature or provenance (unsigned release)")


def verify_release(
    directory: Path | str,
    *,
    checksums: Path | str | None = None,
    sbom: Path | str | None = None,
    allow_unsigned: bool = False,
    which: Which = shutil.which,
    run: Runner = subprocess.run,
    source_uri: str | None = None,
    cosign_identity: str | None = None,
    cosign_issuer: str | None = None,
) -> VerifyReport:
    """Verify a release directory; return a report whose ``ok`` gates the exit code."""
    root = Path(directory)
    report = VerifyReport(root)
    if not root.is_dir():
        report.checks.append(Check("artifacts", False, f"{root} is not a directory"))
        return report

    checksums_path = _find(
        root, Path(checksums) if checksums is not None else None, _CHECKSUM_NAMES
    )
    sbom_path = _find(root, Path(sbom) if sbom is not None else None, _SBOM_NAMES)
    artifacts = _artifacts(root, checksums_path, sbom_path)

    report.checks.append(_check_artifacts(artifacts))
    if not artifacts:
        return report
    report.checks.append(_check_checksums(root, checksums_path, artifacts))
    report.checks.append(_check_sbom(sbom_path))
    report.checks.append(
        _check_signature(
            root,
            artifacts,
            allow_unsigned=allow_unsigned,
            which=which,
            run=run,
            source_uri=source_uri,
            cosign_identity=cosign_identity,
            cosign_issuer=cosign_issuer,
        )
    )
    return report
