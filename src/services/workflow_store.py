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


def add_metric(workflow_id: str, source: str, metric: str, value,
               end_date: str = None, fiscal_year: int = None, form: str = None):
    """Add a metric to the workflow metrics array and activity log.

    Args:
        workflow_id: Workflow identifier
        source: Data source (e.g., 'fundamentals', 'valuation')
        metric: Metric name (e.g., 'Revenue', 'P/E')
        value: Metric value
        end_date: Fiscal period end date (e.g., '2023-09-30')
        fiscal_year: Fiscal year number (e.g., 2023)
        form: SEC form type ('10-K' for annual, '10-Q' for quarterly)
    """
    if workflow_id in WORKFLOWS:
        if "metrics" not in WORKFLOWS[workflow_id]:
            WORKFLOWS[workflow_id]["metrics"] = []

        metric_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "source": source,
            "metric": metric,
            "value": value
        }

        # Add temporal fields if provided
        if end_date:
            metric_entry["end_date"] = end_date
        if fiscal_year:
            metric_entry["fiscal_year"] = fiscal_year
        if form:
            metric_entry["form"] = form

        WORKFLOWS[workflow_id]["metrics"].append(metric_entry)

        # Build display value with fiscal period if available
        display_value = f"{value:.2f}" if isinstance(value, float) else str(value)
        if fiscal_year:
            period_label = f"FY {fiscal_year}" if form == "10-K" else f"Q{_quarter_from_date(end_date)} {fiscal_year}" if end_date else f"FY {fiscal_year}"
            display_value = f"{display_value} ({period_label})"
        add_activity_log(workflow_id, source, f"Fetched {metric}: {display_value}")

        # Update MCP status to completed when we get a metric
        if "mcp_status" in WORKFLOWS[workflow_id] and source in WORKFLOWS[workflow_id]["mcp_status"]:
            WORKFLOWS[workflow_id]["mcp_status"][source] = "completed"


def set_mcp_executing(workflow_id: str):
    """Set all MCP servers to 'executing' state when research starts."""
    if workflow_id in WORKFLOWS and "mcp_status" in WORKFLOWS[workflow_id]:
        for source in WORKFLOWS[workflow_id]["mcp_status"]:
            WORKFLOWS[workflow_id]["mcp_status"][source] = "executing"


def _quarter_from_date(date_str: str) -> int:
    """Extract quarter number from a date string (YYYY-MM-DD)."""
    if not date_str:
        return 0
    try:
        month = int(date_str.split("-")[1])
        return (month - 1) // 3 + 1
    except (ValueError, IndexError):
        return 0


def update_mcp_status(workflow_id: str, source: str, status: str):
    """Update MCP server status (idle/executing/completed/failed)."""
    if workflow_id in WORKFLOWS and "mcp_status" in WORKFLOWS[workflow_id]:
        if source in WORKFLOWS[workflow_id]["mcp_status"]:
            WORKFLOWS[workflow_id]["mcp_status"][source] = status


