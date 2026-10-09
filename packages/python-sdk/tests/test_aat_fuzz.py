"""Fuzz/property hardening for the v0.2.0 AAT reader (M25 RSK-1, #311).

The AAT export is consumed by third-party tooling, so ``verify_aat`` must treat
its input as untrusted: it fails closed on any shape and never raises.
"""

from __future__ import annotations

import json

from hypothesis import given
from hypothesis import strategies as st

from agentwatch.aat import AAT_DRAFT, verify_aat

ARBITRARY_JSON = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text(max_size=50),
    lambda children: st.lists(children, max_size=5)
    | st.dictionaries(st.text(max_size=10), children, max_size=5),
)


@given(ARBITRARY_JSON)
def test_verify_aat_never_raises_on_arbitrary_input(value: object) -> None:
    assert verify_aat(value) in (True, False)


@given(st.text(min_size=1))
def test_verify_aat_rejects_a_wrong_revision(revision: str) -> None:
    bundle = {"aat_version": revision, "records": []}
    assert verify_aat(bundle) is (revision == AAT_DRAFT)


def test_verify_aat_rejects_a_json_string_and_bytes() -> None:
    assert verify_aat(json.dumps({"aat_version": AAT_DRAFT})) is False
    assert verify_aat(b"not-json") is False


def test_verify_aat_rejects_non_object_records() -> None:
    bad_records: dict[str, object] = {"aat_version": AAT_DRAFT, "records": ["nope"]}
    assert verify_aat(bad_records) is False
    bad_entry: dict[str, object] = {
        "aat_version": AAT_DRAFT,
        "records": [{"agentwatch": 1, "chain": 2}],
    }
    assert verify_aat(bad_entry) is False