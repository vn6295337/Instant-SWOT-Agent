from src.tools import get_strategy_context
from src.llm_client import get_llm_client
from langsmith import traceable
import time
import json


def _add_activity_log(workflow_id, progress_store, step, message):
    """Helper to add activity log entry."""
    if workflow_id and progress_store:
        from src.services.workflow_store import add_activity_log
        add_activity_log(workflow_id, step, message)


def _extract_key_metrics(raw_data: str) -> dict:
    """Extract and format key metrics from raw JSON data."""
    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError:
        return {"error": "Could not parse raw data"}

    metrics = data.get("metrics", {})
    extracted = {
        "company": data.get("company_name", "Unknown"),
        "ticker": data.get("ticker", "N/A"),
        "financials": {},
        "valuation": {},
        "volatility": {},
        "macro": {},
        "news": {},
        "sentiment": {},
        "aggregated_swot": data.get("aggregated_swot", {})
    }

    # Extract financials
    fin = metrics.get("financials", {})
    if fin and "error" not in fin:
        fin_data = fin.get("financials", {})
        extracted["financials"] = {
            "revenue": fin_data.get("revenue", {}).get("value"),
            "revenue_cagr_3yr": fin_data.get("revenue_cagr_3yr"),
            "net_margin": fin_data.get("net_margin"),
            "eps": fin_data.get("eps", {}).get("value"),
            "debt_to_equity": fin.get("debt", {}).get("debt_to_equity"),
            "free_cash_flow": fin.get("cash_flow", {}).get("free_cash_flow", {}).get("value"),
        }

    # Extract valuation
    val = metrics.get("valuation", {})
    if val and "error" not in val:
        val_metrics = val.get("metrics", {})
        pe = val_metrics.get("pe_ratio", {})
        extracted["valuation"] = {
            "pe_trailing": pe.get("trailing") if isinstance(pe, dict) else pe,
            "pe_forward": pe.get("forward") if isinstance(pe, dict) else None,
            "pb_ratio": val_metrics.get("pb_ratio"),
            "ps_ratio": val_metrics.get("ps_ratio"),
            "ev_ebitda": val_metrics.get("ev_ebitda"),
            "valuation_signal": val.get("overall_signal"),
        }

    # Extract volatility
    vol = metrics.get("volatility", {})
    if vol and "error" not in vol:
        vol_metrics = vol.get("metrics", {})
        extracted["volatility"] = {
            "beta": vol_metrics.get("beta", {}).get("value"),
            "vix": vol_metrics.get("vix", {}).get("value"),
            "historical_volatility": vol_metrics.get("historical_volatility", {}).get("value"),
        }

    # Extract macro
    macro = metrics.get("macro", {})
    if macro and "error" not in macro:
        macro_metrics = macro.get("metrics", {})
        extracted["macro"] = {
            "gdp_growth": macro_metrics.get("gdp_growth", {}).get("value"),
            "interest_rate": macro_metrics.get("interest_rate", {}).get("value"),
            "inflation": macro_metrics.get("cpi_inflation", {}).get("value"),
            "unemployment": macro_metrics.get("unemployment", {}).get("value"),
        }

    # Extract news
    news = metrics.get("news", {})
    if news and "error" not in news:
        articles = news.get("articles", [])
        extracted["news"] = {
            "article_count": len(articles),
            "headlines": [a.get("title", "")[:100] for a in articles[:5]],
        }

    # Extract sentiment
    sent = metrics.get("sentiment", {})
    if sent and "error" not in sent:
        extracted["sentiment"] = {
            "composite_score": sent.get("composite_score"),
            "overall_category": sent.get("overall_swot_category"),
        }

    return extracted


