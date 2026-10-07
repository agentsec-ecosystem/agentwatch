"""Register the FWK-1 framework OTel conformance packs (M29 #446, O1).

Each certified recipe replays its framework's OTLP payload through the *shared*
``agentwatch.ingest`` transcoder and must produce valid records with the expected
``(tool, step_type)`` sequence — the same bar an adapter pack passes. The packages
are not installed here, so the pack is fixture-driven; the live pinned run is
BLOCKED (recorded on the recipe) and never faked.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentwatch import conformance, frameworks
from agentwatch.ingest import transcode_otel_detailed

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "frameworks"


def _replay(payload: Any) -> Any:
    records, _problems, _unmapped = transcode_otel_detailed(payload)
    return records


def framework_spec(name: str) -> conformance.SdkSpec:
    """The O1 SDK pack for one certified framework recipe."""
    return conformance.SdkSpec(
        name=f"framework-{name}",
        replay=_replay,
        fixtures_dir=FIXTURES / name,
        error_cls=ValueError,
    )


def register_framework_packs() -> None:
    registered = {spec.name for spec in conformance.registered_sdks()}
    for name in frameworks.SUPPORTED_FRAMEWORKS:
        spec = framework_spec(name)
        if spec.name not in registered:
            conformance.register_sdk(spec)
            registered.add(spec.name)


register_framework_packs()

__all__ = ["FIXTURES", "framework_spec", "register_framework_packs"]
