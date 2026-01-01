"""
Research Gateway Node

Fetches data from the Research Service via A2A protocol.
The Research Service internally calls all 6 MCP servers using TRUE MCP protocol.

This node acts as the gateway between the main SWOT Agent and the external Research Service.
"""

import asyncio
import json
from langsmith import traceable

from src.utils.ticker_lookup import get_ticker, normalize_company_name


async def _fetch_via_research_gateway(company: str, ticker: str = None, progress_callback=None, add_log=None) -> dict:
    """Async helper to fetch data via Research Gateway (A2A protocol)."""
    from src.nodes.research_gateway import call_research_service

    # Use provided ticker or lookup from company name
    if not ticker:
        ticker = get_ticker(company)

    if not ticker:
        print(f"Could not determine ticker for '{company}', using company name as ticker")
        ticker = company.upper().replace(" ", "")[:5]

    # Normalize company name for display
    company_name = normalize_company_name(company)

    print(f"Calling Research Service for {company_name} ({ticker})...")

    # Call Research Service with callbacks for real-time streaming
    result = await call_research_service(
        company_name,
        ticker,
        progress_callback=progress_callback,
        add_log=add_log
    )

    return result


@traceable(name="Researcher")
def researcher_node(state, workflow_id=None, progress_store=None):
    """
    Research Gateway node that fetches data via A2A protocol.

    Calls the external Research Service which internally fetches from 6 MCP servers:
    Financials, Volatility, Macro, Valuation, News, Sentiment
    """
    company = state["company_name"]
    ticker = state.get("ticker")  # Use ticker from stock search if available

    # Extract workflow_id and progress_store from state (graph invokes with state only)
    if workflow_id is None:
        workflow_id = state.get("workflow_id")
    if progress_store is None:
        progress_store = state.get("progress_store")

    print(f"[DEBUG] researcher_node: workflow_id={workflow_id}, progress_store={'yes' if progress_store else 'no'}")

    # Update progress if tracking is enabled
    if workflow_id and progress_store:
        progress_store[workflow_id].update({
            "current_step": "researcher",
            "revision_count": state.get("revision_count", 0),
            "score": state.get("score", 0)
        })

    # Helper to add activity log
    def add_log(step: str, message: str):
        if workflow_id and progress_store:
            from src.services.workflow_store import add_activity_log
            add_activity_log(workflow_id, step, message)

    # Create progress callback for granular metric events
    def progress_callback(source: str, metric: str, value):
        if workflow_id and progress_store:
            # Import here to avoid circular imports
            from src.services.workflow_store import add_metric
            add_metric(workflow_id, source, metric, value)

    try:
        # Fetch via Research Gateway (A2A protocol)
        print("[Research Gateway] Calling Research Service via A2A...")
        result = asyncio.run(_fetch_via_research_gateway(
            company,
            ticker,
            progress_callback=progress_callback,
            add_log=add_log
        ))
        state["data_source"] = "a2a"
        # Note: Metrics are streamed via partial_metrics during A2A polling

        # Check MCP source availability with tiered logic
        # Core sources (need at least 2 of 3): financials, valuation, volatility
        # Supplementary sources (non-blocking): macro, news, sentiment
        CORE_SOURCES = {"financials", "valuation", "volatility"}
        SUPPLEMENTARY_SOURCES = {"macro", "news", "sentiment"}

        sources_available = set(result.get("sources_available", []))
        sources_failed = result.get("sources_failed", [])

        core_available = sources_available & CORE_SOURCES
        core_failed = CORE_SOURCES - core_available
        supplementary_failed = set(sources_failed) & SUPPLEMENTARY_SOURCES

        # Log supplementary failures as non-critical
        for source in supplementary_failed:
            add_log("researcher", f"{source.capitalize()} unavailable (non-critical)")

        # Log core failures as critical
        for source in core_failed:
            add_log("researcher", f"{source.capitalize()} unavailable (critical)")

        # Abort if 2+ core sources failed (need at least 2 of 3)
        if len(core_available) < 2:
            failed_list = ", ".join(sorted(core_failed))
            raise RuntimeError(f"Insufficient core data: {failed_list} unavailable. Need at least 2 of: Financials, Valuation, Volatility.")

        if sources_available:
            state["raw_data"] = json.dumps(result, indent=2, default=str)
            state["sources_failed"] = sources_failed

            print(f"  - Sources available: {result['sources_available']}")
            if sources_failed:
                print(f"  - Sources failed: {sources_failed}")
        else:
            # All MCPs failed - raise error
            raise RuntimeError(f"All MCP servers failed for {company}. Check API configurations.")

    except Exception as e:
        print(f"Research failed: {e}")
        raise RuntimeError(f"Research failed for {company}: {str(e)}")

    return state
