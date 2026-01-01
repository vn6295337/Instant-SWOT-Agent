"""
Research Gateway

A2A client for calling the Research Service (Researcher-Agent) via Google A2A protocol.
Acts as the gateway between the main SWOT Agent and the external Research Service.

Supports real-time partial metrics streaming during task execution.
"""

import asyncio
import logging
import os
from typing import Optional, Callable, Set

import httpx

logger = logging.getLogger("research-gateway")

# Research Service configuration - defaults to HuggingFace Spaces deployment
A2A_RESEARCHER_URL = os.getenv(
    "A2A_RESEARCHER_URL",
    "https://vn6295337-researcher-agent.hf.space"
)
A2A_TIMEOUT = float(os.getenv("A2A_TIMEOUT", "120"))  # seconds (increased for remote calls)
A2A_POLL_INTERVAL = float(os.getenv("A2A_POLL_INTERVAL", "1"))  # seconds


class ResearchGatewayError(Exception):
    """Error communicating with Research Service."""
    pass


async def send_message(message_text: str) -> dict:
    """
    Send message/send request to start a research task.

    Args:
        message_text: Text message like "Research Tesla"

    Returns:
        Task info dict with task ID
    """
    async with httpx.AsyncClient() as client:
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "message/send",
            "params": {
                "message": {
                    "parts": [{"type": "text", "text": message_text}]
                }
            }
        }

        try:
            response = await client.post(
                A2A_RESEARCHER_URL,
                json=request,
                timeout=30
            )
            data = response.json()

            if "error" in data:
                raise ResearchGatewayError(f"A2A error: {data['error']}")

            return data.get("result", {})

        except httpx.RequestError as e:
            raise ResearchGatewayError(f"Connection error to {A2A_RESEARCHER_URL}: {e}")


async def get_task_status(task_id: str) -> dict:
    """
    Get task status via tasks/get request.

    Args:
        task_id: Task ID from message/send response

    Returns:
        Task status dict including partial_metrics (if WORKING) or artifacts (if COMPLETED)
    """
    async with httpx.AsyncClient() as client:
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/get",
            "params": {"taskId": task_id}
        }

        try:
            response = await client.post(
                A2A_RESEARCHER_URL,
                json=request,
                timeout=30
            )
            data = response.json()

            if "error" in data:
                raise ResearchGatewayError(f"A2A error: {data['error']}")

            return data.get("result", {}).get("task", {})

        except httpx.RequestError as e:
            raise ResearchGatewayError(f"Connection error: {e}")


async def wait_for_completion(
    task_id: str,
    timeout: float = None,
    progress_callback: Optional[Callable] = None,
    add_log: Optional[Callable] = None
) -> dict:
    """
    Poll task status until completed or failed.
    Emits partial_metrics via progress_callback during WORKING status.

    Args:
        task_id: Task ID to poll
        timeout: Max seconds to wait (default: A2A_TIMEOUT)
        progress_callback: Optional callback for granular metrics (source, metric, value)
        add_log: Optional callback for activity logging (step, message)

    Returns:
        Completed task dict with artifacts
    """
    if timeout is None:
        timeout = A2A_TIMEOUT

    elapsed = 0
    emitted_metrics: Set[str] = set()  # Track which metrics we've already emitted

    while elapsed < timeout:
        task = await get_task_status(task_id)
        status = task.get("status")

        # Emit partial metrics during WORKING status
        if status == "working" and progress_callback:
            partial_metrics = task.get("partial_metrics", [])
            for metric in partial_metrics:
                # Create unique key to avoid duplicate emissions
                metric_key = f"{metric.get('source')}:{metric.get('metric')}:{metric.get('value')}"
                if metric_key not in emitted_metrics:
                    progress_callback(
                        metric.get("source"),
                        metric.get("metric"),
                        metric.get("value")
                    )
                    emitted_metrics.add(metric_key)

        if status == "completed":
            if add_log:
                sources = len(task.get("artifacts", [{}])[0].get("data", {}).get("sources_available", []))
                add_log("researcher", f"Research completed: {sources} sources aggregated")
            return task
        elif status == "failed":
            error = task.get("error", {}).get("message", "Unknown error")
            if add_log:
                add_log("researcher", f"Research failed: {error}")
            raise ResearchGatewayError(f"Task failed: {error}")
        elif status == "canceled":
            if add_log:
                add_log("researcher", "Research task was canceled")
            raise ResearchGatewayError("Task was canceled")

        # Log polling status periodically
        if add_log and elapsed > 0 and elapsed % 5 == 0:
            add_log("researcher", f"Polling Research Service... ({int(elapsed)}s elapsed)")

        await asyncio.sleep(A2A_POLL_INTERVAL)
        elapsed += A2A_POLL_INTERVAL

    raise ResearchGatewayError(f"Task timed out after {timeout} seconds")


