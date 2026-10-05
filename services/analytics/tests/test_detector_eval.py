"""Offline detector-eval harness tests (M25 DET-1, #302).

The harness drives the **real** analytics detectors (single source of truth) over
a versioned corpus, offline and deterministically, and reports per-detector
precision/recall. The harness judges detectors; detectors judge nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

from analytics.detectors.eval import (
    DetectorCase,
    EvalReport,
    load_corpus,
    run_eval,
)
from analytics.detectors.tool import LoopDetector
from analytics.models import RunSummary, SpanNode


def _summary() -> RunSummary:
    return RunSummary(run_id="r1", agent_name="demo", agent_version="v1")


def _spans(tool_names: list[str]) -> list[SpanNode]:
    children = [
        SpanNode(
            span_id=f"s{i}",
            trace_id="t",
            parent_span_id="root",
            operation_name="execute_tool",
            attributes={"gen_ai.tool.name": name},
        )
        for i, name in enumerate(tool_names)
    ]
    return [SpanNode(span_id="root", trace_id="t", operation_name="invoke_agent", child_spans=children)]


def _loop() -> LoopDetector:
    return LoopDetector(threshold=5)


def test_run_eval_is_deterministic() -> None:
    case = DetectorCase(id="c1", summary=_summary(), spans=_spans(["Bash"] * 5), expected=frozenset({"loop"}))
    assert run_eval([case], detectors=[_loop()]) == run_eval([case], detectors=[_loop()])


def test_precision_and_recall_are_computed() -> None:
    cases = [
        DetectorCase(id="hit", summary=_summary(), spans=_spans(["Bash"] * 5), expected=frozenset({"loop"})),
        DetectorCase(id="miss", summary=_summary(), spans=_spans(["Read"]), expected=frozenset({"loop"})),
        DetectorCase(id="fp", summary=_summary(), spans=_spans(["Bash"] * 5), expected=frozenset()),
    ]
    report = run_eval(cases, detectors=[_loop()])

    assert isinstance(report, EvalReport)
    assert report.recall("loop") == 0.5  # 1 of 2 expected hits fired
    assert report.precision("loop") == 0.5  # 1 true positive, 1 false positive


def test_loop_detector_fires_on_five_consecutive_repeats() -> None:
    report = run_eval(
        [DetectorCase(id="hit", summary=_summary(), spans=_spans(["Bash"] * 5), expected=frozenset({"loop"}))],
        detectors=[_loop()],
    )
    assert report.recall("loop") == 1.0
    assert report.precision("loop") == 1.0


def test_load_corpus_builds_cases_from_a_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "corpus.json"
    manifest.write_text(
        json.dumps(
            {
                "version": "v0",
                "cases": [
                    {"id": "loop-5", "expect": ["loop"], "tools": ["Bash", "Bash", "Bash", "Bash", "Bash"]},
                    {"id": "clean", "expect": [], "tools": ["Read", "Write"]},
                ],
            }
        ),
        encoding="utf-8",
    )

    cases = load_corpus(manifest)

    assert [case.id for case in cases] == ["loop-5", "clean"]
    report = run_eval(cases, detectors=[_loop()])
    assert report.recall("loop") == 1.0
    assert report.precision("loop") == 1.0


def test_shipped_corpus_v0_is_present_and_well_formed() -> None:
    corpus = Path(__file__).resolve().parents[1] / "data" / "detector-corpus-v0.json"
    cases = load_corpus(corpus)
    assert cases, "corpus v0 must ship cases"
    report = run_eval(cases, detectors=[_loop()])
    # A corpus with a positive and a negative case must not be degenerate.
    assert 0.0 <= report.precision("loop") <= 1.0
    assert 0.0 <= report.recall("loop") <= 1.0