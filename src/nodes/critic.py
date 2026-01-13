from src.llm_client import get_llm_client
from langsmith import traceable
import json
import time

# Layer 4: Deterministic numeric validation
from src.utils.numeric_validator import (
    validate_numeric_accuracy,
    validate_uncited_numbers,
    validate_minimum_citations,
)
from src.nodes.analyzer import _verify_reference_integrity


def _add_activity_log(workflow_id, progress_store, step, message):
    """Helper to add activity log entry."""
    if workflow_id and progress_store:
        from src.services.workflow_store import add_activity_log
        add_activity_log(workflow_id, step, message)


# ============================================================
# LLM-ONLY WEIGHTED RUBRIC EVALUATION
# ============================================================

CRITIC_SYSTEM_PROMPT = """You are a SWOT Output Critic and Quality Gatekeeper.

## ROLE
Act as an independent, impartial evaluator that reviews SWOT analyses. Your function is to:
1. Verify factual accuracy against provided input data
2. Assess quality against a weighted rubric
3. Decide whether the output PASSES or FAILS
4. Provide actionable feedback if rejected

You are a quality gate, not a collaborator. Be strict.

## VALID METRICS SCHEMA

**Fundamentals:** revenue, net_income, net_margin_pct, total_assets, total_liabilities, stockholders_equity, operating_margin_pct, total_debt, operating_cash_flow, free_cash_flow

**Valuation:** current_price, market_cap, enterprise_value, trailing_pe, forward_pe, ps_ratio, pb_ratio, trailing_peg, forward_peg, earnings_growth, revenue_growth

**Volatility:** vix, vxn, beta, historical_volatility, implied_volatility

**Macro:** gdp_growth, interest_rate, cpi_inflation, unemployment

**Qualitative:** News (title, date, source, url), Sentiment (title, date, source, url)

## EVALUATION RUBRIC (Weighted)

### 1. Evidence Grounding (25%) — HARD FLOOR: >=7
- All claims cite specific metrics from input data
- No fabricated metrics (hallucination check)
- Field names match schema
- 9-10: Every claim traceable; 7-8: Nearly all grounded; 5-6: Most grounded, 2-3 unverifiable; 3-4: Multiple unsupported; 1-2: Clear hallucinations
- **If ANY fabricated metric detected, cap at 4**

### 2. Constraint Compliance (20%) — HARD FLOOR: >=6
- No buy/sell/hold recommendations
- Temporal labels accurate (TTM, FY, forward)
- "DATA NOT PROVIDED" used for missing metrics
- 9-10: All constraints respected; 7-8: Minor issues; 5-6: One moderate violation; 3-4: Multiple violations; 1-2: Systematic violations

### 3. Specificity & Actionability (20%)
- Company-specific, not generic templates
- Quantified findings (not "strong margins" but "31% operating margin")
- Avoids business cliches
- 9-10: Every point specific and quantified; 7-8: Mostly specific; 5-6: Mix of specific/generic; 3-4: Mostly generic; 1-2: Template-like

### 4. Strategic Insight (15%)
- Synthesis across multiple data sources
- Prioritization by materiality
- Goes beyond restating metrics to interpreting implications
- 9-10: Identifies causal relationships; 7-8: Good synthesis; 5-6: Surface-level; 3-4: Restates metrics; 1-2: No value-add

### 5. Completeness & Balance (10%)
Required sections:
- Strengths (Finding, Strategic Implication, Durability)
- Weaknesses (Finding, Severity, Trend, Remediation Levers)
- Opportunities (Catalyst, Timing, Execution Requirements)
- Threats (Risk Factor, Probability, Impact, Mitigation Options)
- Data Quality Notes
- 9-10: All present and substantive; 7-8: All present, minor gaps; 5-6: Missing 1 section; 3-4: Multiple missing; 1-2: Major gaps

### 6. Clarity & Structure (10%)
- Clean formatting, logical grouping
- Easy to scan (not walls of text)
- No contradictions
- 9-10: Impeccable; 7-8: Well-structured; 5-6: Readable but dense; 3-4: Hard to follow; 1-2: Poorly organized

## PASS CONDITIONS (ALL must be met)
1. Weighted average >= 6.0
2. Evidence Grounding >= 6
3. Constraint Compliance >= 6
4. No individual criterion below 5

## OUTPUT FORMAT (JSON only, no other text)

{
  "status": "APPROVED" or "REJECTED",
  "weighted_score": <float>,
  "scores": {
    "evidence_grounding": <1-10>,
    "constraint_compliance": <1-10>,
    "specificity_actionability": <1-10>,
    "strategic_insight": <1-10>,
    "completeness_balance": <1-10>,
    "clarity_structure": <1-10>
  },
  "hard_floor_violations": ["list of violated floors or empty array"],
  "hallucinations_detected": ["list of fabricated metrics or empty array"],
  "key_deficiencies": ["prioritized list, max 5"],
  "strengths_to_preserve": ["elements done well"],
  "actionable_feedback": ["specific rewrite instructions, max 5"]
}
"""

