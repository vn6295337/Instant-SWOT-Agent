from src.llm_client import get_llm_client
from langsmith import traceable
import time
import json

# VADER Sentiment Analysis
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_vader_analyzer = None


def _get_vader():
    """Lazy-load VADER analyzer (singleton)."""
    global _vader_analyzer
    if _vader_analyzer is None:
        _vader_analyzer = SentimentIntensityAnalyzer()
    return _vader_analyzer


def _compute_vader_sentiment(texts: list) -> dict:
    """
    Compute VADER sentiment scores for a list of texts.

    Args:
        texts: List of strings (headlines, titles, etc.)

    Returns:
        {
            "avg_compound": 0.42,
            "min_compound": -0.31,
            "max_compound": 0.78,
            "positive_count": 3,
            "negative_count": 1,
            "neutral_count": 1,
            "total_count": 5
        }
        or None if no texts provided
    """
    if not texts:
        return None

    vader = _get_vader()
    scores = []
    for text in texts:
        if text and isinstance(text, str):
            score = vader.polarity_scores(text)["compound"]
            scores.append(score)

    if not scores:
        return None

    return {
        "avg_compound": round(sum(scores) / len(scores), 3),
        "min_compound": round(min(scores), 3),
        "max_compound": round(max(scores), 3),
        "positive_count": sum(1 for s in scores if s > 0.05),
        "negative_count": sum(1 for s in scores if s < -0.05),
        "neutral_count": sum(1 for s in scores if -0.05 <= s <= 0.05),
        "total_count": len(scores)
    }


# Financial institution detection for EV/EBITDA exclusion
FINANCIAL_SECTORS = {
    "financial services", "financial", "banking", "banks",
    "insurance", "real estate investment trust", "reit",
    "investment management", "capital markets", "diversified financial services",
    "consumer finance", "asset management", "mortgage finance",
}

FINANCIAL_INDUSTRIES = {
    "banks", "regional banks", "diversified banks", "money center banks",
    "insurance", "life insurance", "property insurance", "reinsurance",
    "real estate", "reit", "mortgage reits", "equity reits",
    "asset management", "investment banking", "capital markets",
    "consumer finance", "specialty finance",
}

# Fallback: known financial tickers when sector data unavailable
FINANCIAL_TICKERS = {
    "JPM", "BAC", "WFC", "GS", "MS", "C", "USB", "PNC", "TFC", "COF",
    "AXP", "BLK", "SCHW", "CME", "ICE", "SPGI", "MCO",
    "BRK.A", "BRK.B", "MET", "PRU", "AIG", "ALL", "TRV", "PGR", "CB",
    "AMT", "PLD", "CCI", "EQIX", "PSA", "O", "WELL", "AVB", "EQR",
}

# =============================================================================
# REVISION MODE: Conditional Focus Area Blocks
# These are included in revision prompts based on which rubric criteria failed
# =============================================================================

EVIDENCE_GROUNDING_BLOCK = """
**EVIDENCE GROUNDING (Critical)**
- Every claim must cite a specific metric from the input data
- Use exact field names: `revenue`, `net_margin_pct`, `trailing_pe`, etc.
- Format citations as: "[Metric]: [Value] ([Source], [Period])"
- If a metric was flagged as fabricated, remove it entirely or replace with actual data
"""

CONSTRAINT_COMPLIANCE_BLOCK = """
**CONSTRAINT COMPLIANCE (Critical)**
- Remove any language that sounds like investment advice
- Check all temporal labels — TTM vs FY vs Q must match the source
- Add confidence levels to key conclusions: (High/Medium/Low)
- Do not use EV/EBITDA for financial institutions
- For missing data, state "DATA NOT PROVIDED" — do not estimate
"""

SPECIFICITY_BLOCK = """
**SPECIFICITY & ACTIONABILITY**
- Replace generic statements with company-specific observations
- Quantify every claim possible: not "strong margins" but "31.0% operating margin"
- Remove business clichés: "leveraging," "best-in-class," "synergies"
"""

INSIGHT_BLOCK = """
**STRATEGIC INSIGHT**
- Connect observations across data baskets (e.g., link margin trends to macro rates)
- Go beyond restating metrics — explain WHY they matter
- Identify non-obvious relationships in the data
"""

COMPLETENESS_BLOCK = """
**COMPLETENESS & BALANCE**
- Ensure ALL required sections are present (Strengths, Weaknesses, Opportunities, Threats, Data Quality Notes)
- Balance quadrants — no section should be filler or disproportionately thin
"""

CLARITY_BLOCK = """
**CLARITY & STRUCTURE**
- Use consistent formatting throughout
- Ensure no contradictions across sections
- Make output scannable — executives should grasp key points in 30 seconds
"""


def _is_financial_institution(sector: str, industry: str, ticker: str) -> bool:
    """Detect if company is a financial institution (EV/EBITDA not meaningful)."""
    sector_lower = (sector or "").lower().strip()
    industry_lower = (industry or "").lower().strip()

    if any(fs in sector_lower for fs in FINANCIAL_SECTORS):
        return True
    if any(fi in industry_lower for fi in FINANCIAL_INDUSTRIES):
        return True
    if ticker and ticker.upper() in FINANCIAL_TICKERS:
        return True
    return False


def _extract_company_profile(raw_data: str) -> dict:
    """Extract sector/industry from Yahoo Finance data if available."""
    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError:
        return {}

    multi_source = data.get("multi_source", {})

    # Try valuation Yahoo Finance data first
    yf_val = multi_source.get("valuation_all", {}).get("yahoo_finance", {}).get("data", {})
    profile = yf_val.get("profile", {})

    if profile.get("sector"):
        return {"sector": profile.get("sector"), "industry": profile.get("industry")}

    # Fallback to fundamentals Yahoo Finance
    yf_fund = multi_source.get("fundamentals_all", {}).get("yahoo_finance", {}).get("data", {})
    fund_profile = yf_fund.get("profile", {})

    return {
        "sector": fund_profile.get("sector", ""),
        "industry": fund_profile.get("industry", "")
    }


def _add_activity_log(workflow_id, progress_store, step, message):
    """Helper to add activity log entry."""
    if workflow_id and progress_store:
        from src.services.workflow_store import add_activity_log
        add_activity_log(workflow_id, step, message)


def _extract_temporal_metric(metric_data: dict) -> dict:
    """Extract metric value with temporal metadata (fiscal year, period end, form type)."""
    if not isinstance(metric_data, dict):
        return {"value": metric_data}
    return {
        "value": metric_data.get("value"),
        "end_date": metric_data.get("end_date"),
        "fiscal_year": metric_data.get("fiscal_year"),
        "form": metric_data.get("form"),  # "10-K" (annual) or "10-Q" (quarterly)
    }


