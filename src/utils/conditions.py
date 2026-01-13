from typing import Literal


def should_continue(state) -> Literal["exit", "retry"]:
    """
    Conditional routing function that determines whether to continue
    the self-correcting loop or exit.

    Exit conditions:
    - Error set (LLM providers failed - abort immediately)
    - Analyzer revision skipped (LLM failed but using fallback draft - exit gracefully)
    - Score >= 6 (good quality)
    - Revision count >= 3 (max attempts reached)
    - Status is ESCALATE (critic escalated for human review)

    Continue conditions:
    - No error AND No revision skip AND Score < 6 AND Revisions < 3
    """
    # Abort immediately if error is set (critical failure)
    if state.get("error"):
        return "exit"

    # Exit gracefully if analyzer revision was skipped (using fallback draft)
    if state.get("analyzer_revision_skipped"):
        return "exit"

    # Exit if critic escalated (max iterations reached)
    critique_details = state.get("critique_details", {})
    if critique_details.get("status") == "ESCALATE":
        return "exit"

    current_score = state.get("score", 0)
    revision_count = state.get("revision_count", 0)

    # Exit if quality is good enough or max revisions reached
    if current_score >= 6 or revision_count >= 3:
        return "exit"

    # Continue the loop for improvement
    return "retry"