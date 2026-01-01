from src.llm_client import get_llm_client
from langsmith import traceable
import time
import json


def _add_activity_log(workflow_id, progress_store, step, message):
    """Helper to add activity log entry."""
    if workflow_id and progress_store:
        from src.services.workflow_store import add_activity_log
        add_activity_log(workflow_id, step, message)


@traceable(name="Editor")
def editor_node(state, workflow_id=None, progress_store=None):
    """
    Editor node that revises the SWOT draft based on critique feedback.
    Increments the revision count and returns the improved draft.
    """
    # Extract workflow_id and progress_store from state (graph invokes with state only)
    if workflow_id is None:
        workflow_id = state.get("workflow_id")
    if progress_store is None:
        progress_store = state.get("progress_store")

    current_revision = state.get("revision_count", 0) + 1

    # Update progress if tracking is enabled
    if workflow_id and progress_store:
        progress_store[workflow_id].update({
            "current_step": "editor",
            "revision_count": state.get("revision_count", 0),
            "score": state.get("score", 0)
        })

    # Skip if workflow already has an error (abort mode)
    if state.get("error"):
        _add_activity_log(workflow_id, progress_store, "editor", f"Skipping revision - workflow aborted")
        state["revision_count"] = current_revision
        return state

    # Log revision start
    _add_activity_log(workflow_id, progress_store, "editor", f"Revision #{current_revision} in progress...")

    llm = get_llm_client()
    strategy_name = state.get("strategy_focus", "Cost Leadership")

    # Get source data for grounding - editor must use ONLY this data
    source_data = state.get("raw_data", "")
    # Truncate if too long to avoid token limits
    if len(source_data) > 4000:
        source_data = source_data[:4000] + "\n... [truncated]"

    # Prepare the revision prompt with source data for grounding
    prompt = f"""
You are revising a SWOT analysis based on critique feedback.

CRITICAL GROUNDING RULES:
1. You may ONLY use facts and numbers from the SOURCE DATA provided below.
2. DO NOT invent, assume, or fabricate any information not in the source data.
3. Every claim must cite specific numbers from the source data.
4. If the critique asks for information not in the source data, state "Data not available".

SOURCE DATA (use ONLY this for facts and numbers):
{source_data}

CURRENT DRAFT:
{state['draft_report']}

CRITIQUE:
{state['critique']}

Strategic Focus: {strategy_name}

REVISION INSTRUCTIONS:
1. Address the critique points using ONLY data from SOURCE DATA above
2. Ensure all 4 SWOT sections are present and complete
3. Every bullet point must cite specific metrics from the source data
4. Make sure strengths/opportunities are positive, weaknesses/threats are negative
5. Align analysis with {strategy_name} strategic focus
6. If data is missing for a point, remove that point rather than inventing data

Return only the improved SWOT analysis. Do NOT include any facts not found in the SOURCE DATA.
"""

    # Get the revised draft from LLM
    start_time = time.time()
    response, provider, error, providers_failed = llm.query(prompt, temperature=0)
    elapsed = time.time() - start_time

    # Log failed providers
    for pf in providers_failed:
        _add_activity_log(workflow_id, progress_store, "editor", f"LLM {pf['name']} failed: {pf['error']}")

    # Track failed providers in state for frontend
    if "llm_providers_failed" not in state:
        state["llm_providers_failed"] = []
    state["llm_providers_failed"].extend([pf["name"] for pf in providers_failed])

    if error:
        print(f"Editor LLM error: {error}")
        _add_activity_log(workflow_id, progress_store, "editor", f"Revision failed: {error}")

        # Graceful degradation based on revision count
        if current_revision == 1:
            # First revision failed - use Analyzer's original draft
            _add_activity_log(workflow_id, progress_store, "editor", "Using initial draft from Analyzer (revision unavailable)")
            # Don't set error - allow workflow to continue with original draft
            # draft_report already contains Analyzer's output
            state["editor_skipped"] = True
        else:
            # Revision > 1 failed - use the last successful revision
            _add_activity_log(workflow_id, progress_store, "editor", f"Using revision #{current_revision - 1} draft (further revision unavailable)")
            # Don't set error - allow workflow to complete with previous draft
            state["editor_skipped"] = True
    else:
        state["draft_report"] = response
        state["provider_used"] = provider
        state["editor_skipped"] = False
        _add_activity_log(workflow_id, progress_store, "editor", f"Revision #{current_revision} completed via {provider} ({elapsed:.1f}s)")

    # Increment revision count
    state["revision_count"] = current_revision

    # Update progress with new revision count
    if workflow_id and progress_store:
        progress_store[workflow_id].update({
            "current_step": "editor",
            "revision_count": state["revision_count"],
            "score": state.get("score", 0)
        })

    return state
