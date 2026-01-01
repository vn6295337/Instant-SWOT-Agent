"""
Workflow state management service.
Handles in-memory workflow storage and background execution.
"""

import json
import logging
import os
from datetime import datetime

from src.services.swot_parser import parse_swot_text
from src.utils.analysis_cache import get_cached_analysis, set_cached_analysis

logger = logging.getLogger(__name__)


# In-memory workflow storage
WORKFLOWS: dict = {}

# Configurable delay for granular progress events (ms)
METRIC_DELAY_MS = int(os.getenv("METRIC_DELAY_MS", "300"))


def add_activity_log(workflow_id: str, step: str, message: str):
    """Add an entry to the workflow activity log."""
    if workflow_id in WORKFLOWS:
        if "activity_log" not in WORKFLOWS[workflow_id]:
            WORKFLOWS[workflow_id]["activity_log"] = []
        WORKFLOWS[workflow_id]["activity_log"].append({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "step": step,
            "message": message
        })


def add_metric(workflow_id: str, source: str, metric: str, value):
    """Add a metric to the workflow metrics array and activity log."""
    if workflow_id in WORKFLOWS:
        if "metrics" not in WORKFLOWS[workflow_id]:
            WORKFLOWS[workflow_id]["metrics"] = []
        WORKFLOWS[workflow_id]["metrics"].append({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "source": source,
            "metric": metric,
            "value": value
        })
        # Also add to activity log for visibility
        display_value = f"{value:.2f}" if isinstance(value, float) else str(value)
        add_activity_log(workflow_id, source, f"Fetched {metric}: {display_value}")

        # Update MCP status to completed when we get a metric
        if "mcp_status" in WORKFLOWS[workflow_id] and source in WORKFLOWS[workflow_id]["mcp_status"]:
            WORKFLOWS[workflow_id]["mcp_status"][source] = "completed"


def update_mcp_status(workflow_id: str, source: str, status: str):
    """Update MCP server status (idle/executing/completed/failed)."""
    if workflow_id in WORKFLOWS and "mcp_status" in WORKFLOWS[workflow_id]:
        if source in WORKFLOWS[workflow_id]["mcp_status"]:
            WORKFLOWS[workflow_id]["mcp_status"][source] = status


