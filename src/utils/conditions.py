from typing import Literal

def should_continue(state) -> Literal["exit", "retry"]:
    """
    Conditional routing function that determines whether to continue
    the self-correcting loop or exit.

    Exit conditions:
    - Error set (LLM providers failed - abort immediately)
    - Editor skipped (LLM failed but using fallback draft - exit gracefully)
    - Score >= 7 (good quality)
    - Revision count > 3 (max attempts reached)

    Continue conditions:
    - No error AND No editor skip AND Score < 7 AND Revisions <= 3
    """
    # Abort immediately if error is set (critical failure)
    if state.get("error"):
        return "exit"

    # Exit gracefully if editor was skipped (using fallback draft)
    if state.get("editor_skipped"):
        return "exit"

    current_score = state.get("score", 0)
    revision_count = state.get("revision_count", 0)

    # Exit if quality is good enough or max revisions exceeded
    if current_score >= 7 or revision_count > 3:
        return "exit"

    # Continue the loop for improvement
    return "retry"