async def call_research_service(
    company: str,
    ticker: str = "",
    progress_callback: Optional[Callable] = None,
    add_log: Optional[Callable] = None
) -> dict:
    """
    High-level function to call Research Service and get results.
    Supports real-time partial metrics streaming.

    Args:
        company: Company name to research
        ticker: Optional ticker symbol
        progress_callback: Optional callback for granular metrics
        add_log: Optional callback for activity logging

    Returns:
        Research data dict from the Research Service
    """
    # Format message
    if ticker:
        message = f"Research {ticker} {company}"
    else:
        message = f"Research {company}"

    logger.info(f"Calling Research Service at {A2A_RESEARCHER_URL}: {message}")

    # Log connection
    if add_log:
        add_log("researcher", f"Connecting to Research Service...")
        add_log("researcher", f"A2A URL: {A2A_RESEARCHER_URL}")

    # Check health first
    healthy = await check_service_health()
    if not healthy:
        if add_log:
            add_log("researcher", "WARNING: Research Service health check failed, attempting anyway...")
        logger.warning("Research Service health check failed")

    if add_log:
        add_log("researcher", f"A2A handshake successful")

    # Send message to start task
    if add_log:
        add_log("researcher", f"Submitting research task for {company} ({ticker})...")

    result = await send_message(message)
    task_id = result.get("task", {}).get("id")

    if not task_id:
        raise ResearchGatewayError("No task ID returned from message/send")

    logger.info(f"Task created: {task_id}")
    if add_log:
        add_log("researcher", f"Task submitted: {task_id[:8]}...")
        add_log("researcher", "Fetching data from 6 MCP servers in parallel...")

    # Wait for completion with partial metrics streaming
    task = await wait_for_completion(
        task_id,
        progress_callback=progress_callback,
        add_log=add_log
    )

    # Extract data from artifacts
    artifacts = task.get("artifacts", [])
    if not artifacts:
        raise ResearchGatewayError("No artifacts in completed task")

    # Find data artifact
    for artifact in artifacts:
        if artifact.get("type") == "data":
            data = artifact.get("data", {})
            # Log sources
            if add_log:
                sources = data.get("sources_available", [])
                failed = data.get("sources_failed", [])
                add_log("researcher", f"Sources available: {', '.join(sources)}")
                if failed:
                    add_log("researcher", f"Sources failed: {', '.join(failed)}")
            return data

    raise ResearchGatewayError("No data artifact found in response")


async def check_service_health() -> bool:
    """
    Check if Research Service is healthy.

    Returns:
        True if server is healthy, False otherwise
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{A2A_RESEARCHER_URL}/health",
                timeout=10
            )
            data = response.json()
            return data.get("status") == "healthy"
    except Exception as e:
        logger.warning(f"Health check failed: {e}")
        return False


async def get_agent_card() -> Optional[dict]:
    """
    Fetch the agent card from the Research Service.

    Returns:
        Agent card dict or None if unavailable
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{A2A_RESEARCHER_URL}/.well-known/agent.json",
                timeout=10
            )
            return response.json()
    except Exception:
        return None


# Synchronous wrapper for LangGraph node
def call_research_service_sync(
    company: str,
    ticker: str = "",
    progress_callback: Optional[Callable] = None,
    add_log: Optional[Callable] = None
) -> dict:
    """
    Synchronous wrapper for call_research_service.

    Use this in LangGraph nodes that don't support async.
    """
    return asyncio.run(call_research_service(company, ticker, progress_callback, add_log))


# Backward compatibility aliases
A2AClientError = ResearchGatewayError
call_researcher_a2a = call_research_service
call_researcher_sync = call_research_service_sync
check_researcher_health = check_service_health
