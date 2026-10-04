"""Executable documentation (PRD 38 §Q10, issue #227)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[3]
CHECKER = REPO / "scripts" / "check_docs_commands.py"


def _load_checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_docs_commands", CHECKER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


check = _load_checker()


def test_only_annotated_blocks_are_extracted() -> None:
    markdown = (
        "```sh\nfalse\n```\n\n"
        "```sh run\ntrue\n```\n\n"
        "```sh service\nfalse\n```\n"
    )
    blocks = check.extract_blocks(markdown, Path("x.md"))

    assert [block.mode for block in blocks] == ["run", "service"]
    assert blocks[0].script == "true"


def test_comments_and_continuations_are_handled() -> None:
    markdown = "```sh run\n# a comment\necho one \\\n  two\n```\n"
    blocks = check.extract_blocks(markdown, Path("x.md"))

    assert "# a comment" not in blocks[0].script
    assert blocks[0].script == "echo one \\\n  two"


def test_current_cookbook_executes() -> None:
    assert check.check(REPO) == []


def test_the_cookbook_has_executable_blocks() -> None:
    total = 0
    for path in check.iter_documents(REPO):
        blocks = check.extract_blocks(path.read_text(encoding="utf-8"), path)
        total += sum(1 for block in blocks if block.mode == "run")
    assert total >= 1


def test_a_failing_command_is_reported(tmp_path: Path) -> None:
    doc = tmp_path / "broken.md"
    doc.write_text("# broken\n\n```sh run\nexit 9\n```\n", encoding="utf-8")

    errors = check.run_document(doc, REPO, tmp_path / "work")

    assert errors
    assert "command failed" in errors[0]


def test_the_self_test_passes() -> None:
    assert check._self_test(REPO) == []
