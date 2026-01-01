from src.llm_client import get_llm_client
from langsmith import traceable
import json
import re
import time


def _add_activity_log(workflow_id, progress_store, step, message):
    """Helper to add activity log entry."""
    if workflow_id and progress_store:
        from src.services.workflow_store import add_activity_log
        add_activity_log(workflow_id, step, message)


# ============================================================
# DETERMINISTIC SCORING FUNCTIONS
# ============================================================

def check_swot_sections(report: str) -> dict:
    """
    Check if all 4 SWOT sections are present.
    Returns dict with section presence and score (0-2 points).
    """
    report_lower = report.lower()

    sections = {
        "strengths": bool(re.search(r'\bstrengths?\b', report_lower)),
        "weaknesses": bool(re.search(r'\bweaknesses?\b', report_lower)),
        "opportunities": bool(re.search(r'\bopportunit(y|ies)\b', report_lower)),
        "threats": bool(re.search(r'\bthreats?\b', report_lower))
    }

    present_count = sum(sections.values())
    score = 2 if present_count == 4 else (1 if present_count >= 2 else 0)

    return {
        "sections": sections,
        "present_count": present_count,
        "score": score,
        "max_score": 2
    }


def count_numeric_citations(report: str) -> dict:
    """
    Count specific facts/numbers cited in the report.
    Returns dict with count and score (0-3 points).
    """
    # Patterns for numeric citations
    patterns = [
        r'\$[\d,]+\.?\d*[BMK]?',           # Dollar amounts: $3.6B, $100M
        r'\d+\.?\d*\s*%',                   # Percentages: 7.26%, 42.59%
        r'\d+\.?\d*x',                      # Multiples: 0.13x, 2.35x
        r'P/E[:\s]+\d+',                    # P/E ratios
        r'P/S[:\s]+\d+',                    # P/S ratios
        r'P/B[:\s]+\d+',                    # P/B ratios
        r'EV/EBITDA[:\s]+\d+',              # EV/EBITDA
        r'PEG[:\s]+\d+',                    # PEG ratio
        r'VIX[:\s]+\d+',                    # VIX
        r'Beta[:\s]+\d+',                   # Beta
        r'\d+/100',                         # Scores: 67.38/100
        r'CAGR[:\s]*\d+',                   # CAGR
        r'\d{4}',                           # Years: 2024, 2025
    ]

    citations = []
    for pattern in patterns:
        matches = re.findall(pattern, report, re.IGNORECASE)
        citations.extend(matches)

    # Deduplicate
    unique_citations = list(set(citations))
    count = len(unique_citations)

    # Score: 0-2 citations = 0pts, 3-5 = 1pt, 6-10 = 2pts, 10+ = 3pts
    if count >= 10:
        score = 3
    elif count >= 6:
        score = 2
    elif count >= 3:
        score = 1
    else:
        score = 0

    return {
        "count": count,
        "examples": unique_citations[:10],  # Show first 10
        "score": score,
        "max_score": 3
    }


def check_data_sources(report: str, sources_available: list) -> dict:
    """
    Check if report references data from available MCP sources.
    Returns dict with coverage and score (0-2 points).
    """
    report_lower = report.lower()

    source_keywords = {
        "financials": ["revenue", "net margin", "debt", "cash flow", "eps", "earnings"],
        "volatility": ["beta", "volatility", "vix", "price swing"],
        "macro": ["gdp", "interest rate", "inflation", "unemployment", "fed"],
        "valuation": ["p/e", "p/s", "p/b", "ev/ebitda", "peg", "valuation", "market cap"],
        "news": ["news", "analyst", "article", "report"],
        "sentiment": ["sentiment", "bullish", "bearish", "reddit", "finnhub"]
    }

    sources_referenced = {}
    for source in sources_available:
        keywords = source_keywords.get(source, [])
        found = any(kw in report_lower for kw in keywords)
        sources_referenced[source] = found

    referenced_count = sum(sources_referenced.values())
    coverage_pct = (referenced_count / len(sources_available) * 100) if sources_available else 0

    # Score: <50% = 0pts, 50-75% = 1pt, >75% = 2pts
    if coverage_pct >= 75:
        score = 2
    elif coverage_pct >= 50:
        score = 1
    else:
        score = 0

    return {
        "sources_referenced": sources_referenced,
        "referenced_count": referenced_count,
        "total_available": len(sources_available),
        "coverage_pct": round(coverage_pct, 1),
        "score": score,
        "max_score": 2
    }


