"""Unit tests for the self-correcting loop routing logic."""

from src.utils.conditions import should_continue


def test_exits_on_error():
    assert should_continue({"error": "LLM providers failed", "score": 2}) == "exit"


def test_exits_when_revision_skipped():
    state = {"analyzer_revision_skipped": True, "score": 3, "revision_count": 0}
    assert should_continue(state) == "exit"


def test_exits_on_escalate():
    state = {
        "critique_details": {"status": "ESCALATE"},
        "score": 3,
        "revision_count": 1,
    }
    assert should_continue(state) == "exit"


def test_exits_on_good_score():
    assert should_continue({"score": 6, "revision_count": 0}) == "exit"
    assert should_continue({"score": 9.5, "revision_count": 0}) == "exit"


def test_exits_at_max_revisions():
    assert should_continue({"score": 4, "revision_count": 3}) == "exit"
    assert should_continue({"score": 4, "revision_count": 5}) == "exit"


def test_retries_on_low_score_with_revisions_left():
    assert should_continue({"score": 5.0, "revision_count": 0}) == "retry"
    assert should_continue({"score": 5.9, "revision_count": 2}) == "retry"


def test_retries_with_missing_defaults():
    # No score/revision_count in state defaults to 0/0 -> retry
    assert should_continue({}) == "retry"