def _extract_metrics_from_raw_data(raw_data: dict) -> list:
    """Extract metrics array from raw_data for cached analysis display.

    Parses the multi_source structure to extract quantitative metrics
    in the same format as add_metric() produces.

    Args:
        raw_data: Parsed raw_data dict from cached analysis

    Returns:
        List of metric entries with source, metric, value, and temporal fields
    """
    metrics = []
    timestamp = datetime.utcnow().isoformat() + "Z"

    multi_source = raw_data.get("multi_source", {})

    # Extract fundamentals from SEC EDGAR and Yahoo Finance
    fin_all = multi_source.get("fundamentals_all", {})
    sec_data = fin_all.get("sec_edgar", {}).get("data", {})
    yf_fund = fin_all.get("yahoo_finance", {}).get("data", {})

    # Fundamentals metrics to extract
    fin_metrics = [
        "revenue", "net_income", "gross_profit", "operating_income",
        "gross_margin_pct", "operating_margin_pct", "net_margin_pct",
        "free_cash_flow", "operating_cash_flow", "total_assets",
        "total_liabilities", "stockholders_equity", "cash",
        "long_term_debt", "net_debt", "rd_expense", "eps", "debt_to_equity"
    ]

    for metric_name in fin_metrics:
        # Prefer SEC EDGAR data, fall back to Yahoo Finance
        # Track which source the data actually came from
        sec_metric = sec_data.get(metric_name)
        yf_metric = yf_fund.get(metric_name)

        if sec_metric is not None:
            metric_data = sec_metric
            actual_source = "sec_edgar"
        elif yf_metric is not None:
            metric_data = yf_metric
            actual_source = "yahoo_finance"
        else:
            continue

        entry = {
            "timestamp": timestamp,
            "source": "fundamentals",
            "metric": metric_name,
            "data_source": actual_source,  # Track actual data source for frontend
        }
        if isinstance(metric_data, dict):
            entry["value"] = metric_data.get("value")
            if metric_data.get("end_date"):
                entry["end_date"] = metric_data["end_date"]
            if metric_data.get("fiscal_year"):
                entry["fiscal_year"] = metric_data["fiscal_year"]
            if metric_data.get("form"):
                entry["form"] = metric_data["form"]
        else:
            entry["value"] = metric_data

        if entry.get("value") is not None:
            metrics.append(entry)

    # Extract valuation metrics from Yahoo Finance
    val_all = multi_source.get("valuation_all", {})
    yf_val = val_all.get("yahoo_finance", {}).get("data", {})

    # Get valuation fetch date if available (point-in-time data)
    # MCP server returns regular_market_time from Yahoo Finance quote data
    val_fetch_date = (
        yf_val.get("_fetch_date")
        or yf_val.get("fetch_date")
        or multi_source.get("valuation_all", {}).get("yahoo_finance", {}).get("regular_market_time")
    )

    val_metrics = [
        "market_cap", "enterprise_value", "trailing_pe", "forward_pe",
        "pb_ratio", "ps_ratio", "trailing_peg", "price_to_fcf",
        "ev_ebitda", "ev_revenue", "revenue_growth", "earnings_growth"
    ]

    for metric_name in val_metrics:
        metric_data = yf_val.get(metric_name)
        if metric_data is not None:
            entry = {
                "timestamp": timestamp,
                "source": "valuation",
                "metric": metric_name,
            }
            if isinstance(metric_data, dict):
                entry["value"] = metric_data.get("value")
                # Extract date if available in metric data
                if metric_data.get("date"):
                    entry["end_date"] = metric_data["date"]
                elif metric_data.get("end_date"):
                    entry["end_date"] = metric_data["end_date"]
                elif val_fetch_date:
                    entry["end_date"] = val_fetch_date
            else:
                entry["value"] = metric_data
                if val_fetch_date:
                    entry["end_date"] = val_fetch_date

            if entry.get("value") is not None:
                metrics.append(entry)

    # Extract volatility metrics
    vol_all = multi_source.get("volatility_all", {})
    ctx = vol_all.get("market_volatility_context", {})
    yf_vol = vol_all.get("yahoo_finance", {}).get("data", {})

    # VIX and VXN from market context
    for vol_metric in ["vix", "vxn"]:
        vol_data = ctx.get(vol_metric, {})
        if vol_data.get("value") is not None:
            entry = {
                "timestamp": timestamp,
                "source": "volatility",
                "metric": vol_metric,
                "value": vol_data["value"]
            }
            if vol_data.get("date"):
                entry["end_date"] = vol_data["date"]
            metrics.append(entry)

    # Beta and volatility from Yahoo Finance
    # Get volatility fetch date if available (MCP returns generated_at at response level)
    vol_fetch_date = (
        yf_vol.get("_fetch_date")
        or yf_vol.get("fetch_date")
        or (vol_all.get("generated_at", "")[:10] if vol_all.get("generated_at") else None)
    )

    for vol_metric in ["beta", "historical_volatility", "implied_volatility"]:
        metric_data = yf_vol.get(vol_metric)
        if metric_data is not None:
            entry = {
                "timestamp": timestamp,
                "source": "volatility",
                "metric": vol_metric,
            }
            if isinstance(metric_data, dict):
                entry["value"] = metric_data.get("value")
                if metric_data.get("date"):
                    entry["end_date"] = metric_data["date"]
                elif metric_data.get("end_date"):
                    entry["end_date"] = metric_data["end_date"]
                elif vol_fetch_date:
                    entry["end_date"] = vol_fetch_date
            else:
                entry["value"] = metric_data
                if vol_fetch_date:
                    entry["end_date"] = vol_fetch_date

            if entry.get("value") is not None:
                metrics.append(entry)

    # Extract macro indicators
    macro_all = multi_source.get("macro_all", {})
    bea_bls = macro_all.get("bea_bls", {}).get("data", {})
    fred = macro_all.get("fred", {}).get("data", {})

    macro_metrics = ["gdp_growth", "cpi_inflation", "unemployment", "interest_rate"]

    for metric_name in macro_metrics:
        # Prefer BEA/BLS, fall back to FRED
        metric_data = bea_bls.get(metric_name) or fred.get(metric_name)
        if metric_data is not None and isinstance(metric_data, dict):
            if metric_data.get("value") is not None:
                entry = {
                    "timestamp": timestamp,
                    "source": "macro",
                    "metric": metric_name,
                    "value": metric_data["value"]
                }
                if metric_data.get("date"):
                    entry["end_date"] = metric_data["date"]
                metrics.append(entry)

    return metrics


