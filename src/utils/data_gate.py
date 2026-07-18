"""
Deterministic data gate for the Researcher -> Analyzer edge.

Two checks, run on the same extracted-metrics view the Analyzer consumes:

- DG (data gap): required metrics per category. Gaps are surfaced to the
  Analyzer as explicit DATA NOT PROVIDED entries instead of silent omission,
  giving the Critic's constraint-compliance rule something to enforce.
- SC (signal corruption): impossible magnitudes (unit/decimal slips upstream)
  are quarantined before they can enter the reference table and be cited.

Bounds are deliberately loose - they reject the impossible, not the unusual.
"""

# Per-category requirement rules: (metric keys, minimum count present)
REQUIRED_METRICS = {
    "fundamentals": (["revenue", "net_margin", "eps"], 2),
    "valuation": (["pe_trailing", "pe_forward", "pb_ratio", "ps_ratio"], 1),
    "volatility": (["beta", "vix", "historical_volatility"], 1),
    "macro": (["gdp_growth", "interest_rate", "inflation", "unemployment"], 2),
}

# (min, max) inclusive. Values are in the units the extractor produces
# (margins/rates/vol in percent, ratios as multiples, currency in dollars).
SANITY_BOUNDS = {
    "revenue": (0, 1e13),
    "net_income": (-1e12, 1e12),
    "free_cash_flow": (-1e12, 1e12),
    "net_margin": (-200, 100),
    "gross_margin": (-200, 100),
    "operating_margin": (-200, 100),
    "eps": (-10000, 10000),
    "debt_to_equity": (-100, 100),
    "revenue_cagr_3yr": (-100, 300),
    "pe_trailing": (-1000, 1000),
    "pe_forward": (-1000, 1000),
    "pb_ratio": (-100, 500),
    "ps_ratio": (0, 500),
    "ev_ebitda": (-1000, 1000),
    "beta": (-5, 10),
    "vix": (5, 150),
    "historical_volatility": (0, 500),
    "gdp_growth": (-30, 30),
    "interest_rate": (-5, 50),
    "inflation": (-20, 100),
    "unemployment": (0, 50),
}


def _numeric_value(metric_val):
    """Extracted metrics are either numbers or {'value': number, ...} dicts."""
    if isinstance(metric_val, dict):
        metric_val = metric_val.get("value")
    if isinstance(metric_val, (int, float)) and not isinstance(metric_val, bool):
        return float(metric_val)
    return None


def audit_extracted_metrics(extracted: dict) -> dict:
    """
    Audit the extracted metrics view.

    Args:
        extracted: dict from analyzer._extract_key_metrics -
                   {"fundamentals": {...}, "valuation": {...}, ...}

    Returns:
        {
          "gaps": ["fundamentals: revenue", ...]        # DG findings
          "suspect": [("volatility", "vix", 1673.0), ...]  # SC findings
        }
    """
    gaps = []
    suspect = []

    for category, (keys, min_present) in REQUIRED_METRICS.items():
        data = extracted.get(category) or {}
        present = [k for k in keys if _numeric_value(data.get(k)) is not None]
        if len(present) < min_present:
            for k in keys:
                if k not in present:
                    gaps.append(f"{category}: {k}")

    for category in REQUIRED_METRICS:
        data = extracted.get(category) or {}
        if not isinstance(data, dict):
            continue
        for key, raw in data.items():
            value = _numeric_value(raw)
            bounds = SANITY_BOUNDS.get(key)
            if value is None or bounds is None:
                continue
            lo, hi = bounds
            if not (lo <= value <= hi):
                suspect.append((category, key, value))

    # Cross-consistency: net_margin must agree with its components. A
    # violation means mixed reporting periods upstream (annual revenue paired
    # with a quarterly net income); quarantine all three so a wrong margin
    # can never be cited as fact.
    fundamentals = extracted.get("fundamentals") or {}
    revenue = _numeric_value(fundamentals.get("revenue"))
    net_income = _numeric_value(fundamentals.get("net_income"))
    net_margin = _numeric_value(fundamentals.get("net_margin"))
    if revenue and net_income is not None and net_margin is not None and revenue > 0:
        derived = net_income / revenue * 100
        if abs(derived - net_margin) > max(1.0, abs(net_margin) * 0.2):
            for key, value in (("net_income", net_income), ("net_margin", net_margin)):
                if ("fundamentals", key, value) not in suspect:
                    suspect.append(("fundamentals", key, value))
            gaps.append("fundamentals: net_margin (inconsistent with components - period mixing suspected)")

    return {"gaps": gaps, "suspect": suspect}


def scrub_suspect_metrics(extracted: dict, suspect: list) -> dict:
    """Remove quarantined values so they cannot enter the reference table."""
    for category, key, _value in suspect:
        if isinstance(extracted.get(category), dict):
            extracted[category].pop(key, None)
    return extracted
