"""
Analysis and workflow route handlers.
Handles SWOT analysis workflow lifecycle.
"""

import uuid
import threading

from fastapi import APIRouter, HTTPException

from src.api.schemas import AnalysisRequest, WorkflowStartResponse
from src.services.workflow_store import (
    WORKFLOWS,
    add_activity_log,
    add_metric,
    run_workflow_background,
)

router = APIRouter()


@router.post("/analyze", response_model=WorkflowStartResponse)
async def start_analysis(request: AnalysisRequest):
    """Start a new SWOT analysis workflow."""
    workflow_id = str(uuid.uuid4())

    # Initialize workflow state
    WORKFLOWS[workflow_id] = {
        "status": "starting",
        "current_step": "input",
        "revision_count": 0,
        "score": 0,
        "company_name": request.name,
        "ticker": request.ticker,
        "strategy_focus": request.strategy_focus,
        "activity_log": [],
        "metrics": [],
        "mcp_status": {
            "financials": "idle",
            "valuation": "idle",
            "volatility": "idle",
            "macro": "idle",
            "news": "idle",
            "sentiment": "idle"
        },
        "llm_status": {
            "groq": "idle",
            "gemini": "idle",
            "openrouter": "idle"
        }
    }

    # Start workflow in background thread
    thread = threading.Thread(
        target=run_workflow_background,
        args=(workflow_id, request.name, request.ticker, request.strategy_focus),
        daemon=True
    )
    thread.start()

    return {"workflow_id": workflow_id}


@router.get("/workflow/{workflow_id}/status")
async def get_workflow_status(workflow_id: str):
    """Get current status of a workflow."""
    if workflow_id not in WORKFLOWS:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = WORKFLOWS[workflow_id]
    response = {
        "status": workflow.get("status", "unknown"),
        "current_step": workflow.get("current_step", "unknown"),
        "revision_count": workflow.get("revision_count", 0),
        "score": workflow.get("score", 0),
        "activity_log": workflow.get("activity_log", []),
        "metrics": workflow.get("metrics", []),
        "mcp_status": workflow.get("mcp_status", {}),
        "llm_status": workflow.get("llm_status", {}),
        "provider_used": workflow.get("provider_used"),
        "data_source": workflow.get("data_source")
    }

    # Include error message for error/aborted states
    if workflow.get("status") in ("error", "aborted"):
        response["error"] = workflow.get("error", "Unknown error")

    return response


@router.post("/workflow/{workflow_id}/retry-mcp/{mcp_name}")
async def retry_mcp_server(workflow_id: str, mcp_name: str):
    """
    Retry fetching data from a specific MCP server.

    Note: MCP servers are now managed by the external Research Service.
    Individual MCP retries are not available in this architecture.
    Start a new analysis to refresh all data.
    """
    raise HTTPException(
        status_code=501,
        detail="MCP retry not available. MCP servers are managed by the external Research Service. Please start a new analysis to refresh data."
    )


@router.get("/workflow/{workflow_id}/result")
async def get_workflow_result(workflow_id: str):
    """Get final result of a completed workflow."""
    if workflow_id not in WORKFLOWS:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = WORKFLOWS[workflow_id]

    if workflow.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Workflow not completed. Status: {workflow.get('status')}"
        )

    return workflow.get("result", {})