def run_workflow_background(workflow_id: str, company_name: str, ticker: str, strategy_focus: str,
                            skip_cache: bool = False, user_api_keys: dict = None):
    """Execute workflow in background thread with progress tracking."""
    try:
        # Check cache first (unless skip_cache is True)
        add_activity_log(workflow_id, "cache", f"Checking cache for {ticker}")
        WORKFLOWS[workflow_id]["current_step"] = "cache"

        if skip_cache:
            add_activity_log(workflow_id, "cache", f"Cache skipped - running fresh analysis")
            cached = None
        else:
            cached = get_cached_analysis(ticker)

        if cached:
            # Cache hit - use cached result
            add_activity_log(workflow_id, "cache", f"Cache HIT - {ticker} analysis found in history")
            add_activity_log(workflow_id, "cache", f"Returning cached result (skipping agentic workflow)")

            # Extract metrics from cached raw_data for frontend display
            cached_raw_data = cached.get("raw_data", {})
            cached_metrics = _extract_metrics_from_raw_data(cached_raw_data)

            WORKFLOWS[workflow_id].update({
                "status": "completed",
                "current_step": "completed",
                "revision_count": cached.get("revision_count", 0),
                "score": cached.get("score", 0),
                "data_source": "cache",
                "metrics": cached_metrics,  # Populate metrics for frontend
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
                    "raw_data": cached.get("raw_data", {}),
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
            "fundamentals": "idle",
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
            "progress_store": WORKFLOWS,
            "user_api_keys": user_api_keys or {}  # Pass user API keys to nodes
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
        # IMPORTANT: Do this BEFORE checking for errors so frontend sees failures
        llm_providers_failed = result.get("llm_providers_failed", [])
        provider_used = result.get("provider_used", "")
        llm_status = WORKFLOWS[workflow_id]["llm_status"]

        # Mark failed providers (dedupe: one log line per provider, not per call)
        for provider in dict.fromkeys(llm_providers_failed):
            if provider in llm_status:
                llm_status[provider] = "failed"
                add_activity_log(workflow_id, "llm", f"{provider.capitalize()} provider failed")

        # Mark the used provider as completed
        if provider_used:
            provider_name = provider_used.split(":")[0]
            if provider_name in llm_status:
                llm_status[provider_name] = "completed"

        # Check if workflow ended with an error (LLM failures etc)
        # Do this BEFORE parsing SWOT so we properly abort on errors
        if result.get("error"):
            error_msg = result.get("error")
            add_activity_log(workflow_id, "workflow", f"Workflow failed: {error_msg}")
            WORKFLOWS[workflow_id].update({
                "status": "aborted",
                "error": error_msg,
                "current_step": "aborted"
            })
            return

        # Parse SWOT from draft report (edge contract: uncited lines become
        # recommendations, data-quality prose is separated - neither leaks
        # into the quadrant tables)
        parsed_sections = parse_swot_text(result.get("draft_report", ""))
        recommendations = parsed_sections.pop("recommendations", [])
        llm_quality_notes = parsed_sections.pop("data_quality_notes", [])
        swot_data = parsed_sections

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

        # Parse raw_data for MCP display
        raw_data_parsed = {}
        try:
            raw_data_str = result.get("raw_data", "{}")
            if isinstance(raw_data_str, str):
                raw_data_parsed = json.loads(raw_data_str)
            else:
                raw_data_parsed = raw_data_str or {}
        except Exception as e:
            logger.warning(f"Could not parse raw_data: {e}")

        # Extract business address from company profile
        company_profile = raw_data_parsed.get("company_profile", {})
        business_address = company_profile.get("business_address", "")

        # Generate data quality notes from metric reference
        metric_reference = result.get("metric_reference", {})
        quality_notes = {"high_confidence": [], "gaps_or_stale": [], "assumptions": []}
        if metric_reference:
            from src.nodes.analyzer import _generate_data_quality_notes
            quality_notes = _generate_data_quality_notes(metric_reference)
        quality_notes["assumptions"] = llm_quality_notes
        # Surface gate findings in the user-visible quality notes
        for gap in result.get("data_gaps") or []:
            quality_notes.setdefault("gaps_or_stale", []).append(
                f"Not available from data sources: {gap}")
        for cat, key, value in result.get("suspect_metrics") or []:
            quality_notes.setdefault("gaps_or_stale", []).append(
                f"Discarded implausible value: {cat}.{key} = {value:g}")

        # Build final result
        final_result = {
            "company_name": company_name,
            "business_address": business_address,
            "score": result.get("score", 0),
            "revision_count": result.get("revision_count", 0),
            "report_length": len(result.get("draft_report", "")),
            "critique": result.get("critique", ""),
            "quality_notes": quality_notes,
            "swot_data": swot_data,
            "raw_report": result.get("draft_report", ""),
            "data_source": result.get("data_source", "unknown"),
            "provider_used": result.get("provider_used", "unknown"),
            "recommendations": recommendations,
            # Canonical [M##] list - the SAME numbering the SWOT text cites.
            # UI/PDF must render their Quantitative Data table from this, not
            # from the streamed metrics (whose row order produced misaligned refs)
            "metric_reference": [
                {
                    "ref": ref_id,
                    "key": entry.get("key"),
                    "value": entry.get("raw_value"),
                    "as_of": entry.get("as_of_date"),
                    "category": entry.get("category"),
                }
                for ref_id, entry in sorted(metric_reference.items())
            ],
            "raw_data": raw_data_parsed
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
        # Aborts: Core MCP failures, insufficient data, LLM failures
        is_abort = any(phrase in error_msg for phrase in [
            "Insufficient core data",
            "All MCP servers failed",
            "Need at least 2 of",
            "All LLM providers failed"
        ])

        WORKFLOWS[workflow_id].update({
            "status": "aborted" if is_abort else "error",
            "error": error_msg
        })
