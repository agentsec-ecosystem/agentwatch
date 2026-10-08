#!/usr/bin/env python3
"""Validate every `agentwatch` invocation in the field-test steps + drivers
against the *real* CLI surface built from the shipped parser (M31 31.2/31.3).

Fails (exit 1) on any unknown command, unknown subcommand, or unknown option,
and on any `from agentwatch import <module>` / `agentwatch.<module>` that does
not import. This is the gate that keeps the cases wired to the product that
actually ships, not to an imagined one.

Run: python3 scripts/fieldtest/check_cli_usage.py
"""
from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STEPS = REPO / "scripts/fieldtest/cases/steps"
DRIVERS = REPO / "scripts/fieldtest"
SDK_SRC = REPO / "packages/python-sdk/src"

sys.path.insert(0, str(SDK_SRC))


def _subs(parser):
    for a in parser._actions:
        if hasattr(a, "choices") and a.choices and hasattr(a, "add_parser"):
            return a
    return None


def surface() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Return (commands -> subcommands, command -> options)."""
    mm = importlib.import_module("agentwatch.cli.main")
    top = _subs(mm._build_parser())
    cmds: dict[str, set[str]] = {}
    opts: dict[str, set[str]] = {}
    for name, sp in top.choices.items():
        s = _subs(sp)
        cmds[name] = set(s.choices) if s else set()
        o = {x for a in sp._actions for x in a.option_strings}
        # option strings of subparsers belong to the subcommand, keyed "cmd sub"
        for sub, ssp in (s.choices.items() if s else []):
            o = {x for a in ssp._actions for x in a.option_strings}
            opts[f"{name} {sub}"] = o | {"-h", "--help"}
        opts[name] = o | {"-h", "--help"}
    return cmds, opts


CMDS, OPTS = surface()
_VALID_MODULES = {p.stem for p in (SDK_SRC / "agentwatch").glob("*.py")}


def _check_invocation(ctx: str, argv: list[str], problems: list[str]) -> None:
    if not argv or argv[0] != "agentwatch":
        return
    if len(argv) < 2:
        return
    cmd = argv[1]
    if cmd.startswith("-"):
        return
    if cmd not in CMDS:
        problems.append(f"{ctx}: unknown command 'agentwatch {cmd}'")
        return
    subs = CMDS[cmd]
    if subs and len(argv) >= 3 and not argv[2].startswith("-"):
        if argv[2] not in subs:
            problems.append(f"{ctx}: unknown subcommand 'agentwatch {cmd} {argv[2]}'")
    # options: pick the deepest parser (cmd sub) then cmd
    key = f"{cmd} {argv[2]}" if (subs and len(argv) >= 3 and argv[2] in subs) else cmd
    allowed = OPTS.get(key, set())
    for tok in argv[2:]:
        if tok.startswith("--") and "=" not in tok and tok not in allowed:
            problems.append(f"{ctx}: unknown option '{tok}' for '{key}'")


def scan_steps(problems: list[str]) -> int:
    n = 0
    for step in sorted(STEPS.glob("FT-*.sh")) + sorted(STEPS.glob("CUJ-*.sh")):
        text = step.read_text(encoding="utf-8")
        for m in re.finditer(r"agentwatch((?:\s+[A-Za-z0-9_./:=+-]+)+)", text):
            argv = ["agentwatch"] + m.group(1).split()
            # stop at shell metacharacters
            argv = [t for t in argv if not any(c in t for c in "|;&(){}")]
            _check_invocation(step.name, argv, problems)
            n += 1
    return n


def scan_drivers(problems: list[str]) -> int:
    n = 0
    for drv in sorted(DRIVERS.glob("*.py")):
        if drv.name in {"gen_cases.py", "collect-results.py", "check_cli_usage.py",
                        "build_fixtures.py", "dump_cli_surface.py"}:
            continue
        text = drv.read_text(encoding="utf-8")
        # list-literal invocations: ["agentwatch", "cmd", ...]
        for m in re.finditer(r"\[\s*[\"']agentwatch[\"']\s*,([^\]]*)\]", text):
            args = re.findall(r"[\"']([^\"']+)[\"']", m.group(1))
            _check_invocation(drv.name, ["agentwatch", *args], problems)
            n += 1
        # string invocations: "agentwatch cmd ..."
        for m in re.finditer(r"[\"']agentwatch((?: [A-Za-z0-9_./:=+-]+)+)[\"']", text):
            _check_invocation(drv.name, ["agentwatch"] + m.group(1).split(), problems)
            n += 1
        # python module usage
        for m in re.finditer(r"from agentwatch import ([A-Za-z0-9_, ]+)", text):
            for mod in m.group(1).replace(" ", "").split(","):
                if mod and mod not in _VALID_MODULES:
                    problems.append(f"{drv.name}: unknown module 'agentwatch.{mod}'")
        for m in re.finditer(r"agentwatch\.([a-z_][a-z0-9_]+)\.", text):
            if m.group(1) not in _VALID_MODULES:
                problems.append(f"{drv.name}: unknown module 'agentwatch.{m.group(1)}'")
    return n


def main() -> int:
    problems: list[str] = []
    n = scan_steps(problems) + scan_drivers(problems)
    print(f"cli-usage: scanned {n} invocation(s) across steps + drivers; "
          f"{len(CMDS)} commands in the surface")
    if problems:
        print(f"FAIL: {len(problems)} problem(s):")
        for p in problems:
            print("  -", p)
        return 1
    print("OK: every invocation matches the shipped CLI surface")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
