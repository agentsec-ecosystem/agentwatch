#!/usr/bin/env python3
"""Checksum (and optionally sign) the offline browser verifier artifact (M30 VFY-1, #475).

The page is a self-contained release artifact: users open it from ``file://`` and
read its sha256 from ``SHA256SUMS`` (listed in ``README.md`` release evidence). The
release pipeline signs the checksum with the release ed25519 key via ``--sign``.

Usage::

    python scripts/build_browser_verifier.py --check
    python scripts/build_browser_verifier.py            # write SHA256SUMS
    python scripts/build_browser_verifier.py --sign key # also write SHA256SUMS.sig
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = REPO / "docs" / "release" / "verifier"
ARTIFACT = ARTIFACT_DIR / "agentwatch-verify.html"
CHECKSUMS = ARTIFACT_DIR / "SHA256SUMS"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_checksums() -> str:
    digest = sha256(ARTIFACT)
    CHECKSUMS.write_text(f"{digest}  {ARTIFACT.name}\n", encoding="utf-8")
    return digest


def check() -> int:
    if not CHECKSUMS.is_file():
        print("SHA256SUMS missing; run without --check", file=sys.stderr)
        return 1
    recorded = CHECKSUMS.read_text(encoding="utf-8").split()[0]
    actual = sha256(ARTIFACT)
    if recorded != actual:
        print(f"SHA256SUMS drift: recorded {recorded}, actual {actual}", file=sys.stderr)
        return 1
    print(f"browser verifier checksum OK: {actual}")
    return 0


def sign(key_path: Path) -> int:
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            NoEncryption,
            PrivateFormat,
        )
    except ImportError:  # pragma: no cover - signing is an optional extra
        print("cryptography is required to sign", file=sys.stderr)
        return 1
    if key_path.is_file():
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        key = load_pem_private_key(key_path.read_bytes(), password=None)
    else:
        key = Ed25519PrivateKey.generate()
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_bytes(
            key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
        )
    signature = key.sign(CHECKSUMS.read_bytes())
    CHECKSUMS.with_name(CHECKSUMS.name + ".sig").write_bytes(signature)
    print(f"signed {CHECKSUMS.name} -> {CHECKSUMS.name}.sig")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify SHA256SUMS matches")
    parser.add_argument("--sign", default=None, help="PEM ed25519 key path (created if absent)")
    args = parser.parse_args(argv)
    if args.check:
        return check()
    digest = write_checksums()
    print(f"wrote SHA256SUMS for {ARTIFACT.name}: {digest}")
    if args.sign:
        return sign(Path(args.sign))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
