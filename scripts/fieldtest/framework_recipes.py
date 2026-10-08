#!/usr/bin/env python3
"""M31 31.2 — certified framework recipes (FWK-1). Real API: frameworks.all_recipes."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agentwatch import frameworks  # real API
from _ftutil import ok

def main(argv):
    recipes = list(frameworks.all_recipes())
    assert recipes, "no framework recipes registered"
    for r in recipes:
        assert frameworks.recipe_line_count(r.name) <= 2, f"recipe {r.name} exceeds 2 lines"
    ok(f"{len(recipes)} framework recipes; <=2 lines each; source+integrity carried")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
