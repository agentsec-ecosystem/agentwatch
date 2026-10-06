"""MCP protocol-revision conformance matrix tests (M27 MCP-6 #338).

The MCP spec revised under us (2025-06-18 / 2025-11-25 / 2026-07-28). The proxy
declares, per revision, which surfaces it records and which the standard retired;
protocol drift (a new revision, or the tested range lagging the matrix) fails CI.
"""

from __future__ import annotations

import json
from pathlib import Path

from agentwatch import compatibility, mcp_protocol
from agentwatch.adapters import mcp_proxy as adapter

REVISIONS_DIR = Path(__file__).resolve().parent / "fixtures" / "mcp-proxy" / "revisions"


def test_versions_are_declared_and_ordered() -> None:
    assert mcp_protocol.PROTOCOL_VERSIONS == ("2025-06-18", "2025-11-25", "2026-07-28")
    assert mcp_protocol.PROTOCOL_VERSIONS[-1] == mcp_protocol.LATEST_PROTOCOL_VERSION


def test_every_revision_declares_surfaces() -> None:
    for revision in mcp_protocol.PROTOCOL_VERSIONS:
        assert mcp_protocol.supported_surfaces(revision)
    # Tasks arrived experimentally in 2025-11-25 (SEP-2663 redesigns them later).
    assert "mcp-tasks" in mcp_protocol.supported_surfaces("2025-11-25")
    assert "mcp-tasks" in mcp_protocol.supported_surfaces("2026-07-28")


def test_latest_surfaces_are_implemented_capabilities() -> None:
    latest = mcp_protocol.supported_surfaces(mcp_protocol.LATEST_PROTOCOL_VERSION)
    assert latest <= adapter.CAPABILITIES


def test_tested_range_tracks_the_latest_revision() -> None:
    # Protocol drift fails CI: the proxy's tested range must be the newest in the
    # matrix, not lag it.
    assert compatibility.SHIPPED["mcp-proxy"].tested.maximum == (
        mcp_protocol.LATEST_PROTOCOL_VERSION
    )


def test_compat_table_gained_a_protocol_column() -> None:
    table = compatibility.render_table()
    assert "| Protocol |" in table
    assert mcp_protocol.LATEST_PROTOCOL_VERSION in table


def test_closed_by_spec_surfaces_are_never_capabilities() -> None:
    assert set(mcp_protocol.CLOSED_BY_SPEC).isdisjoint(adapter.CAPABILITIES)


def test_each_revision_has_a_replayable_fixture_pack() -> None:
    for revision in mcp_protocol.PROTOCOL_VERSIONS:
        files = sorted((REVISIONS_DIR / revision).glob("*.json"))
        assert files, f"no per-revision fixture for {revision}"
        for path in files:
            fixture = json.loads(path.read_text(encoding="utf-8"))
            records = [record.to_dict() for record in adapter.normalize(fixture["message"])]
            assert records == fixture["expected"], path