def check_section_balance(report: str) -> dict:
    """
    Check if SWOT sections are reasonably balanced (not all items in one section).
    Returns dict with balance info and score (0-1 point).
    """
    # Count bullet points or list items per section
    sections = ["strength", "weakness", "opportunit", "threat"]

    # Split report by sections and count items
    report_lower = report.lower()
    item_counts = {}

    for section in sections:
        # Find section and count bullet points after it
        pattern = rf'{section}.*?(?=(?:weakness|opportunit|threat|$))'
        match = re.search(pattern, report_lower, re.DOTALL)
        if match:
            section_text = match.group()
            # Count bullet points (-, *, •) or numbered items
            items = len(re.findall(r'[\-\*\•]\s+\w|^\d+\.\s+\w', section_text, re.MULTILINE))
            item_counts[section] = max(items, 1)  # At least 1 if section exists

    if not item_counts:
        return {"balanced": False, "score": 0, "max_score": 1}

    counts = list(item_counts.values())
    avg = sum(counts) / len(counts)

    # Check if any section has less than 25% of average (unbalanced)
    balanced = all(c >= avg * 0.25 for c in counts) if avg > 0 else False

    return {
        "item_counts": item_counts,
        "balanced": balanced,
        "score": 1 if balanced else 0,
        "max_score": 1
    }


def run_deterministic_checks(report: str, sources_available: list) -> dict:
    """
    Run all deterministic checks and return combined results.
    Total possible: 8 points
    """
    sections_check = check_swot_sections(report)
    citations_check = count_numeric_citations(report)
    sources_check = check_data_sources(report, sources_available)
    balance_check = check_section_balance(report)

    total_score = (
        sections_check["score"] +
        citations_check["score"] +
        sources_check["score"] +
        balance_check["score"]
    )
    max_score = 8

    # Convert to 1-10 scale (deterministic portion = 40% weight)
    normalized_score = (total_score / max_score) * 4  # 0-4 points

    return {
        "sections": sections_check,
        "citations": citations_check,
        "sources": sources_check,
        "balance": balance_check,
        "total_score": total_score,
        "max_score": max_score,
        "normalized_score": round(normalized_score, 2)
    }


# ============================================================
# LLM SCORING
# ============================================================

LLM_RUBRIC = """
You are a strategy evaluator. Given a SWOT analysis and the SOURCE DATA it should be based on, score it on a scale of 1 to 6.

Scoring Criteria:
1. Strategic Alignment (0-2 pts): Does the analysis align with the given strategic focus?
2. Data Grounding (0-2 pts): Does EVERY claim cite specific numbers from the source data? Penalize any invented facts not in the data.
3. Logical Consistency (0-2 pts): Are S/O clearly positive and W/T clearly negative? No contradictions?

IMPORTANT: If the analysis mentions facts/numbers NOT present in the source data, score Data Grounding as 0.

Respond in this JSON format only, no other text:
{
  "score": <int 1-6>,
  "strategic_alignment": <0-2>,
  "data_grounding": <0-2>,
  "logical_consistency": <0-2>,
  "reasoning": "<string>"
}
"""


def run_llm_evaluation(report: str, strategy_focus: str, llm, source_data: str = "") -> dict:
    """
    Run LLM-based qualitative evaluation.
    Returns score (1-6) and reasoning.
    """
    prompt = f"""
SWOT Draft:
{report}

Strategic Focus: {strategy_focus}

SOURCE DATA (the analysis should be based ONLY on this):
{source_data if source_data else "No source data provided"}

{LLM_RUBRIC}
"""

    response, provider, error, providers_failed = llm.query(prompt, temperature=0)

    if error:
        return {
            "score": 3,  # Default middle score
            "reasoning": f"LLM evaluation failed: {error}",
            "provider": provider,
            "providers_failed": providers_failed,
            "error": True
        }

    try:
        content = response.strip()
        if "{" in content:
            json_start = content.index("{")
            json_end = content.rindex("}") + 1
            content = content[json_start:json_end]

        parsed = json.loads(content)
        return {
            "score": min(max(parsed.get("score", 3), 1), 6),  # Clamp 1-6
            "strategic_alignment": parsed.get("strategic_alignment", 0),
            "data_grounding": parsed.get("data_grounding", 0),
            "logical_consistency": parsed.get("logical_consistency", 0),
            "reasoning": parsed.get("reasoning", "No reasoning provided"),
            "provider": provider,
            "providers_failed": providers_failed,
            "error": False
        }
    except (json.JSONDecodeError, ValueError) as e:
        return {
            "score": 3,
            "reasoning": f"JSON parsing failed: {str(e)[:100]}",
            "provider": provider,
            "providers_failed": providers_failed,
            "error": True
        }


# ============================================================
# HYBRID SCORING
# ============================================================

