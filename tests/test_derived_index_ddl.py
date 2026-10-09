"""Derived-index DDL + data dictionary (M28 DATA-1, #435; PRD 41).

The Postgres index is **derived and rebuildable** from the hash-chained store:
every table carries a `source_seq`/`source_hash` back-reference to the chain, and
the store remains the source of truth (a drop-Postgres mode is always possible).
This test guards that contract against the committed DDL and dictionary.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DDL = ROOT / "schema" / "derived-index.sql"
DICTIONARY = ROOT / "docs" / "design" / "data-dictionary.md"

TABLES = ("sessions", "records", "events", "usage", "identity", "detectors")


def _ddl() -> str:
    return DDL.read_text(encoding="utf-8")


def _table_block(sql: str, name: str) -> str:
    match = re.search(
        rf"CREATE TABLE(?:\s+IF NOT EXISTS)?\s+{name}\s*\((.*?)\n\);",
        sql,
        re.DOTALL,
    )
    assert match is not None, f"DDL is missing table {name}"
    return match.group(1)


def test_ddl_is_present_and_declares_derived_only() -> None:
    sql = _ddl()
    assert "derived" in sql.lower()
    assert "rebuild" in sql.lower()
    # It must never claim authority over the chain.
    assert "source of truth" in sql.lower()


def test_every_table_has_source_back_references() -> None:
    sql = _ddl()
    for table in TABLES:
        block = _table_block(sql, table)
        assert "source_seq" in block, f"{table} is missing source_seq"
        assert "source_hash" in block, f"{table} is missing source_hash"


def test_dictionary_lists_the_tables_and_links_the_ddl() -> None:
    text = DICTIONARY.read_text(encoding="utf-8")
    assert "derived-index.sql" in text
    for table in TABLES:
        assert f"`{table}`" in text, f"dictionary does not document table {table}"
