"""EXT-8: Postgres is re-sequenced behind the embedded index (M30, PRD 54 §EXT-8).

A decision ticket has no new runtime code path; this test pins the *record* of the
decision so the design docs cannot silently drift back to "Postgres is the only
tier". The embedded index is the general-case tier (ADR-0035); Postgres is the
fleet / multi-tenant tier.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ADR_0035 = REPO / "docs" / "adr" / "0035-embedded-query-index.md"
DERIVED_PG = REPO / "docs" / "design" / "derived-postgres.md"
ADR_INDEX = REPO / "docs" / "adr" / "README.md"


def test_adr_0035_records_embedded_index_first() -> None:
    text = ADR_0035.read_text(encoding="utf-8").lower()
    assert "embedded" in text
    assert "general-case query tier" in text
    assert "fleet" in text or "multi-tenant" in text


def test_derived_postgres_documents_the_fleet_tenant_tier() -> None:
    text = DERIVED_PG.read_text(encoding="utf-8").lower()
    assert "re-sequenc" in text
    assert "fleet" in text
    assert "embedded" in text
    assert "adr-0035" in text
    # The re-sequencing is a recorded decision, not just a passing note.
    assert "## re-sequencing decision (ext-8)" in text


def test_adr_index_lists_0035() -> None:
    text = ADR_INDEX.read_text(encoding="utf-8")
    assert "0035-embedded-query-index.md" in text
