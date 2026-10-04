#!/usr/bin/env python3
"""Full-parity + PRD-coverage gate (M13 13.7, PRD 10 A1–A6).

Verifies that every feature that shipped in ``agent-exec-trace`` is delivered by
agentwatch itself, and that the PRD coverage matrix has no gap. Exits non-zero on
any missing row so the release gate cannot pass vacuously.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SDK = REPO / "packages" / "python-sdk"
sys.path.insert(0, str(SDK / "src"))


def _check_a1_sdk() -> list[str]:
    problems: list[str] = []
    from agentwatch import langgraph, raw, spans
    from agentwatch.redact import PrivacyMode

    for name in ("plan_span", "tool_span", "execute_tool_span", "retrieval_span", "memory_span", "approval_span"):
        if not hasattr(spans, name):
            problems.append(f"A1: missing span helper {name}")
    if not hasattr(raw, "trace_agent"):
        problems.append("A1: missing @trace_agent")
    if not hasattr(langgraph, "trace_graph"):
        problems.append("A1: missing LangGraph adapter")
    try:
        import agentwatch.pydantic as pydantic_adapter

        if not hasattr(pydantic_adapter, "trace_pydantic_agent"):
            problems.append("A1: missing PydanticAI adapter")
    except Exception as exc:  # noqa: BLE001
        problems.append(f"A1: PydanticAI adapter import failed: {exc}")
    if len(list(PrivacyMode)) != 4:
        problems.append("A1: expected four privacy modes")
    return problems


def _count_classes(path: Path, *, suffix: str = "Detector") -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return sum(
        1
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name.endswith(suffix)
    )


def _check_a2_detectors() -> list[str]:
    detectors = REPO / "services" / "analytics" / "src" / "analytics" / "detectors"
    rule = sum(
        _count_classes(detectors / name)
        for name in (
            "tool.py",
            "cost.py",
            "runtime.py",
            "retry.py",
            "interaction.py",
            "output.py",
            "cross_run.py",
            "claude_code.py",
        )
    )
    llm = _count_classes(detectors / "llm.py")
    problems: list[str] = []
    if rule < 35:
        problems.append(f"A2: expected >=35 rule detectors, found {rule}")
    if llm < 5:
        problems.append(f"A2: expected >=5 LLM detectors, found {llm}")
    return problems


def _check_a3_analytics() -> list[str]:
    src = REPO / "services" / "analytics" / "src" / "analytics"
    problems = []
    for name in ("ingest.py", "materializer.py", "worker.py", "models.py"):
        if not (src / name).exists():
            problems.append(f"A3: missing analytics {name}")
    if not list((src / "migrations" / "versions").glob("*.py")):
        problems.append("A3: no analytics migrations")
    return problems


def _check_a4_api() -> list[str]:
    routes = REPO / "services" / "api" / "src" / "api" / "routes.py"
    text = routes.read_text(encoding="utf-8") if routes.exists() else ""
    return [
        f"A4: missing endpoint {endpoint}"
        for endpoint in ("/runs", "/fleet", "/compare", "/anomalies")
        if endpoint not in text
    ]


def _check_a5_ui() -> list[str]:
    pages = REPO / "apps" / "web" / "src" / "pages"
    expected = ("FleetHealth.tsx", "RunTimeline.tsx", "VersionCompare.tsx", "AnomalyInbox.tsx")
    problems = [f"A5: missing view {name}" for name in expected if not (pages / name).exists()]
    a11y = REPO / "apps" / "web" / "src" / "__tests__" / "a11y.test.tsx"
    if "Agent Detail" not in a11y.read_text(encoding="utf-8"):
        problems.append("A5: Agent Detail view not covered by a11y tests")
    return problems


def _check_a6_stack() -> list[str]:
    problems: list[str] = []
    compose = REPO / "docker-compose.yml"
    text = compose.read_text(encoding="utf-8") if compose.exists() else ""
    for service in ("jaeger", "postgres", "api", "analytics", "web"):
        if f"  {service}:" not in text:
            problems.append(f"A6: compose missing service {service}")
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    for target in ("setup:", "lint:", "typecheck:", "test:", "stack-up:", "stack-down:", "seed-e2e:", "migrate:"):
        if target not in makefile:
            problems.append(f"A6: Makefile missing target {target}")
    if not (REPO / "examples" / "demo-agent" / "run_demo.py").exists():
        problems.append("A6: missing demo agent")
    if not (REPO / "scripts" / "seed-e2e-data.py").exists():
        problems.append("A6: missing seed script")
    if not list((REPO / "apps" / "web" / "tests" / "e2e").glob("*.spec.ts")):
        problems.append("A6: no Playwright E2E specs")
    if not (REPO / "docs" / "field-test" / "v0.1.0" / "FIELD_TEST_REPORT.md").exists():
        problems.append("A6: missing field-test report")
    return problems


def main() -> int:
    results = {
        "A1 instrumentation SDK": _check_a1_sdk(),
        "A2 detectors": _check_a2_detectors(),
        "A3 analytics pipeline": _check_a3_analytics(),
        "A4 read API": _check_a4_api(),
        "A5 operator UI": _check_a5_ui(),
        "A6 stack/tooling/evidence": _check_a6_stack(),
    }
    failures = 0
    for row, problems in results.items():
        if problems:
            failures += len(problems)
            print(f"FAIL {row}")
            for problem in problems:
                print(f"  - {problem}")
        else:
            print(f"PASS {row}")
    if failures:
        print(f"\nparity gate: {failures} gap(s)")
        return 1
    print("\nparity gate: all A1–A6 rows delivered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