def _get_fiscal_period_label(metric: dict) -> str:
    """Format fiscal period label from temporal data (e.g., 'FY 2023' or 'Q3 2024')."""
    if not isinstance(metric, dict):
        return ""
    form = metric.get("form", "")
    fy = metric.get("fiscal_year")
    end_date = metric.get("end_date")

    if not fy:
        return ""

    if form == "10-K":
        return f"FY {fy}"
    elif form == "10-Q" and end_date:
        try:
            # Parse quarter from end date
            month = int(end_date.split("-")[1])
            quarter = (month - 1) // 3 + 1
            return f"Q{quarter} {fy}"
        except (ValueError, IndexError):
            return f"FY {fy}"
    return f"FY {fy}"


def _format_currency(value):
    """Format large numbers as currency (B/M)."""
    if value is None:
        return "N/A"
    if isinstance(value, dict):
        value = value.get("value")
    if value is None:
        return "N/A"
    if isinstance(value, (int, float)):
        if abs(value) >= 1e12:
            return f"${value/1e12:.2f}T"
        if abs(value) >= 1e9:
            return f"${value/1e9:.2f}B"
        if abs(value) >= 1e6:
            return f"${value/1e6:.0f}M"
        return f"${value:,.0f}"
    return str(value)


def _format_number(value, suffix="", decimals=2):
    """Format a number with optional suffix."""
    if value is None:
        return "N/A"
    if isinstance(value, dict):
        value = value.get("value")
    if value is None:
        return "N/A"
    if isinstance(value, (int, float)):
        return f"{value:.{decimals}f}{suffix}"
    return str(value)


def _get_period_label(metric_data: dict) -> str:
    """Get period label from metric data (e.g., 'FY 2024', 'Q3 2024', '2024-11')."""
    if not isinstance(metric_data, dict):
        return ""

    # Check for fiscal year/form info
    fy = metric_data.get("fiscal_year")
    form = metric_data.get("form", "")
    end_date = metric_data.get("end_date", "")
    date = metric_data.get("date", "")

    if fy:
        if form == "10-K":
            return f"FY {fy}"
        elif form == "10-Q" and end_date:
            try:
                month = int(end_date.split("-")[1])
                quarter = (month - 1) // 3 + 1
                return f"Q{quarter} {fy}"
            except:
                return f"FY {fy}"
        return f"FY {fy}"

    # Fallback to date
    if end_date:
        return end_date[:10]
    if date:
        return str(date)[:10]
    return ""


def _get_value(metric_data) -> any:
    """Extract value from metric data (handles both dict and plain values)."""
    if isinstance(metric_data, dict):
        return metric_data.get("value")
    return metric_data