def _format_metrics_for_prompt(extracted: dict) -> str:
    """Format extracted metrics into a clear text for the LLM."""
    lines = []
    lines.append(f"Company: {extracted['company']} ({extracted['ticker']})")
    lines.append("")

    # Financials
    fin = extracted.get("financials", {})
    if fin:
        lines.append("=== FINANCIALS (from SEC EDGAR) ===")
        if fin.get("revenue"):
            lines.append(f"- Revenue: ${fin['revenue']:,.0f}" if isinstance(fin['revenue'], (int, float)) else f"- Revenue: {fin['revenue']}")
        if fin.get("revenue_cagr_3yr"):
            lines.append(f"- Revenue CAGR (3yr): {fin['revenue_cagr_3yr']:.1f}%")
        if fin.get("net_margin"):
            lines.append(f"- Net Margin: {fin['net_margin']:.1f}%")
        if fin.get("eps"):
            lines.append(f"- EPS: ${fin['eps']:.2f}")
        if fin.get("debt_to_equity"):
            lines.append(f"- Debt/Equity: {fin['debt_to_equity']:.2f}")
        if fin.get("free_cash_flow"):
            lines.append(f"- Free Cash Flow: ${fin['free_cash_flow']:,.0f}" if isinstance(fin['free_cash_flow'], (int, float)) else f"- Free Cash Flow: {fin['free_cash_flow']}")
        lines.append("")

    # Valuation
    val = extracted.get("valuation", {})
    if val:
        lines.append("=== VALUATION (from Yahoo Finance) ===")
        if val.get("pe_trailing"):
            lines.append(f"- P/E Ratio (trailing): {val['pe_trailing']:.1f}")
        if val.get("pe_forward"):
            lines.append(f"- P/E Ratio (forward): {val['pe_forward']:.1f}")
        if val.get("pb_ratio"):
            lines.append(f"- P/B Ratio: {val['pb_ratio']:.2f}")
        if val.get("ps_ratio"):
            lines.append(f"- P/S Ratio: {val['ps_ratio']:.2f}")
        if val.get("ev_ebitda"):
            lines.append(f"- EV/EBITDA: {val['ev_ebitda']:.1f}")
        if val.get("valuation_signal"):
            lines.append(f"- Overall Signal: {val['valuation_signal']}")
        lines.append("")

    # Volatility
    vol = extracted.get("volatility", {})
    if vol:
        lines.append("=== VOLATILITY/RISK ===")
        if vol.get("beta"):
            lines.append(f"- Beta: {vol['beta']:.2f}")
        if vol.get("vix"):
            lines.append(f"- VIX (market fear index): {vol['vix']:.1f}")
        if vol.get("historical_volatility"):
            lines.append(f"- Historical Volatility: {vol['historical_volatility']:.1f}%")
        lines.append("")

    # Macro
    macro = extracted.get("macro", {})
    if macro:
        lines.append("=== MACROECONOMIC ENVIRONMENT (from FRED) ===")
        if macro.get("gdp_growth"):
            lines.append(f"- GDP Growth: {macro['gdp_growth']:.1f}%")
        if macro.get("interest_rate"):
            lines.append(f"- Federal Funds Rate: {macro['interest_rate']:.2f}%")
        if macro.get("inflation"):
            lines.append(f"- Inflation (CPI): {macro['inflation']:.1f}%")
        if macro.get("unemployment"):
            lines.append(f"- Unemployment: {macro['unemployment']:.1f}%")
        lines.append("")

    # News
    news = extracted.get("news", {})
    if news:
        lines.append("=== RECENT NEWS ===")
        lines.append(f"- Articles found: {news.get('article_count', 0)}")
        for headline in news.get("headlines", []):
            lines.append(f"  • {headline}")
        lines.append("")

    # Sentiment
    sent = extracted.get("sentiment", {})
    if sent:
        lines.append("=== MARKET SENTIMENT ===")
        if sent.get("composite_score") is not None:
            lines.append(f"- Composite Score: {sent['composite_score']:.2f}")
        if sent.get("overall_category"):
            lines.append(f"- Overall: {sent['overall_category']}")
        lines.append("")

    # Pre-built SWOT hints from MCP servers
    swot = extracted.get("aggregated_swot", {})
    if any(swot.get(k) for k in ["strengths", "weaknesses", "opportunities", "threats"]):
        lines.append("=== DATA-DRIVEN SWOT SIGNALS (from metrics analysis) ===")
        for category in ["strengths", "weaknesses", "opportunities", "threats"]:
            items = swot.get(category, [])
            if items:
                lines.append(f"{category.upper()}:")
                for item in items:
                    lines.append(f"  • {item}")
        lines.append("")

    return "\n".join(lines)


