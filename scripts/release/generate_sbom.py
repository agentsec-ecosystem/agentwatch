#!/usr/bin/env python3
"""Generate a CycloneDX SBOM for the SDK (M13 13.5, OpenSSF/SLSA).

Reads ``packages/python-sdk/pyproject.toml`` and emits a CycloneDX 1.5 document
listing the package and its declared dependencies. Versions are taken from the
resolved environment (``importlib.metadata``) when the dependency is installed,
falling back to an exact ``==`` pin in the specifier, then to ``unspecified`` for
uninstalled/optional dependencies.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - 3.10 backport
    import tomli as tomllib  # type: ignore[no-redef]

REPO = Path(__file__).resolve().parents[2]
PYPROJECT = REPO / "packages" / "python-sdk" / "pyproject.toml"

_SPECIFIER = re.compile(r"^(?P<name>[A-Za-z0-9._-]+)")


def _resolved_version(name: str) -> str | None:
    """Return the installed version of ``name``, or None if it is not installed."""
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:  # pragma: no cover - Python < 3.8
        return None
    try:
        return version(name)
    except PackageNotFoundError:
        return None
    except Exception:  # pragma: no cover - defensive
        return None


def _pinned_version(spec: str) -> str | None:
    match = re.search(r"==\s*([0-9][0-9A-Za-z.\-]*)", spec)
    return match.group(1) if match else None


def _version_of(spec: str) -> str | None:
    name = _SPECIFIER.match(spec.strip())
    resolved = _resolved_version(name.group("name")) if name else None
    return resolved or _pinned_version(spec)


def build_sbom() -> dict[str, object]:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    project = data["project"]
    components = []
    for spec in project.get("dependencies", []):
        match = _SPECIFIER.match(spec.strip())
        if match is None:
            continue
        name = match.group("name")
        version = _version_of(spec) or "unspecified"
        purl = f"pkg:pypi/{name}"
        if version != "unspecified":
            purl = f"{purl}@{version}"
        components.append(
            {
                "type": "library",
                "name": name,
                "version": version,
                "purl": purl,
            }
        )
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": project["name"],
                "version": project["version"],
            }
        },
        "components": components,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="generate_sbom")
    parser.add_argument("--output", default=str(REPO / "dist" / "sbom.cdx.json"))
    args = parser.parse_args(argv)

    sbom = build_sbom()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(sbom, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"sbom: wrote {output} ({len(sbom['components'])} component(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