def _generate_data_report(raw_data: str, is_financial: bool = False) -> str:
    """Generate complete multi-source data report with simple tables.

    Args:
        raw_data: JSON string of research data
        is_financial: If True, exclude EV/EBITDA for financial institutions
    """
    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError:
        return "Error: Could not parse data"

    lines = []
    company = data.get("company_name", "Unknown")
    ticker = data.get("ticker", "N/A")
    multi_source = data.get("multi_source", {})
    metrics = data.get("metrics", {})

    lines.append(f"# Data Report: {company} ({ticker})")
    lines.append("")

    # ========== FINANCIALS ==========
    fin_all = multi_source.get("fundamentals_all", {})
    sec_data = fin_all.get("sec_edgar", {}).get("data", {})
    yf_data = fin_all.get("yahoo_finance", {}).get("data", {})

    if sec_data or yf_data:
        lines.append("## Financials")
        lines.append("Primary: SEC EDGAR | Secondary: Yahoo Finance")
        lines.append("")
        lines.append("| Metric | Period | SEC EDGAR | Yahoo Finance |")
        lines.append("|--------|--------|-----------|---------------|")

        fin_metrics = [
            ("Revenue", "revenue", _format_currency),
            ("Net Income", "net_income", _format_currency),
            ("Gross Profit", "gross_profit", _format_currency),
            ("Operating Income", "operating_income", _format_currency),
            ("Gross Margin %", "gross_margin_pct", lambda v: _format_number(v, "%")),
            ("Operating Margin %", "operating_margin_pct", lambda v: _format_number(v, "%")),
            ("Net Margin %", "net_margin_pct", lambda v: _format_number(v, "%")),
            ("Free Cash Flow", "free_cash_flow", _format_currency),
            ("Operating Cash Flow", "operating_cash_flow", _format_currency),
            ("Total Assets", "total_assets", _format_currency),
            ("Total Liabilities", "total_liabilities", _format_currency),
            ("Stockholders Equity", "stockholders_equity", _format_currency),
            ("Cash", "cash", _format_currency),
            ("Long-term Debt", "long_term_debt", _format_currency),
            ("Net Debt", "net_debt", _format_currency),
            ("R&D Expense", "rd_expense", _format_currency),
        ]

        for name, key, fmt in fin_metrics:
            sec_val = sec_data.get(key)
            yf_val = yf_data.get(key)
            period = _get_period_label(sec_val) or _get_period_label(yf_val)
            sec_str = fmt(_get_value(sec_val)) if sec_val else "N/A"
            yf_str = fmt(_get_value(yf_val)) if yf_val else "N/A"
            if sec_str != "N/A" or yf_str != "N/A":
                lines.append(f"| {name} | {period} | {sec_str} | {yf_str} |")

        lines.append("")

    # ========== VALUATION ==========
    val_all = multi_source.get("valuation_all", {})
    yf_val = val_all.get("yahoo_finance", {}).get("data", {})
    av_val = val_all.get("alpha_vantage", {}).get("data", {})

    if yf_val or av_val:
        lines.append("## Valuation")
        lines.append("Primary: Yahoo Finance | Secondary: Alpha Vantage")
        lines.append("")
        lines.append("| Metric | Yahoo Finance | Alpha Vantage |")
        lines.append("|--------|---------------|---------------|")

        val_metrics = [
            ("Market Cap", "market_cap", _format_currency),
            ("Enterprise Value", "enterprise_value", _format_currency),
            ("P/E Trailing", "trailing_pe", lambda v: _format_number(v, "x")),
            ("P/E Forward", "forward_pe", lambda v: _format_number(v, "x")),
            ("P/B Ratio", "pb_ratio", lambda v: _format_number(v, "x")),
            ("P/S Ratio", "ps_ratio", lambda v: _format_number(v, "x")),
            ("PEG Ratio", "trailing_peg", lambda v: _format_number(v, "x")),
            ("Price/FCF", "price_to_fcf", lambda v: _format_number(v, "x")),
            ("Revenue Growth", "revenue_growth", lambda v: _format_number(v * 100 if v and abs(v) < 10 else v, "%") if v else "N/A"),
            ("Earnings Growth", "earnings_growth", lambda v: _format_number(v * 100 if v and abs(v) < 10 else v, "%") if v else "N/A"),
        ]

        # Only include EV/EBITDA for non-financial companies
        if not is_financial:
            val_metrics.insert(6, ("EV/EBITDA", "ev_ebitda", lambda v: _format_number(v, "x")))
            val_metrics.insert(7, ("EV/Revenue", "ev_revenue", lambda v: _format_number(v, "x")))

        for name, key, fmt in val_metrics:
            y = yf_val.get(key)
            a = av_val.get(key)
            ys = fmt(_get_value(y)) if y is not None else "N/A"
            avs = fmt(_get_value(a)) if a is not None else "N/A"
            if ys != "N/A" or avs != "N/A":
                lines.append(f"| {name} | {ys} | {avs} |")

        lines.append("")

    # ========== VOLATILITY ==========
    vol_all = multi_source.get("volatility_all", {})
    if vol_all:
        lines.append("## Volatility")
        lines.append("Primary: FRED + Yahoo | Secondary: Alpha Vantage")
        lines.append("")
        lines.append("| Metric | Date | Primary | Secondary |")
        lines.append("|--------|------|---------|-----------|")

        ctx = vol_all.get("market_volatility_context", {})
        vix = ctx.get("vix", {})
        vxn = ctx.get("vxn", {})
        yf_vol = vol_all.get("yahoo_finance", {}).get("data", {})
        av_vol = vol_all.get("alpha_vantage", {}).get("data", {})

        # VIX
        if vix.get("value"):
            lines.append(f"| VIX | {vix.get('date', '')} | {_format_number(vix.get('value'))} | - |")

        # VXN
        if vxn.get("value"):
            lines.append(f"| VXN | {vxn.get('date', '')} | {_format_number(vxn.get('value'))} | - |")

        # Beta
        beta_yf = _get_value(yf_vol.get("beta"))
        beta_av = _get_value(av_vol.get("beta")) if av_vol else None
        if beta_yf or beta_av:
            lines.append(f"| Beta | - | {_format_number(beta_yf, '', 3)} | {_format_number(beta_av, '', 3) if beta_av else 'N/A'} |")

        # Historical Volatility
        hv_yf = _get_value(yf_vol.get("historical_volatility"))
        hv_av = _get_value(av_vol.get("historical_volatility")) if av_vol else None
        if hv_yf or hv_av:
            lines.append(f"| Historical Volatility | - | {_format_number(hv_yf, '%')} | {_format_number(hv_av, '%') if hv_av else 'N/A'} |")

        # Implied Volatility
        iv_yf = _get_value(yf_vol.get("implied_volatility"))
        if iv_yf:
            lines.append(f"| Implied Volatility | - | {_format_number(iv_yf, '%')} | N/A |")

        lines.append("")

    # ========== MACRO ==========
    macro_all = multi_source.get("macro_all", {})
    if macro_all:
        lines.append("## Macro Indicators")
        lines.append("Primary: BEA/BLS | Secondary: FRED")
        lines.append("")
        lines.append("| Metric | Period | BEA/BLS | FRED |")
        lines.append("|--------|--------|---------|------|")

        bea_bls = macro_all.get("bea_bls", {}).get("data", {})
        fred = macro_all.get("fred", {}).get("data", {})

        # GDP Growth
        gdp_p = bea_bls.get("gdp_growth", {}) or {}
        gdp_f = fred.get("gdp_growth", {}) or {}
        gdp_date = gdp_p.get("date", "") or gdp_f.get("date", "")
        lines.append(f"| GDP Growth | {gdp_date} | {_format_number(gdp_p.get('value'), '%')} | {_format_number(gdp_f.get('value'), '%')} |")

        # CPI/Inflation
        cpi_p = bea_bls.get("cpi_inflation", {}) or {}
        cpi_f = fred.get("cpi_inflation", {}) or {}
        cpi_date = cpi_p.get("date", "") or cpi_f.get("date", "")
        lines.append(f"| Inflation (CPI YoY) | {cpi_date} | {_format_number(cpi_p.get('value'), '%')} | {_format_number(cpi_f.get('value'), '%')} |")

        # Unemployment
        unemp_p = bea_bls.get("unemployment", {}) or {}
        unemp_f = fred.get("unemployment", {}) or {}
        unemp_date = unemp_p.get("date", "") or unemp_f.get("date", "")
        lines.append(f"| Unemployment | {unemp_date} | {_format_number(unemp_p.get('value'), '%')} | {_format_number(unemp_f.get('value'), '%')} |")

        # Fed Funds Rate (FRED only)
        rates = fred.get("interest_rate", {}) or {}
        lines.append(f"| Fed Funds Rate | {rates.get('date', '')} | - | {_format_number(rates.get('value'), '%')} |")

        lines.append("")

    # ========== NEWS ==========
    news = metrics.get("news", {})
    # Tavily returns results in 'results', other sources use 'articles'
    articles = news.get("results", []) or news.get("articles", []) if news else []

    if articles:
        lines.append("## News Articles")
        lines.append(f"Source: {news.get('source', 'Tavily')}")
        lines.append("")
        lines.append("| # | Title | Source | URL |")
        lines.append("|---|-------|--------|-----|")

        for i, article in enumerate(articles[:10], 1):
            title = article.get("title", "Untitled")
            source = article.get("source", "Unknown")
            url = article.get("url", article.get("link", ""))
            lines.append(f"| {i} | {title} | {source} | {url} |")

        lines.append("")

    # ========== SENTIMENT ==========
    sentiment = metrics.get("sentiment", {})
    if sentiment:
        composite_score = sentiment.get("composite_score", "N/A")
        interpretation = sentiment.get("overall_interpretation", "")

        # Try both old format (finnhub_sentiment) and new format (metrics.finnhub)
        finnhub = sentiment.get("finnhub_sentiment", {}) or sentiment.get("metrics", {}).get("finnhub", {})
        reddit = sentiment.get("reddit_sentiment", {}) or sentiment.get("metrics", {}).get("reddit", {})

        finn_articles = finnhub.get("articles", [])
        finn_score = finnhub.get("score", finnhub.get("composite_score", "N/A"))
        finn_count = finnhub.get("articles_analyzed", len(finn_articles))

        reddit_posts = reddit.get("posts", [])
        reddit_score = reddit.get("score", reddit.get("composite_score", "N/A"))
        reddit_count = reddit.get("posts_analyzed", len(reddit_posts))

        lines.append("## Sentiment Analysis")
        lines.append(f"Composite Score: {composite_score}/100 - {interpretation}")
        lines.append("")
        lines.append("| Source | Score | Items Analyzed |")
        lines.append("|--------|-------|----------------|")
        lines.append(f"| Finnhub | {finn_score}/100 | {finn_count} articles |")
        lines.append(f"| Reddit | {reddit_score}/100 | {reddit_count} posts |")
        lines.append("")

        # Show individual articles if available
        if finn_articles:
            lines.append("### Finnhub Articles")
            lines.append("")
            lines.append("| # | Headline | Sentiment | URL |")
            lines.append("|---|----------|-----------|-----|")
            for i, article in enumerate(finn_articles[:10], 1):
                headline = article.get("headline", article.get("title", "Untitled"))
                sent = article.get("sentiment_score", article.get("sentiment", "N/A"))
                if isinstance(sent, (int, float)):
                    sent = f"{sent:+.2f}"
                url = article.get("url", article.get("link", ""))
                lines.append(f"| {i} | {headline} | {sent} | {url} |")
            lines.append("")

        # Show Reddit posts if available
        if reddit_posts:
            lines.append("### Reddit Posts")
            lines.append("")
            lines.append("| # | Title | Subreddit | Upvotes | Sentiment | URL |")
            lines.append("|---|-------|-----------|---------|-----------|-----|")
            for i, post in enumerate(reddit_posts[:10], 1):
                title = post.get("title", "Untitled")
                subreddit = post.get("subreddit", "r/unknown")
                upvotes = post.get("upvotes", post.get("score", 0))
                sent = post.get("sentiment_score", post.get("sentiment", "N/A"))
                if isinstance(sent, (int, float)):
                    sent = f"{sent:+.2f}"
                url = post.get("url", post.get("permalink", ""))
                if url and not url.startswith("http"):
                    url = f"https://reddit.com{url}"
                lines.append(f"| {i} | {title} | {subreddit} | {upvotes} | {sent} | {url} |")
            lines.append("")

    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def _extract_key_metrics(raw_data: str) -> dict:
    """Extract and format key metrics from raw JSON data, preserving temporal info."""
    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError:
        return {"error": "Could not parse raw data"}

    metrics = data.get("metrics", {})
    extracted = {
        "company": data.get("company_name", "Unknown"),
        "ticker": data.get("ticker", "N/A"),
        "fundamentals": {},
        "valuation": {},
        "volatility": {},
        "macro": {},
        "news": {},
        "sentiment": {},
        "aggregated_swot": data.get("aggregated_swot", {})
    }

    # Extract fundamentals with temporal data
    fin = metrics.get("fundamentals", {})
    if fin and "error" not in fin:
        fin_data = fin.get("fundamentals", {})
        debt_data = fin.get("debt", {})
        extracted["fundamentals"] = {
            "revenue": _extract_temporal_metric(fin_data.get("revenue", {})),
            "revenue_cagr_3yr": fin_data.get("revenue_growth_3yr"),
            "net_margin": _extract_temporal_metric(fin_data.get("net_margin_pct", {})),
            "gross_margin": _extract_temporal_metric(fin_data.get("gross_margin_pct", {})),
            "operating_margin": _extract_temporal_metric(fin_data.get("operating_margin_pct", {})),
            "eps": _extract_temporal_metric(fin_data.get("eps", {})),
            "debt_to_equity": _extract_temporal_metric(debt_data.get("debt_to_equity", {})),
            "free_cash_flow": _extract_temporal_metric(fin.get("cash_flow", {}).get("free_cash_flow", {})),
            "net_income": _extract_temporal_metric(fin_data.get("net_income", {})),
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

    # Extract news with VADER sentiment
    news = metrics.get("news", {})
    if news and "error" not in news:
        articles = news.get("articles", [])
        headlines = [a.get("title", "") for a in articles if a.get("title")]

        # Compute VADER sentiment on headlines
        vader_news = _compute_vader_sentiment(headlines)

        extracted["news"] = {
            "article_count": len(articles),
            "headlines": [a.get("title", "")[:100] for a in articles[:5]],
            "vader_sentiment": vader_news,
        }

    # Extract sentiment with VADER on reddit posts
    sent = metrics.get("sentiment", {})
    if sent and "error" not in sent:
        # Get reddit posts for VADER analysis
        reddit_posts = sent.get("reddit_posts", [])
        reddit_titles = [p.get("title", "") for p in reddit_posts if p.get("title")]

        # Compute VADER sentiment on reddit titles
        vader_reddit = _compute_vader_sentiment(reddit_titles)

        extracted["sentiment"] = {
            "composite_score": sent.get("composite_score"),
            "overall_category": sent.get("overall_swot_category"),
            "vader_reddit": vader_reddit,
        }

    return extracted


def _format_metrics_for_prompt(extracted: dict, is_financial: bool = False) -> str:
    """Format extracted metrics into a clear text for the LLM.

    Args:
        extracted: Extracted metrics dictionary
        is_financial: If True, exclude EV/EBITDA from valuation metrics
    """
    lines = []
    lines.append(f"Company: {extracted['company']} ({extracted['ticker']})")
    lines.append("")

    # Financials (with temporal context)
    fin = extracted.get("fundamentals", {})
    if fin:
        lines.append("=== FINANCIALS (from SEC EDGAR) ===")
        # Revenue with fiscal period
        revenue = fin.get("revenue", {})
        if isinstance(revenue, dict) and revenue.get("value"):
            period = _get_fiscal_period_label(revenue)
            period_str = f" ({period})" if period else ""
            lines.append(f"- Revenue: ${revenue['value']:,.0f}{period_str}")
        elif isinstance(revenue, (int, float)):
            lines.append(f"- Revenue: ${revenue:,.0f}")

        if fin.get("revenue_cagr_3yr"):
            lines.append(f"- Revenue CAGR (3yr): {fin['revenue_cagr_3yr']:.1f}%")

        # Net margin with fiscal period
        net_margin = fin.get("net_margin", {})
        if isinstance(net_margin, dict) and net_margin.get("value") is not None:
            period = _get_fiscal_period_label(net_margin)
            period_str = f" ({period})" if period else ""
            lines.append(f"- Net Margin: {net_margin['value']:.1f}%{period_str}")
        elif isinstance(net_margin, (int, float)):
            lines.append(f"- Net Margin: {net_margin:.1f}%")

        # EPS with fiscal period
        eps = fin.get("eps", {})
        if isinstance(eps, dict) and eps.get("value"):
            period = _get_fiscal_period_label(eps)
            period_str = f" ({period})" if period else ""
            lines.append(f"- EPS: ${eps['value']:.2f}{period_str}")
        elif isinstance(eps, (int, float)):
            lines.append(f"- EPS: ${eps:.2f}")

        # Debt/Equity with fiscal period
        d_to_e = fin.get("debt_to_equity", {})
        if isinstance(d_to_e, dict) and d_to_e.get("value") is not None:
            period = _get_fiscal_period_label(d_to_e)
            period_str = f" ({period})" if period else ""
            lines.append(f"- Debt/Equity: {d_to_e['value']:.2f}{period_str}")
        elif isinstance(d_to_e, (int, float)):
            lines.append(f"- Debt/Equity: {d_to_e:.2f}")

        # Free Cash Flow with fiscal period
        fcf = fin.get("free_cash_flow", {})
        if isinstance(fcf, dict) and fcf.get("value"):
            period = _get_fiscal_period_label(fcf)
            period_str = f" ({period})" if period else ""
            lines.append(f"- Free Cash Flow: ${fcf['value']:,.0f}{period_str}")
        elif isinstance(fcf, (int, float)):
            lines.append(f"- Free Cash Flow: ${fcf:,.0f}")

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
        if val.get("ev_ebitda") and not is_financial:
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

    # News with VADER sentiment
    news = extracted.get("news", {})
    if news:
        lines.append("=== RECENT NEWS ===")
        lines.append(f"- Articles found: {news.get('article_count', 0)}")
        # VADER sentiment scores for news
        vader_news = news.get("vader_sentiment")
        if vader_news:
            lines.append(f"- VADER Sentiment: {vader_news['avg_compound']:.2f} (range: {vader_news['min_compound']:.2f} to {vader_news['max_compound']:.2f})")
            lines.append(f"  Breakdown: {vader_news['positive_count']} positive, {vader_news['negative_count']} negative, {vader_news['neutral_count']} neutral")
        for headline in news.get("headlines", []):
            lines.append(f"  • {headline}")
        lines.append("")

    # Sentiment with VADER for reddit
    sent = extracted.get("sentiment", {})
    if sent:
        lines.append("=== MARKET SENTIMENT ===")
        if sent.get("composite_score") is not None:
            lines.append(f"- Composite Score: {sent['composite_score']:.2f}")
        if sent.get("overall_category"):
            lines.append(f"- Overall: {sent['overall_category']}")
        # VADER sentiment scores for reddit
        vader_reddit = sent.get("vader_reddit")
        if vader_reddit:
            lines.append(f"- Reddit VADER: {vader_reddit['avg_compound']:.2f} (range: {vader_reddit['min_compound']:.2f} to {vader_reddit['max_compound']:.2f})")
            lines.append(f"  Breakdown: {vader_reddit['positive_count']} positive, {vader_reddit['negative_count']} negative, {vader_reddit['neutral_count']} neutral")
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


# ============================================================
# METRIC REFERENCE TABLE - For Hallucination Prevention (Layer 1)
# ============================================================

import hashlib


def _format_metric_for_reference(key: str, value, temporal_info: dict = None) -> tuple:
    """
    Format a single metric for the reference table with exact as-of date.

    Returns:
        tuple: (formatted_string, as_of_date)
    """
    if value is None:
        return None, None

    # Format value based on metric type
    if key in ("revenue", "net_income", "free_cash_flow", "market_cap", "enterprise_value",
               "total_assets", "total_liabilities", "stockholders_equity", "operating_cash_flow"):
        formatted = f"${value:,.0f}"
    elif key in ("net_margin", "gross_margin", "operating_margin", "gdp_growth",
                 "inflation", "unemployment", "historical_volatility", "revenue_cagr_3yr"):
        formatted = f"{value:.1f}%"
    elif key in ("interest_rate",):
        formatted = f"{value:.2f}%"
    elif key in ("pe_trailing", "pe_forward", "ps_ratio", "ev_ebitda", "vix"):
        formatted = f"{value:.1f}"
    elif key in ("pb_ratio", "debt_to_equity", "beta"):
        formatted = f"{value:.2f}"
    elif key in ("eps",):
        formatted = f"${value:.2f}"
    elif key in ("composite_score",):
        formatted = f"{value:.1f}"
    else:
        # Default formatting for unknown metrics
        if isinstance(value, float):
            formatted = f"{value:.2f}"
        else:
            formatted = str(value)

    # Extract actual date (not fiscal period label)
    as_of_date = None
    if temporal_info and isinstance(temporal_info, dict):
        as_of_date = temporal_info.get("end_date")  # e.g., "2024-09-28"

    if as_of_date:
        formatted = f"{formatted} (as of {as_of_date})"

    return formatted, as_of_date


def _generate_metric_reference_table(extracted: dict, is_financial: bool = False) -> tuple:
    """
    Generate an immutable metric reference table for LLM grounding.

    Args:
        extracted: Extracted metrics dictionary from _extract_key_metrics()
        is_financial: If True, exclude EV/EBITDA

    Returns:
        tuple: (table_string, metric_lookup_dict)
    """
    lines = [
        "=" * 60,
        "METRIC REFERENCE TABLE - COPY VALUES EXACTLY AS SHOWN",
        "=" * 60,
        "",
        "CRITICAL INSTRUCTION:",
        "- Copy metric values EXACTLY as shown (including $, %, decimals)",
        "- Do NOT round, estimate, or approximate numbers",
        "- Do NOT invent metrics not listed below",
        "- Include the 'as of' date when citing temporal metrics",
        "",
    ]

    lookup = {}
    mid = 1

    # Define categories and their metric keys
    categories = [
        ("FUNDAMENTALS", "fundamentals", [
            "revenue", "net_income", "net_margin", "gross_margin", "operating_margin",
            "eps", "debt_to_equity", "free_cash_flow", "revenue_cagr_3yr"
        ]),
        ("VALUATION", "valuation", [
            "pe_trailing", "pe_forward", "pb_ratio", "ps_ratio", "ev_ebitda"
        ]),
        ("VOLATILITY", "volatility", [
            "beta", "vix", "historical_volatility"
        ]),
        ("MACRO", "macro", [
            "gdp_growth", "interest_rate", "inflation", "unemployment"
        ]),
    ]

    for label, cat_key, metric_keys in categories:
        data = extracted.get(cat_key, {})
        if not data:
            continue

        category_lines = []

        for metric_key in metric_keys:
            metric_val = data.get(metric_key)
            if metric_val is None:
                continue

            # Skip EV/EBITDA for financial institutions
            if is_financial and metric_key == "ev_ebitda":
                continue

            # Handle temporal metrics (dict with value and end_date)
            if isinstance(metric_val, dict) and metric_val.get("value") is not None:
                raw_value = metric_val["value"]
                formatted, as_of_date = _format_metric_for_reference(
                    metric_key, raw_value, metric_val
                )
            elif isinstance(metric_val, (int, float)):
                raw_value = metric_val
                formatted, as_of_date = _format_metric_for_reference(metric_key, raw_value)
            else:
                continue  # Skip non-numeric

            if formatted:
                ref_id = f"M{mid:02d}"
                category_lines.append(f"  {ref_id}: {metric_key} = {formatted}")
                lookup[ref_id] = {
                    "key": metric_key,
                    "raw_value": raw_value,
                    "formatted": formatted,
                    "as_of_date": as_of_date,
                    "category": cat_key
                }
                mid += 1

        if category_lines:
            lines.append(f"[{label}]")
            lines.extend(category_lines)
            lines.append("")

    # Add VADER sentiment metrics (news and reddit)
    sentiment_lines = []

    # News VADER sentiment
    news_data = extracted.get("news", {})
    if news_data.get("vader_sentiment"):
        vader = news_data["vader_sentiment"]
        ref_id = f"M{mid:02d}"
        formatted = f"{vader['avg_compound']:.2f}"
        sentiment_lines.append(f"  {ref_id}: news_sentiment = {formatted} ({vader['total_count']} articles)")
        lookup[ref_id] = {
            "key": "news_sentiment",
            "raw_value": vader['avg_compound'],
            "formatted": formatted,
            "as_of_date": None,
            "category": "sentiment"
        }
        mid += 1

    # Reddit VADER sentiment
    sent_data = extracted.get("sentiment", {})
    if sent_data.get("vader_reddit"):
        vader = sent_data["vader_reddit"]
        ref_id = f"M{mid:02d}"
        formatted = f"{vader['avg_compound']:.2f}"
        sentiment_lines.append(f"  {ref_id}: reddit_sentiment = {formatted} ({vader['total_count']} posts)")
        lookup[ref_id] = {
            "key": "reddit_sentiment",
            "raw_value": vader['avg_compound'],
            "formatted": formatted,
            "as_of_date": None,
            "category": "sentiment"
        }
        mid += 1

    if sentiment_lines:
        lines.append("[SENTIMENT]")
        lines.extend(sentiment_lines)
        lines.append("")

    lines.append("=" * 60)
    lines.append("")

    return "\n".join(lines), lookup


def _compute_reference_hash(metric_lookup: dict) -> str:
    """Compute SHA256 hash of metric lookup for integrity verification."""
    # Sort keys for deterministic serialization
    serialized = json.dumps(metric_lookup, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def _verify_reference_integrity(metric_lookup: dict, stored_hash: str) -> bool:
    """Verify metric lookup hasn't been corrupted."""
    if not metric_lookup or not stored_hash:
        return False
    return _compute_reference_hash(metric_lookup) == stored_hash


def _format_reference_log(metric_lookup: dict) -> str:
    """Format metric reference as compact single-line log for activity display."""
    if not metric_lookup:
        return "No metrics extracted"

    parts = []
    for ref_id in sorted(metric_lookup.keys()):
        entry = metric_lookup[ref_id]
        key = entry.get("key", "unknown")
        formatted = entry.get("formatted", "N/A")
        # Shorten large numbers for compact display
        if "$" in formatted and len(formatted) > 15:
            # Convert $394,328,000,000 to $394.3B
            raw = entry.get("raw_value", 0)
            if isinstance(raw, (int, float)) and abs(raw) >= 1e9:
                formatted = f"${raw/1e9:.1f}B"
            elif isinstance(raw, (int, float)) and abs(raw) >= 1e6:
                formatted = f"${raw/1e6:.0f}M"
        # Remove "as of" date for compact display
        if " (as of " in formatted:
            formatted = formatted.split(" (as of ")[0]
        parts.append(f"{key}={formatted}")

    return ", ".join(parts)


# New institutional-grade prompt
ANALYZER_SYSTEM_PROMPT = """You are a senior financial analyst producing institutional-grade SWOT analyses.

## DATA GROUNDING RULES (CRITICAL)
1. USE ONLY the provided data. Never invent or assume metrics not given.
2. CITE specific numbers for every finding (e.g., "Net margin: 24.3%", "P/E: 21.3x").
3. If data is missing, state "Insufficient data" - do NOT fabricate.
4. Distinguish trailing (historical) vs forward (projected) metrics.

## AVAILABLE DATA BASKETS

### Fundamentals (SEC EDGAR + Yahoo Finance)
revenue, net_income, net_margin_pct, gross_margin_pct, operating_margin_pct,
total_assets, total_liabilities, stockholders_equity, free_cash_flow,
operating_cash_flow, long_term_debt, debt_to_equity, eps

### Valuation (Yahoo Finance)
market_cap, enterprise_value, trailing_pe, forward_pe, pb_ratio, ps_ratio,
trailing_peg, price_to_fcf, revenue_growth, earnings_growth
{ev_ebitda_note}

### Volatility (FRED + Yahoo)
vix, vxn, beta, historical_volatility, implied_volatility

### Macro (BEA/BLS/FRED)
gdp_growth, interest_rate, cpi_inflation, unemployment

### News & Sentiment
News articles with title, source, url
Sentiment scores from Finnhub and Reddit

## WHAT YOU DO NOT DO
- Provide buy/sell/hold recommendations
- Compare to sector/peer benchmarks (data not provided)
- Speculate beyond provided data
- Use vague hedge words without quantification"""


def _build_revision_prompt(
    critique_details: dict,
    company_data: str,
    current_draft: str,
    is_financial: bool,
    extracted: dict = None
) -> str:
    """Build revision prompt with conditional focus areas based on failed criteria.

    Args:
        critique_details: Structured dict from Critic with scores and feedback
        company_data: Formatted metrics string for reference
        current_draft: The current SWOT draft to be revised
        is_financial: Whether the company is a financial institution
        extracted: Extracted metrics dict for reference table generation

    Returns:
        Complete revision prompt string
    """
    # Generate metric reference table for revision (same as initial mode)
    reference_table = ""
    if extracted:
        reference_table, _ = _generate_metric_reference_table(extracted, is_financial)
    scores = critique_details.get("scores", {})

    # Determine which focus areas to include based on failed criteria
    focus_areas = []
    if scores.get("evidence_grounding", 10) < 7:
        focus_areas.append(EVIDENCE_GROUNDING_BLOCK)
    if scores.get("constraint_compliance", 10) < 6:
        focus_areas.append(CONSTRAINT_COMPLIANCE_BLOCK)
    if scores.get("specificity_actionability", 10) < 7:
        focus_areas.append(SPECIFICITY_BLOCK)
    if scores.get("strategic_insight", 10) < 7:
        focus_areas.append(INSIGHT_BLOCK)
    if scores.get("completeness_balance", 10) < 7:
        focus_areas.append(COMPLETENESS_BLOCK)
    if scores.get("clarity_structure", 10) < 7:
        focus_areas.append(CLARITY_BLOCK)

    # Format critic feedback components
    deficiencies = critique_details.get("key_deficiencies", [])
    strengths = critique_details.get("strengths_to_preserve", [])
    feedback = critique_details.get("actionable_feedback", [])

    # Build deficiencies section
    deficiencies_text = "\n".join(f"- {d}" for d in deficiencies) if deficiencies else "- None specified"

    # Build strengths section
    strengths_text = "\n".join(f"- {s}" for s in strengths) if strengths else "- None specified"

    # Build feedback section
    feedback_text = "\n".join(f"{i+1}. {f}" for i, f in enumerate(feedback)) if feedback else "- None specified"

    # Build focus areas section
    focus_areas_text = "\n".join(focus_areas) if focus_areas else "Address all deficiencies listed above."

    # Add EV/EBITDA note for financial institutions
    ev_note = ""
    if is_financial:
        ev_note = "\n**Note:** This is a financial institution - EV/EBITDA is excluded from analysis."

    prompt = f"""{reference_table}## REVISION MODE ACTIVATED

You previously generated a SWOT analysis that did not meet quality standards. You are now in revision mode.

### YOUR TASK

1. **Review the Critic's feedback** carefully
2. **Address each deficiency** listed in priority order
3. **Preserve strengths** explicitly called out — do not regress on what worked
4. **Regenerate the complete SWOT** — not a partial patch
5. **Use EXACT values from the METRIC REFERENCE TABLE above** — do not round or estimate

### CRITIC FEEDBACK

Status: {critique_details.get('status', 'REJECTED')}
Weighted Score: {critique_details.get('weighted_score', 0):.1f} / 10

**Key Deficiencies:**
{deficiencies_text}

**Strengths to Preserve:**
{strengths_text}

**Actionable Feedback:**
{feedback_text}

### FOCUS AREAS FOR THIS REVISION

{focus_areas_text}

### REVISION RULES

**DO:**
- Fix every item in "Key Deficiencies" — these are blocking issues
- Apply each point in "Actionable Feedback" — these are specific instructions
- Keep everything listed under "Strengths to Preserve" — do not modify these sections
- **Use EXACT metric values from the METRIC REFERENCE TABLE** — copy numbers verbatim
- **Include [M##] citation after every metric value** — e.g., "$394.3B [M01]"
- Include the 'as of' date when citing temporal metrics
{ev_note}

**DO NOT:**
- Ignore lower-priority feedback items — address all of them
- Introduce new metrics not in the original input data
- **Round, estimate, or approximate any numbers** — use exact values only
- **Omit [M##] citations** — they are required for automatic verification
- Remove content that was working well
- Add defensive caveats or apologies about the revision
- Reference the revision process in your output — produce a clean SWOT as if first attempt

### REFERENCE DATA

{company_data}

### CURRENT DRAFT (to revise)

{current_draft}

### OUTPUT INSTRUCTIONS

Produce a complete, revised SWOT analysis following the original template structure.

Do not:
- Include any preamble about revisions
- Apologize or explain what you changed
- Reference the Critic's feedback in your output

Simply output the improved SWOT as a clean, final deliverable."""

    return prompt


def _build_analyzer_prompt(company: str, ticker: str, formatted_data: str,
                           is_financial: bool, extracted: dict = None) -> tuple:
    """Build analyzer prompt with metric reference table for hallucination prevention.

    Args:
        company: Company name
        ticker: Stock ticker
        formatted_data: Formatted metrics text
        is_financial: If True, exclude EV/EBITDA
        extracted: Extracted metrics dict (for reference table generation)

    Returns:
        tuple: (prompt_string, metric_lookup_dict, reference_hash)
    """
    # Generate metric reference table if extracted data is available
    reference_table = ""
    metric_lookup = {}
    ref_hash = ""

    if extracted:
        reference_table, metric_lookup = _generate_metric_reference_table(extracted, is_financial)
        ref_hash = _compute_reference_hash(metric_lookup)

    if is_financial:
        ev_note = "\nNote: EV/EBITDA excluded - not meaningful for financial institutions."
    else:
        ev_note = ", ev_ebitda, ev_revenue"

    system = ANALYZER_SYSTEM_PROMPT.format(ev_ebitda_note=ev_note)

    prompt = f"""{reference_table}{system}

=== DATA FOR {company} ({ticker}) ===
{formatted_data}

=== OUTPUT FORMAT ===

Produce a SWOT analysis with this exact structure:

## Strengths
For each (3-5 points):
- **Finding:** [One sentence with metric value and citation, e.g., "Revenue of $394.3B [M01] shows..."]
- **Strategic Implication:** [Why this matters]
- **Durability:** [High/Medium/Low]

## Weaknesses
For each (3-5 points):
- **Finding:** [One sentence with metric value and citation, e.g., "Debt/equity of 1.87 [M04] indicates..."]
- **Severity:** [Critical/Moderate/Minor]
- **Trend:** [Improving/Stable/Deteriorating]
- **Remediation Levers:** [What could improve this]

## Opportunities
For each (3-5 points):
- **Catalyst:** [Description with metric citations where applicable]
- **Timing:** [Near-term/Medium-term/Long-term]
- **Execution Requirements:** [What must happen]

## Threats
For each (3-5 points):
- **Risk Factor:** [Description with metric citations where applicable]
- **Probability:** [High/Medium/Low]
- **Impact:** [Potential magnitude]
- **Mitigation Options:** [Possible responses]

## Data Quality Notes
- **Metrics Used:** [List key metrics analyzed]
- **Data Gaps:** [Any unavailable metrics]
- **Confidence Level:** [High/Medium/Low]

CRITICAL CITATION REQUIREMENTS:
1. Every numeric finding MUST include the reference ID in brackets: value [M##]
2. Use EXACT values from the METRIC REFERENCE TABLE - do NOT round or estimate
3. Example: "Revenue of $394,328,000,000 [M01] demonstrates strong market position"
4. Citations will be automatically verified - mismatches cause rejection"""

    return prompt, metric_lookup, ref_hash


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

    # Use user-provided API keys if available
    user_keys = state.get("user_api_keys", {})
    llm = get_llm_client(user_keys) if user_keys else get_llm_client()
    raw = state["raw_data"]
    company = state["company_name"]
    ticker = state.get("ticker", "")

    # Extract company profile and detect financial institution
    company_profile = _extract_company_profile(raw)
    sector = company_profile.get("sector", "")
    industry = company_profile.get("industry", "")
    is_financial = _is_financial_institution(sector, industry, ticker)

    if is_financial:
        _add_activity_log(workflow_id, progress_store, "analyzer",
                          f"Financial institution detected - excluding EV/EBITDA")

    # Extract and format metrics for better LLM understanding
    extracted = _extract_key_metrics(raw)
    formatted_data = _format_metrics_for_prompt(extracted, is_financial=is_financial)

    # Generate detailed data report (shown before SWOT)
    data_report = _generate_data_report(raw, is_financial=is_financial)

    # Detect revision mode: if we have critique_details with REJECTED status
    # (revision_count may still be 0 on first revision loop)
    critique_details = state.get("critique_details", {})
    is_revision = bool(critique_details) and critique_details.get("status") == "REJECTED"

    if is_revision and critique_details:
        # REVISION MODE: Use enhanced revision prompt with Critic feedback
        current_revision = state.get("revision_count", 0) + 1
        _add_activity_log(workflow_id, progress_store, "analyzer",
                          f"Revision #{current_revision} in progress...")

        prompt = _build_revision_prompt(
            critique_details=critique_details,
            company_data=formatted_data,
            current_draft=state.get("draft_report", ""),
            is_financial=is_financial,
            extracted=extracted
        )

        # Update progress with revision info
        if workflow_id and progress_store:
            progress_store[workflow_id].update({
                "current_step": "analyzer",
                "revision_count": current_revision,
            })
    else:
        # INITIAL MODE: Use standard analyzer prompt
        _add_activity_log(workflow_id, progress_store, "analyzer",
                          f"Calling LLM to generate SWOT analysis...")
        prompt, metric_lookup, ref_hash = _build_analyzer_prompt(
            company, ticker, formatted_data, is_financial, extracted
        )
        # Store metric reference for validation (Layer 1 hallucination prevention)
        state["metric_reference"] = metric_lookup
        state["metric_reference_hash"] = ref_hash
        # Log reference values for manual verification
        ref_log = _format_reference_log(metric_lookup)
        _add_activity_log(workflow_id, progress_store, "analyzer",
                          f"Reference values: {ref_log}")
        current_revision = 0

    # In revision mode, add delay before LLM call to avoid rate limits
    # (Critic just called LLM, so we need to wait)
    if is_revision:
        print("Waiting 5s before revision LLM call (rate limit buffer)...")
        time.sleep(5)

    start_time = time.time()
    response, provider, error, providers_failed = llm.query(prompt, temperature=0)
    elapsed = time.time() - start_time

    # Log failed providers and update LLM status in real-time
    for pf in providers_failed:
        _add_activity_log(workflow_id, progress_store, "analyzer", f"LLM {pf['name']} failed: {pf['error']}")
        # Update LLM status in real-time for frontend
        if workflow_id and progress_store and workflow_id in progress_store:
            llm_status = progress_store[workflow_id].get("llm_status", {})
            if pf["name"] in llm_status:
                llm_status[pf["name"]] = "failed"

    # Track failed providers in state for frontend
    if "llm_providers_failed" not in state:
        state["llm_providers_failed"] = []
    state["llm_providers_failed"].extend([pf["name"] for pf in providers_failed])

    # Update successful provider status
    if provider and workflow_id and progress_store and workflow_id in progress_store:
        llm_status = progress_store[workflow_id].get("llm_status", {})
        provider_name = provider.split(":")[0]
        if provider_name in llm_status:
            llm_status[provider_name] = "completed"

    if error:
        if is_revision:
            # REVISION MODE ERROR: Graceful degradation - keep previous draft
            _add_activity_log(workflow_id, progress_store, "analyzer", f"Revision failed: {error}")
            if current_revision == 1:
                _add_activity_log(workflow_id, progress_store, "analyzer",
                                  "Using initial draft (revision unavailable)")
            else:
                _add_activity_log(workflow_id, progress_store, "analyzer",
                                  f"Using revision #{current_revision - 1} draft (further revision unavailable)")
            # Don't set error - allow workflow to complete with previous draft
            state["analyzer_revision_skipped"] = True
            state["revision_count"] = current_revision
        else:
            # INITIAL MODE ERROR: Abort workflow
            state["draft_report"] = f"Error generating analysis: {error}"
            state["provider_used"] = None
            state["error"] = error  # Signal workflow to abort
            _add_activity_log(workflow_id, progress_store, "analyzer", f"LLM error: {error}")
            _add_activity_log(workflow_id, progress_store, "analyzer",
                              "Workflow aborted - all LLM providers unavailable")
    else:
        if is_revision:
            # REVISION MODE SUCCESS: Update draft with revision
            state["draft_report"] = response
            state["provider_used"] = provider
            state["analyzer_revision_skipped"] = False
            state["revision_count"] = current_revision
            _add_activity_log(workflow_id, progress_store, "analyzer",
                              f"Revision #{current_revision} completed via {provider} ({elapsed:.1f}s)")
        else:
            # INITIAL MODE SUCCESS: Combine data report with SWOT analysis
            swot_section = f"## SWOT Analysis\n\n{response}"
            full_report = f"{data_report}\n{swot_section}"
            state["draft_report"] = full_report
            state["data_report"] = data_report  # Store separately for frontend flexibility
            state["provider_used"] = provider
            _add_activity_log(workflow_id, progress_store, "analyzer",
                              f"SWOT generated via {provider} ({elapsed:.1f}s)")

    # Update progress with final revision count
    if workflow_id and progress_store:
        progress_store[workflow_id].update({
            "revision_count": state.get("revision_count", 0),
            "score": state.get("score", 0)
        })

    return state
