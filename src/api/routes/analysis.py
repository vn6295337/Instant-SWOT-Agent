"""
Analysis and workflow route handlers.
Handles SWOT analysis workflow lifecycle.
"""

import time
import uuid
import threading
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request

from src.api.schemas import AnalysisRequest, WorkflowStartResponse
from src.services.workflow_store import (
    WORKFLOWS,
    add_activity_log,
    add_metric,
    run_workflow_background,
)

router = APIRouter()

# Abuse guards for the public endpoint (in-memory, per-process)
WORKFLOW_TTL_SECONDS = 3600       # evict finished workflows after 1h
MAX_ACTIVE_WORKFLOWS = 3          # concurrent analyses per instance
RATE_LIMIT_WINDOW_SECONDS = 3600
RATE_LIMIT_MAX_REQUESTS = 10      # analyses per IP per window
_REQUESTS_BY_IP: dict = defaultdict(deque)


def _evict_stale_workflows():
    """Drop workflows past TTL so the in-memory store cannot grow unbounded."""
    cutoff = time.time() - WORKFLOW_TTL_SECONDS
    for wid in [
        wid for wid, wf in WORKFLOWS.items()
        if wf.get("created_at", 0) < cutoff
        and wf.get("status") not in ("starting", "running")
    ]:
        WORKFLOWS.pop(wid, None)


def _check_rate_limit(client_ip: str):
    now = time.time()
    window = _REQUESTS_BY_IP[client_ip]
    while window and window[0] < now - RATE_LIMIT_WINDOW_SECONDS:
        window.popleft()
    if len(window) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded: max "
                   f"{RATE_LIMIT_MAX_REQUESTS} analyses per hour per client."
        )
    window.append(now)


@router.post("/analyze", response_model=WorkflowStartResponse)
async def start_analysis(request: AnalysisRequest, http_request: Request):
    """Start a new SWOT analysis workflow."""
    _evict_stale_workflows()

    client_ip = http_request.client.host if http_request.client else "unknown"
    _check_rate_limit(client_ip)

    active = sum(
        1 for wf in WORKFLOWS.values()
        if wf.get("status") in ("starting", "running")
    )
    if active >= MAX_ACTIVE_WORKFLOWS:
        raise HTTPException(
            status_code=429,
            detail="Server busy: too many concurrent analyses. Retry shortly."
        )

    workflow_id = str(uuid.uuid4())

    # Initialize workflow state
    WORKFLOWS[workflow_id] = {
        "created_at": time.time(),
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
            "fundamentals": "idle",
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
        args=(workflow_id, request.name, request.ticker, request.strategy_focus,
              request.skip_cache, request.user_api_keys),
        daemon=True
    )
    thread.start()

    return {"workflow_id": workflow_id}


def _status_payload(workflow: dict) -> dict:
    """Status snapshot shared by the polling and SSE endpoints."""
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


@router.get("/workflow/{workflow_id}/status")
async def get_workflow_status(workflow_id: str):
    """Get current status of a workflow."""
    if workflow_id not in WORKFLOWS:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return _status_payload(WORKFLOWS[workflow_id])


@router.get("/workflow/{workflow_id}/events")
async def stream_workflow_events(workflow_id: str):
    """
    Server-Sent Events stream of workflow status.

    Emits a status snapshot whenever it changes (checked every second) and
    closes after a terminal status. The frontend falls back to polling
    /status if SSE is unavailable.
    """
    import asyncio
    import json as _json

    from fastapi.responses import StreamingResponse

    if workflow_id not in WORKFLOWS:
        raise HTTPException(status_code=404, detail="Workflow not found")

    async def event_stream():
        last_sent = None
        # Hard cap: 15 min per connection so abandoned tabs cannot pin
        # the stream forever
        for _ in range(900):
            workflow = WORKFLOWS.get(workflow_id)
            if workflow is None:
                yield 'data: {"status": "error", "error": "Workflow evicted"}\n\n'
                return
            payload = _json.dumps(_status_payload(workflow))
            if payload != last_sent:
                yield f"data: {payload}\n\n"
                last_sent = payload
            if workflow.get("status") in ("completed", "aborted", "error"):
                return
            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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
