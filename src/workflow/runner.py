"""
Workflow execution wrapper with LangSmith tracing.
"""

from langsmith import traceable

from src.workflow.graph import app


@traceable(
    name="Run - Self-Correcting SWOT Analysis",
    tags=["cyclic", "quality-control", "demo"],
    metadata={"purpose": "iterative_improvement"}
)
def run_self_correcting_workflow(
    company_name: str = "Tesla",
    ticker: str = "",
    strategy_focus: str = "Cost Leadership",
    workflow_id: str = None,
    progress_store: dict = None
):
    """
    Execute the complete self-correcting SWOT analysis workflow.

    Args:
        company_name: Name of the company to analyze
        ticker: Stock ticker symbol
        strategy_focus: Strategic focus for analysis
        workflow_id: Optional workflow ID for progress tracking
        progress_store: Optional dict for storing progress updates

    Returns:
        Final workflow state with analysis results
    """
    # Initialize state with default values
    initial_state = {
        "company_name": company_name,
        "ticker": ticker or company_name,
        "strategy_focus": strategy_focus,
        "raw_data": None,
        "draft_report": None,
        "critique": None,
        "revision_count": 0,
        "messages": [],
        "score": 0,
        "data_source": "live",
        "provider_used": None,
        "sources_failed": [],
        "workflow_id": workflow_id,
        "progress_store": progress_store,
        "error": None
    }

    # Execute the workflow
    output = app.invoke(initial_state, config={
        "configurable": {
            "workflow_id": workflow_id,
            "progress_store": progress_store
        }
    })

    return output
