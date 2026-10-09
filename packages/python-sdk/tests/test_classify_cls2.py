"""``cls2`` test/build/lint outcome classes (M30 EXT-4, #482).

``cls2`` extends the shared argument classifier with deterministic command
outcome classes while ``cls1`` pattern outputs stay reproducible. Facts only:
``pass``/``fail`` is an exit-status fact, never a quality verdict.
"""

from __future__ import annotations

from datetime import datetime, timezone

from agentwatch.classify import (
    CLASSIFIER_VERSION,
    FAIL,
    OUTCOME_BUILD,
    OUTCOME_LINT,
    OUTCOME_TEST,
    OUTCOME_VERSION,
    PASS,
    UNKNOWN,
    OutcomeFact,
    classify_command,
    classify_outcome,
    classify_record_outcome,
    outcome_table,
    pattern_table,
)
from agentwatch.records import AgentIdentity, AgentRecord, Outcome, StepType, ToolCall

AT = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)


def _record(
    command: str,
    *,
    outcome: Outcome = Outcome.OK,
    response: dict[str, object] | None = None,
) -> AgentRecord:
    return AgentRecord(
        session_id="s1",
        agent=AgentIdentity(identity="a"),
        tool=ToolCall(name="Bash", arguments={"command": command}, response=response),
        outcome=outcome,
        started_at=AT,
        step_type=StepType.ACT,
    )


def _fact(
    command: str, *, exit_code: int | None = None, succeeded: bool | None = None
) -> OutcomeFact:
    fact = classify_outcome(command, exit_code=exit_code, succeeded=succeeded)
    assert fact is not None
    return fact


def test_cls1_outputs_are_reproducible() -> None:
    # cls2 must not redefine the published cls1 table or the classifier version.
    assert CLASSIFIER_VERSION == "cls1"
    assert OUTCOME_VERSION == "cls2"
    assert pattern_table()
    facts = classify_command("pip install requests")
    assert [fact.category for fact in facts] == ["command:install"]


def test_cls2_table_is_versioned_and_shaped() -> None:
    assert OUTCOME_VERSION == "cls2"
    table = outcome_table()
    assert table
    assert all({"id", "category", "confidence", "pattern", "detail"} <= set(row) for row in table)
    categories = {row["category"] for row in table}
    assert categories == {OUTCOME_TEST, OUTCOME_BUILD, OUTCOME_LINT}


def test_test_build_lint_commands_are_classified() -> None:
    assert _fact("pytest -q").category == OUTCOME_TEST
    assert _fact("python -m pytest tests -q").category == OUTCOME_TEST
    assert _fact("cargo test").category == OUTCOME_TEST
    assert _fact("npm run build").category == OUTCOME_BUILD
    assert _fact("tsc --noEmit").category == OUTCOME_BUILD
    assert _fact("ruff check .").category == OUTCOME_LINT
    assert _fact("eslint src/").category == OUTCOME_LINT


def test_make_targets_disambiguate_test_lint_build() -> None:
    assert _fact("make test").category == OUTCOME_TEST
    assert _fact("make lint").category == OUTCOME_LINT
    assert _fact("make build").category == OUTCOME_BUILD


def test_unrecognized_command_has_no_outcome_class() -> None:
    assert classify_outcome("echo hello") is None


def test_exit_status_is_a_fact_and_unknown_stays_unknown() -> None:
    assert _fact("pytest", exit_code=0).status == PASS
    assert _fact("pytest", exit_code=1).status == FAIL
    assert _fact("pytest").status == UNKNOWN
    assert _fact("pytest", succeeded=True).status == PASS
    assert _fact("pytest", succeeded=False).status == FAIL


def test_record_outcome_reads_exit_code_and_record_outcome() -> None:
    fact = classify_record_outcome(
        _record("pytest -q", outcome=Outcome.OK, response={"exit_code": 0})
    )
    assert fact is not None
    assert (fact.category, fact.status) == (OUTCOME_TEST, PASS)

    failed = classify_record_outcome(_record("pytest -q", outcome=Outcome.ERROR))
    assert failed is not None
    assert failed.status == FAIL

    # An explicit exit code is the stronger fact and overrides the coarse outcome.
    overridden = classify_record_outcome(
        _record("pytest -q", outcome=Outcome.ERROR, response={"exit_code": 0})
    )
    assert overridden is not None
    assert overridden.status == PASS

    # A non-outcome command (or a non-shell tool) yields no cls2 fact.
    assert classify_record_outcome(_record("echo hello")) is None


def test_cls2_status_language_is_not_a_verdict() -> None:
    table = outcome_table()
    forbidden = {"good", "bad", "healthy", "unhealthy", "severity", "score"}
    for row in table:
        assert not (forbidden & set(row["detail"].lower().split()))
