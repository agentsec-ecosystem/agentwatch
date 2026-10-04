"""The investigation cookbook narratives run end-to-end (M8 addition J3).

Reproduces the commands from ``docs/examples/investigations/*.md`` against the
seed dataset, so the docs cannot silently drift.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from agentwatch.cli import main
from agentwatch.store import RecordStore

_ROOT = Path(__file__).resolve().parents[3]
_SEED = _ROOT / "scripts" / "seed-investigations.py"


def _load_seed() -> ModuleType:
    spec = importlib.util.spec_from_file_location("seed_investigations", _SEED)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def seeded_store(tmp_path: Path) -> Path:
    seed = _load_seed()
    store = RecordStore(tmp_path / "records.jsonl")
    for record in seed.build_records():
        store.append(record)
    return tmp_path


def test_loop_narrative(seeded_store: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base = ["--set", f"store.path={seeded_store}"]

    assert main([*base, "view", "sess-loop"]) == 0
    out = capsys.readouterr().out
    assert out.count("Read") >= 4

    assert main([*base, "replay", "sess-loop"]) == 0


def test_secret_narrative(seeded_store: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base = ["--set", f"store.path={seeded_store}"]

    assert main([*base, "search", "--session", "sess-secret"]) == 0
    assert "Bash" in capsys.readouterr().out

    # The store is clean: only the redacted payload and the security event.
    assert main([*base, "verify-privacy"]) == 0


def test_denied_narrative(seeded_store: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base = ["--set", f"store.path={seeded_store}"]

    assert main([*base, "search", "--outcome", "denied"]) == 0
    assert "Bash" in capsys.readouterr().out
    assert main([*base, "explain", "sess-denied"]) == 0


def test_diff_narrative(seeded_store: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base = ["--set", f"store.path={seeded_store}"]

    assert main([*base, "diff", "sess-loop", "sess-secret"]) == 0
    assert "diff sess-loop -> sess-secret" in capsys.readouterr().out