def run_workflow_background(workflow_id: str, company_name: str, ticker: str, strategy_focus: str):
    """Execute workflow in background thread with progress tracking."""
    try:
        # Check cache first
        add_activity_log(workflow_id, "cache", f"Checking cache for {ticker}")
        WORKFLOWS[workflow_id]["current_step"] = "cache"

        cached = get_cached_analysis(ticker)
        if cached:
            # Cache hit - use cached result
            add_activity_log(workflow_id, "cache", f"Cache HIT - {ticker} analysis found in history")
            add_activity_log(workflow_id, "cache", f"Returning cached result (skipping agentic workflow)")
            WORKFLOWS[workflow_id].update({
                "status": "completed",
                "current_step": "completed",
                "revision_count": cached.get("revision_count", 0),
                "score": cached.get("score", 0),
                "data_source": "cache",
                "result": {
                    "company_name": cached.get("company_name", company_name),
                    "score": cached.get("score", 0),
                    "revision_count": cached.get("revision_count", 0),
                    "report_length": cached.get("report_length", 0),
                    "critique": cached.get("critique", ""),
                    "swot_data": cached.get("swot_data", {}),
                    "raw_report": cached.get("raw_report", ""),
                    "data_source": "cache",
                    "provider_used": cached.get("provider_used", "cached"),
                    "_cache_info": cached.get("_cache_info", {})
                }
            })
            return

        add_activity_log(workflow_id, "cache", f"Cache MISS - {ticker} not in history")
        add_activity_log(workflow_id, "cache", f"Proceeding with full agentic workflow...")

        # Import here to avoid circular imports and init issues
        from src.workflow.graph import app as graph_app

        # Update status to running
        WORKFLOWS[workflow_id]["status"] = "running"
        WORKFLOWS[workflow_id]["current_step"] = "researcher"
        add_activity_log(workflow_id, "input", f"Starting analysis for {company_name} ({ticker})")

        # Initialize MCP status
        WORKFLOWS[workflow_id]["mcp_status"] = {
            "financials": "idle",
            "valuation": "idle",
            "volatility": "idle",
            "macro": "idle",
            "news": "idle",
            "sentiment": "idle"
        }

        # Initialize state
        state = {
            "company_name": company_name,
            "ticker": ticker,
            "strategy_focus": strategy_focus,
            "raw_data": None,
            "draft_report": None,
            "critique": None,
            "revision_count": 0,
            "messages": [],
            "score": 0,
            "data_source": "live",
            "provider_used": None,
            "workflow_id": workflow_id,
            "progress_store": WORKFLOWS
        }

        # Execute workflow
        result = graph_app.invoke(state)

        # Update MCP status based on sources
        sources_available = result.get("sources_available", [])
        sources_failed = result.get("sources_failed", [])
        mcp_status = WORKFLOWS[workflow_id]["mcp_status"]

        for source in sources_available:
            if source in mcp_status:
                mcp_status[source] = "completed"

        for source in sources_failed:
            if source in mcp_status:
                mcp_status[source] = "failed"
                add_activity_log(workflow_id, source, f"MCP server failed")

        # Update LLM status based on failed providers and used provider
        llm_providers_failed = result.get("llm_providers_failed", [])
        provider_used = result.get("provider_used", "")
        llm_status = WORKFLOWS[workflow_id]["llm_status"]

        # Mark failed providers
        for provider in llm_providers_failed:
            if provider in llm_status:
                llm_status[provider] = "failed"

        # Mark the used provider as completed
        if provider_used:
            provider_name = provider_used.split(":")[0]
            if provider_name in llm_status:
                llm_status[provider_name] = "completed"

        # Parse SWOT from draft report
        swot_data = parse_swot_text(result.get("draft_report", ""))

        # Supplement with MCP-aggregated SWOT data (ensures weaknesses/threats aren't lost)
        try:
            raw_data = result.get("raw_data", "{}")
            if isinstance(raw_data, str):
                raw_data = json.loads(raw_data)
            mcp_swot = raw_data.get("aggregated_swot", {})
            if mcp_swot:
                # Add MCP items that aren't already in parsed data
                for category in ["strengths", "weaknesses", "opportunities", "threats"]:
                    existing = set(item.lower()[:50] for item in swot_data.get(category, []))
                    for item in mcp_swot.get(category, []):
                        # Only add if not a duplicate (check first 50 chars lowercased)
                        if item.lower()[:50] not in existing:
                            swot_data[category].append(item)
                            existing.add(item.lower()[:50])
        except Exception as e:
            logger.warning(f"Could not merge MCP SWOT data: {e}")

        # Check if workflow ended with an error (LLM failures etc)
        if result.get("error"):
            error_msg = result.get("error")
            add_activity_log(workflow_id, "workflow", f"Workflow failed: {error_msg}")
            WORKFLOWS[workflow_id].update({
                "status": "aborted",
                "error": error_msg,
                "current_step": "aborted"
            })
            return

        # Build final result
        final_result = {
            "company_name": company_name,
            "score": result.get("score", 0),
            "revision_count": result.get("revision_count", 0),
            "report_length": len(result.get("draft_report", "")),
            "critique": result.get("critique", ""),
            "swot_data": swot_data,
            "raw_report": result.get("draft_report", ""),
            "data_source": result.get("data_source", "unknown"),
            "provider_used": result.get("provider_used", "unknown")
        }

        # Cache the final result
        set_cached_analysis(ticker, company_name, final_result)
        add_activity_log(workflow_id, "cache", f"Cached analysis for {ticker}")

        # Update with final result
        WORKFLOWS[workflow_id].update({
            "status": "completed",
            "current_step": "completed",
            "revision_count": result.get("revision_count", 0),
            "score": result.get("score", 0),
            "result": final_result
        })

    except Exception as e:
        error_msg = str(e)
        # Determine if this is an abort (critical) or error (retryable)
        # Aborts: Core MCP failures, insufficient data
        is_abort = any(phrase in error_msg for phrase in [
            "Insufficient core data",
            "All MCP servers failed",
            "Need at least 2 of"
        ])

        WORKFLOWS[workflow_id].update({
            "status": "aborted" if is_abort else "error",
            "error": error_msg
        })