# Weights for each criterion
CRITERION_WEIGHTS = {
    "evidence_grounding": 0.25,
    "constraint_compliance": 0.20,
    "specificity_actionability": 0.20,
    "strategic_insight": 0.15,
    "completeness_balance": 0.10,
    "clarity_structure": 0.10,
}

# Hard floor requirements
HARD_FLOORS = {
    "evidence_grounding": 6,
    "constraint_compliance": 6,
}

# Minimum score for any criterion
MIN_INDIVIDUAL_SCORE = 5


def calculate_weighted_score(scores: dict) -> float:
    """Calculate weighted average from individual criterion scores."""
    total = 0.0
    for criterion, weight in CRITERION_WEIGHTS.items():
        score = scores.get(criterion, 5)  # Default to 5 if missing
        total += score * weight
    return round(total, 2)


def check_pass_conditions(scores: dict, weighted_score: float) -> tuple:
    """
    Check if all pass conditions are met.
    Returns (passed: bool, violations: list)
    """
    violations = []

    # Check weighted average threshold
    if weighted_score < 6.0:
        violations.append(f"Weighted score {weighted_score:.1f} < 6.0 threshold")

    # Check hard floors
    for criterion, floor in HARD_FLOORS.items():
        score = scores.get(criterion, 0)
        if score < floor:
            violations.append(f"{criterion}: {score} < {floor} (hard floor)")

    # Check minimum individual scores
    for criterion, score in scores.items():
        if score < MIN_INDIVIDUAL_SCORE:
            violations.append(f"{criterion}: {score} < {MIN_INDIVIDUAL_SCORE} (minimum)")

    return (len(violations) == 0, violations)


def run_llm_evaluation(report: str, source_data: str, iteration: int, llm) -> dict:
    """
    Run LLM-based evaluation with weighted rubric.

    Args:
        report: The SWOT output to evaluate
        source_data: The source data the SWOT should be based on
        iteration: Current revision number (1, 2, or 3)
        llm: LLM client instance

    Returns:
        Evaluation result dict with scores, status, and feedback
    """
    # Truncate source data if too long (Groq has ~8K token limit)
    max_source_len = 4000
    if len(source_data) > max_source_len:
        source_data = source_data[:max_source_len] + "\n... [truncated]"

    prompt = f"""{CRITIC_SYSTEM_PROMPT}

## INPUTS

**Iteration:** {iteration} of 3

**Source Data (the SWOT should be based ONLY on this):**
{source_data}

**SWOT Output to Evaluate:**
{report}

Evaluate strictly and respond with JSON only."""

    response, provider, error, providers_failed = llm.query(prompt, temperature=0)

    if error:
        # Return default middle scores on error
        return {
            "status": "REJECTED",
            "weighted_score": 5.0,
            "scores": {k: 5 for k in CRITERION_WEIGHTS.keys()},
            "hard_floor_violations": [],
            "hallucinations_detected": [],
            "key_deficiencies": [f"LLM evaluation failed: {error}"],
            "strengths_to_preserve": [],
            "actionable_feedback": ["Unable to evaluate - please retry"],
            "provider": provider,
            "providers_failed": providers_failed,
            "error": True
        }

    try:
        # Parse JSON from response
        content = response.strip()
        if "{" in content:
            json_start = content.index("{")
            json_end = content.rindex("}") + 1
            content = content[json_start:json_end]

        parsed = json.loads(content)

        # Extract and validate scores
        scores = parsed.get("scores", {})
        for criterion in CRITERION_WEIGHTS.keys():
            if criterion not in scores:
                scores[criterion] = 5  # Default
            else:
                scores[criterion] = min(max(int(scores[criterion]), 1), 10)  # Clamp 1-10

        # Calculate weighted score
        weighted_score = calculate_weighted_score(scores)

        # Check pass conditions
        passed, violations = check_pass_conditions(scores, weighted_score)

        # Determine status
        status = "APPROVED" if passed else "REJECTED"

        # Override status if LLM said APPROVED but conditions not met
        if parsed.get("status") == "APPROVED" and not passed:
            status = "REJECTED"

        return {
            "status": status,
            "weighted_score": weighted_score,
            "scores": scores,
            "hard_floor_violations": parsed.get("hard_floor_violations", violations),
            "hallucinations_detected": parsed.get("hallucinations_detected", []),
            "key_deficiencies": parsed.get("key_deficiencies", [])[:5],
            "strengths_to_preserve": parsed.get("strengths_to_preserve", []),
            "actionable_feedback": parsed.get("actionable_feedback", [])[:5],
            "provider": provider,
            "providers_failed": providers_failed,
            "error": False
        }

    except (json.JSONDecodeError, ValueError) as e:
        return {
            "status": "REJECTED",
            "weighted_score": 5.0,
            "scores": {k: 5 for k in CRITERION_WEIGHTS.keys()},
            "hard_floor_violations": [],
            "hallucinations_detected": [],
            "key_deficiencies": [f"JSON parsing failed: {str(e)[:100]}"],
            "strengths_to_preserve": [],
            "actionable_feedback": ["Evaluation response was malformed - please retry"],
            "provider": provider,
            "providers_failed": providers_failed,
            "error": True
        }


