#!/usr/bin/env python3
"""FWK-1: certified framework recipes -- real API ``frameworks.all_recipes``.

Asserts each recipe is <=2 lines and carries a valid source vocabulary tag, a
pinned version, and non-empty identity/step/cost mappings -- no recipe is silently
partial. The shipped ``test_frameworks.py`` (host assert) is the canonical recipe
test.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "/ft/scripts")
from _ftutil import fail, ok  # noqa: E402

from agentwatch import frameworks  # noqa: E402


def main(argv: list[str]) -> int:
    recipes = list(frameworks.all_recipes())
    if not recipes:
        fail("no framework recipes registered")
    for recipe in recipes:
        if frameworks.recipe_line_count(recipe.name) > 2:
            fail(f"recipe {recipe.name} exceeds 2 lines")
        if frameworks.source_kind(recipe.source) != recipe.source:
            fail(f"recipe {recipe.name} carries an invalid source {recipe.source!r}")
        if not recipe.pinned:
            fail(f"recipe {recipe.name} has no pinned version")
        if not (recipe.identity_keys and recipe.step_map and recipe.cost_keys):
            fail(f"recipe {recipe.name} is silently partial (missing identity/step/cost mapping)")
    ok(f"{len(recipes)} framework recipes: <=2 lines, valid source, pinned, mappings present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