@traceable(name="Analyzer")
def analyzer_node(state, workflow_id=None, progress_store=None):
    # Extract workflow_id and progress_store from state (graph invokes with state only)
    if workflow_id is None:
        workflow_id = state.get("workflow_id")
    if progress_store is None:
        progress_store = state.get("progress_store")

    # Update progress if tracking is enabled
    if workflow_id and progress_store:
        progress_store[workflow_id].update({
            "current_step": "analyzer",
            "revision_count": state.get("revision_count", 0),
            "score": state.get("score", 0)
        })

    llm = get_llm_client()
    raw = state["raw_data"]
    strategy_name = state.get("strategy_focus", "Cost Leadership")
    strategy_context = get_strategy_context(strategy_name)
    company = state["company_name"]
    ticker = state.get("ticker", "")

    # Extract and format metrics for better LLM understanding
    extracted = _extract_key_metrics(raw)
    formatted_data = _format_metrics_for_prompt(extracted)

    # Log LLM call start
    _add_activity_log(workflow_id, progress_store, "analyzer", f"Calling LLM to generate SWOT analysis...")

    prompt = f"""You are a financial analyst creating a SWOT analysis for {company} ({ticker}).

CRITICAL INSTRUCTIONS:
1. ONLY use the data provided below. DO NOT invent or assume any information.
2. Every point MUST cite specific numbers from the data (e.g., "P/E of 21.3", "Beta of 0.88").
3. If data is missing for a category, say "Insufficient data" - do NOT make up information.
4. Focus on what the numbers actually mean for this specific company.
5. This is a {company} - tailor your analysis to their industry (e.g., bank, tech, retail).

Strategic Focus: {strategy_name}
Context: {strategy_context}

=== ACTUAL DATA FROM FINANCIAL SOURCES ===
{formatted_data}

Based ONLY on the data above, provide a SWOT analysis in this format:

Strengths:
- [Cite specific metrics that show strengths]

Weaknesses:
- [Cite specific metrics that show weaknesses]

Opportunities:
- [Cite macro/market conditions that create opportunities]

Threats:
- [Cite risks from volatility, macro conditions, or sentiment]

Remember: Every bullet point must reference actual data provided above. Do not invent any figures or facts."""
    start_time = time.time()
    response, provider, error, providers_failed = llm.query(prompt, temperature=0)
    elapsed = time.time() - start_time

    # Log failed providers
    for pf in providers_failed:
        _add_activity_log(workflow_id, progress_store, "analyzer", f"LLM {pf['name']} failed: {pf['error']}")

    # Track failed providers in state for frontend
    if "llm_providers_failed" not in state:
        state["llm_providers_failed"] = []
    state["llm_providers_failed"].extend([pf["name"] for pf in providers_failed])

    if error:
        state["draft_report"] = f"Error generating analysis: {error}"
        state["provider_used"] = None
        state["error"] = error  # Signal workflow to abort
        _add_activity_log(workflow_id, progress_store, "analyzer", f"LLM error: {error}")
        _add_activity_log(workflow_id, progress_store, "analyzer", "Workflow aborted - all LLM providers unavailable")
    else:
        state["draft_report"] = response
        state["provider_used"] = provider
        _add_activity_log(workflow_id, progress_store, "analyzer", f"SWOT generated via {provider} ({elapsed:.1f}s)")

    return state