@traceable(name="Critic")
def critic_node(state, workflow_id=None, progress_store=None):
    """
    Critic node with LLM-only weighted rubric evaluation.

    Evaluates SWOT output on 6 criteria with weighted scoring:
    - Evidence Grounding (25%) - hard floor >= 6
    - Constraint Compliance (20%) - hard floor >= 6
    - Specificity & Actionability (20%)
    - Strategic Insight (15%)
    - Completeness & Balance (10%)
    - Clarity & Structure (10%)

    Pass requires: weighted avg >= 6.0, hard floors met, no score < 5
    """
    # Extract workflow_id and progress_store from state
    if workflow_id is None:
        workflow_id = state.get("workflow_id")
    if progress_store is None:
        progress_store = state.get("progress_store")

    # Skip evaluation if workflow has an error (abort mode)
    if state.get("error"):
        _add_activity_log(workflow_id, progress_store, "critic", "Skipping evaluation - workflow aborted")
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
    revision_count = state.get("revision_count", 0)
    iteration = revision_count + 1  # 1-indexed for display

    # Log evaluation start
    _add_activity_log(workflow_id, progress_store, "critic", f"Evaluating SWOT quality (iteration {iteration}/3)...")

    # Get source data for grounding verification
    source_data = state.get("raw_data", "")

    # Run LLM evaluation
    print(f"Running LLM evaluation (iteration {iteration})...")
    llm = get_llm_client()

    # Add delay before LLM call to avoid rate limits (Analyzer just called LLM)
    print("Waiting 10s before Critic LLM call (rate limit buffer)...")
    time.sleep(10)

    _add_activity_log(workflow_id, progress_store, "critic", "Calling LLM for quality evaluation...")
    start_time = time.time()

    result = run_llm_evaluation(report, source_data, iteration, llm)
    elapsed = time.time() - start_time
    provider = result.get('provider', 'unknown')

    # Propagate LLM error to state to trigger graceful exit (prevents infinite retry loop)
    if result.get("error"):
        _add_activity_log(workflow_id, progress_store, "critic",
                          "LLM evaluation failed - exiting gracefully with current draft")
        state["analyzer_revision_skipped"] = True  # Triggers graceful exit in should_continue()

    # Log failed providers
    providers_failed = result.get('providers_failed', [])
    for pf in providers_failed:
        _add_activity_log(workflow_id, progress_store, "critic", f"LLM {pf['name']} failed: {pf['error']}")

    # Track failed providers in state for frontend
    if "llm_providers_failed" not in state:
        state["llm_providers_failed"] = []
    state["llm_providers_failed"].extend([pf["name"] for pf in providers_failed])

    # Extract results
    status = result["status"]
    weighted_score = result["weighted_score"]
    scores = result["scores"]

    # ============================================================
    # LAYER 4: Deterministic Numeric Validation
    # ============================================================
    metric_ref = state.get("metric_reference", {})
    ref_hash = state.get("metric_reference_hash", "")

    if metric_ref and ref_hash:
        # Verify integrity before using
        if _verify_reference_integrity(metric_ref, ref_hash):
            mismatches = validate_numeric_accuracy(report, metric_ref)
            if mismatches:
                _add_activity_log(workflow_id, progress_store, "critic",
                                  f"Numeric validation: {len(mismatches)} mismatch(es) detected")

                # Ensure hallucinations_detected exists
                if "hallucinations_detected" not in result:
                    result["hallucinations_detected"] = []
                result["hallucinations_detected"].extend(mismatches)

                # Cap evidence_grounding score
                if scores.get("evidence_grounding", 0) > 4:
                    scores["evidence_grounding"] = 4
                    if "hard_floor_violations" not in result:
                        result["hard_floor_violations"] = []
                    result["hard_floor_violations"].append(
                        "Numeric mismatch detected - evidence_grounding capped at 4"
                    )

                # Add specific feedback
                if "actionable_feedback" not in result:
                    result["actionable_feedback"] = []
                result["actionable_feedback"].insert(0,
                    f"Fix {len(mismatches)} numeric mismatch(es) - use exact values with [M##] citations from reference table"
                )

                # Recalculate weighted score with capped evidence_grounding
                weighted_score = calculate_weighted_score(scores)
                result["weighted_score"] = weighted_score

                # Force rejection if numeric mismatches
                status = "REJECTED"
                result["status"] = status
            else:
                _add_activity_log(workflow_id, progress_store, "critic",
                                  "Numeric validation: all citations verified")

            # ============================================================
            # LAYER 3: Uncited Number Detection
            # ============================================================
            # Only validate SWOT section (not Data Report tables which have raw metrics)
            swot_section = report
            if "## SWOT Analysis" in report:
                swot_section = report[report.index("## SWOT Analysis"):]
            uncited_warnings = validate_uncited_numbers(swot_section, metric_ref)
            if uncited_warnings:
                _add_activity_log(workflow_id, progress_store, "critic",
                                  f"Uncited numbers: {len(uncited_warnings)} suspicious value(s) found")

                # Add to hallucinations_detected
                if "hallucinations_detected" not in result:
                    result["hallucinations_detected"] = []
                result["hallucinations_detected"].extend(uncited_warnings)

                # Cap score and add feedback (less severe than mismatches)
                if scores.get("evidence_grounding", 0) > 6:
                    scores["evidence_grounding"] = 6
                    if "hard_floor_violations" not in result:
                        result["hard_floor_violations"] = []
                    result["hard_floor_violations"].append(
                        "Uncited metric-like numbers found - evidence_grounding capped at 6"
                    )

                # Add feedback
                if "actionable_feedback" not in result:
                    result["actionable_feedback"] = []
                result["actionable_feedback"].append(
                    f"Add [M##] citations for {len(uncited_warnings)} uncited metric value(s)"
                )

                # Recalculate and reject
                weighted_score = calculate_weighted_score(scores)
                result["weighted_score"] = weighted_score
                status = "REJECTED"
                result["status"] = status

            # ============================================================
            # LAYER 2: Minimum Citation Count Enforcement
            # ============================================================
            citation_check = validate_minimum_citations(report, metric_ref, min_ratio=0.3)
            if not citation_check["valid"]:
                _add_activity_log(workflow_id, progress_store, "critic",
                                  f"Citation coverage insufficient: {citation_check['message']}")

                # Cap score severely - this indicates LLM ignored citation instructions
                if scores.get("evidence_grounding", 0) > 3:
                    scores["evidence_grounding"] = 3
                    if "hard_floor_violations" not in result:
                        result["hard_floor_violations"] = []
                    result["hard_floor_violations"].append(
                        f"Insufficient citation coverage ({citation_check['ratio']:.0%}) - evidence_grounding capped at 3"
                    )

                # Add feedback
                if "actionable_feedback" not in result:
                    result["actionable_feedback"] = []
                result["actionable_feedback"].insert(0,
                    f"CRITICAL: Add more [M##] citations. Current: {citation_check['citations_found']}/{citation_check['metrics_available']} ({citation_check['ratio']:.0%})"
                )

                # Recalculate and reject
                weighted_score = calculate_weighted_score(scores)
                result["weighted_score"] = weighted_score
                status = "REJECTED"
                result["status"] = status
            else:
                _add_activity_log(workflow_id, progress_store, "critic",
                                  f"Citation coverage OK: {citation_check['message']}")

        else:
            _add_activity_log(workflow_id, progress_store, "critic",
                              "Warning: metric reference integrity check failed - skipping numeric validation")

    # Handle ESCALATE if max iterations reached
    if iteration > 3 and status == "REJECTED":
        status = "ESCALATE"
        _add_activity_log(workflow_id, progress_store, "critic", "Max iterations reached - escalating for human review")

    # Log scores
    print(f"  Status: {status}")
    print(f"  Weighted Score: {weighted_score:.1f}/10")
    for criterion, score in scores.items():
        floor = HARD_FLOORS.get(criterion, "-")
        print(f"    {criterion}: {score}/10 (floor: {floor})")

    _add_activity_log(workflow_id, progress_store, "critic", f"Evaluation via {provider} ({elapsed:.1f}s)")

    # Log status and score
    if status == "APPROVED":
        score_msg = f"Score: {weighted_score:.1f}/10"
    elif status == "ESCALATE":
        score_msg = f"Score: {weighted_score:.1f}/10"
    else:
        score_msg = f"Score: {weighted_score:.1f}/10"
    _add_activity_log(workflow_id, progress_store, "critic", score_msg)

    # Build critique message
    critique_lines = [
        f"Status: {status}",
        f"Weighted Score: {weighted_score:.1f}/10",
        "",
        "Criterion Scores:",
    ]

    for criterion, score in scores.items():
        weight = int(CRITERION_WEIGHTS[criterion] * 100)
        floor = HARD_FLOORS.get(criterion)
        floor_str = f" (floor: {floor})" if floor else ""
        passed = "PASS" if score >= (floor or MIN_INDIVIDUAL_SCORE) else "FAIL"
        critique_lines.append(f"  {criterion}: {score}/10 [{weight}%] {floor_str} - {passed}")

    if result.get("hard_floor_violations"):
        critique_lines.append("")
        critique_lines.append("Hard Floor Violations:")
        for v in result["hard_floor_violations"]:
            critique_lines.append(f"  - {v}")

    if result.get("hallucinations_detected"):
        critique_lines.append("")
        critique_lines.append("Hallucinations Detected:")
        for h in result["hallucinations_detected"]:
            critique_lines.append(f"  - {h}")

    if result.get("key_deficiencies"):
        critique_lines.append("")
        critique_lines.append("Key Deficiencies:")
        for i, d in enumerate(result["key_deficiencies"], 1):
            critique_lines.append(f"  {i}. {d}")

    if result.get("actionable_feedback"):
        critique_lines.append("")
        critique_lines.append("Actionable Feedback:")
        for i, f in enumerate(result["actionable_feedback"], 1):
            critique_lines.append(f"  {i}. {f}")

    if result.get("strengths_to_preserve"):
        critique_lines.append("")
        critique_lines.append("Strengths to Preserve:")
        for s in result["strengths_to_preserve"]:
            critique_lines.append(f"  - {s}")

    state["critique"] = "\n".join(critique_lines)
    state["score"] = weighted_score
    state["critique_details"] = {
        "status": status,
        "weighted_score": weighted_score,
        "scores": scores,
        "hard_floor_violations": result.get("hard_floor_violations", []),
        "hallucinations_detected": result.get("hallucinations_detected", []),
        "key_deficiencies": result.get("key_deficiencies", []),
        "strengths_to_preserve": result.get("strengths_to_preserve", []),
        "actionable_feedback": result.get("actionable_feedback", []),
    }

    # Debug: Log what's being set in critique_details
    print(f"[DEBUG] Critic: Setting critique_details status={status}, score={weighted_score:.1f}")

    # Update progress
    if workflow_id and progress_store:
        progress_store[workflow_id].update({
            "current_step": "critic",
            "revision_count": revision_count,
            "score": weighted_score
        })

    return state
