"""Community adapter contract tests (M10 #79/#203).

Proves the published plugin contract is usable by an out-of-tree adapter: a
minimal adapter that only uses the public `agentwatch.conformance` API passes,
and a deliberately broken copy is rejected.
"""

from __future__ import annotations

import community_adapter

from agentwatch import conformance


def test_sample_community_adapter_conforms() -> None:
    report = conformance.run(community_adapter.spec())

    assert report.ok, report.summary()


def test_broken_adapter_is_rejected() -> None:
    report = conformance.run(community_adapter.broken_spec())

    assert not report.ok