@traceable(name="Critic")
def critic_node(state, workflow_id=None, progress_store=None):
    """
    Critic node with hybrid scoring:
    - Deterministic checks (40%): sections, citations, source coverage, balance
    - LLM evaluation (60%): strategic alignment, insight quality, consistency

    Final score = deterministic (0-4) + LLM (0-6) = 1-10 scale
    """
    # Extract workflow_id and progress_store from state (graph invokes with state only)
    if workflow_id is None:
        workflow_id = state.get("workflow_id")
    if progress_store is None:
        progress_store = state.get("progress_store")

    # Skip evaluation if workflow has an error (abort mode)
    if state.get("error"):
        _add_activity_log(workflow_id, progress_store, "critic", "Skipping evaluation - workflow aborted")
        # Simplify error message for user display
        error_msg = state.get("error", "")
        if "429" in error_msg or "Too Many Requests" in error_msg:
            user_friendly_msg = "All AI providers are temporarily unavailable due to rate limits. Please wait a moment and try again."
        elif "All LLM providers failed" in error_msg:
            user_friendly_msg = "Unable to connect to AI providers. Please check your API keys or try again later."
        else:
            user_friendly_msg = "Analysis could not be completed. Please try again."
        state["critique"] = user_friendly_msg
        state["score"] = 0
        return state

    report = state.get("draft_report", "")
    strategy_focus = state.get("strategy_focus", "Cost Leadership")
    revision_count = state.get("revision_count", 0)

    # Log evaluation start
    _add_activity_log(workflow_id, progress_store, "critic", f"Evaluating SWOT quality (revision #{revision_count})...")

    # Parse sources_available from raw_data
    sources_available = []
    try:
        raw_data = json.loads(state.get("raw_data", "{}"))
        sources_available = raw_data.get("sources_available", [])
    except:
        sources_available = ["financials", "volatility", "macro", "valuation", "news", "sentiment"]

    # Run deterministic checks
    print("Running deterministic checks...")
    det_results = run_deterministic_checks(report, sources_available)
    det_score = det_results["normalized_score"]  # 0-4

    print(f"  Sections: {det_results['sections']['present_count']}/4 ({det_results['sections']['score']}/{det_results['sections']['max_score']} pts)")
    print(f"  Citations: {det_results['citations']['count']} found ({det_results['citations']['score']}/{det_results['citations']['max_score']} pts)")
    print(f"  Source Coverage: {det_results['sources']['coverage_pct']}% ({det_results['sources']['score']}/{det_results['sources']['max_score']} pts)")
    print(f"  Balance: {'Yes' if det_results['balance']['balanced'] else 'No'} ({det_results['balance']['score']}/{det_results['balance']['max_score']} pts)")
    print(f"  Deterministic Score: {det_score:.1f}/4")

    # Run LLM evaluation with source data for grounding check
    print("Running LLM evaluation...")
    llm = get_llm_client()
    _add_activity_log(workflow_id, progress_store, "critic", f"Calling LLM for quality evaluation...")
    start_time = time.time()

    # Get formatted source data for grounding verification
    source_data = state.get("raw_data", "")
    # Truncate if too long to avoid token limits
    if len(source_data) > 4000:
        source_data = source_data[:4000] + "\n... [truncated]"

    llm_results = run_llm_evaluation(report, strategy_focus, llm, source_data)
    llm_score = llm_results["score"]  # 1-6
    elapsed = time.time() - start_time
    provider = llm_results.get('provider', 'unknown')

    # Log failed providers
    providers_failed = llm_results.get('providers_failed', [])
    for pf in providers_failed:
        _add_activity_log(workflow_id, progress_store, "critic", f"LLM {pf['name']} failed: {pf['error']}")

    # Track failed providers in state for frontend
    if "llm_providers_failed" not in state:
        state["llm_providers_failed"] = []
    state["llm_providers_failed"].extend([pf["name"] for pf in providers_failed])

    print(f"  LLM Score: {llm_score}/6 ({provider})")
    _add_activity_log(workflow_id, progress_store, "critic", f"LLM evaluation via {provider} ({elapsed:.1f}s)")

    # Combine scores: deterministic (0-4) + LLM (1-6) = 1-10
    final_score = det_score + llm_score
    final_score = min(max(final_score, 1), 10)  # Clamp 1-10

    print(f"Critic scored: {final_score:.1f}/10 (det:{det_score:.1f} + llm:{llm_score})")

    # Log score result with revision decision hint
    score_msg = f"Score: {final_score:.0f}/10"
    if final_score < 7:
        score_msg += " - needs revision"
    else:
        score_msg += " - quality passed"
    _add_activity_log(workflow_id, progress_store, "critic", score_msg)

    # Build detailed critique
    critique_parts = [
        f"Deterministic Analysis ({det_results['total_score']}/{det_results['max_score']} pts):",
        f"  - SWOT Sections: {det_results['sections']['present_count']}/4 present",
        f"  - Numeric Citations: {det_results['citations']['count']} found",
        f"  - Data Source Coverage: {det_results['sources']['coverage_pct']}%",
        f"  - Section Balance: {'Balanced' if det_results['balance']['balanced'] else 'Unbalanced'}",
        "",
        f"LLM Evaluation ({llm_score}/6 pts):",
        f"  {llm_results['reasoning']}"
    ]

    state["critique"] = "\n".join(critique_parts)
    state["score"] = final_score
    state["critique_details"] = {
        "deterministic": det_results,
        "llm": llm_results,
        "final_score": final_score
    }

    # Update progress
    if workflow_id and progress_store:
        progress_store[workflow_id].update({
            "current_step": "critic",
            "revision_count": state.get("revision_count", 0),
            "score": final_score
        })

    return state
