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


def _generate_data_report(raw_data: str) -> str:
    """Generate complete multi-source data report with simple tables."""
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
            ("EV/EBITDA", "ev_ebitda", lambda v: _format_number(v, "x")),
            ("EV/Revenue", "ev_revenue", lambda v: _format_number(v, "x")),
            ("PEG Ratio", "trailing_peg", lambda v: _format_number(v, "x")),
            ("Price/FCF", "price_to_fcf", lambda v: _format_number(v, "x")),
            ("Revenue Growth", "revenue_growth", lambda v: _format_number(v * 100 if v and abs(v) < 10 else v, "%") if v else "N/A"),
            ("Earnings Growth", "earnings_growth", lambda v: _format_number(v * 100 if v and abs(v) < 10 else v, "%") if v else "N/A"),
        ]

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

    # Use user-provided API keys if available
    user_keys = state.get("user_api_keys", {})
    llm = get_llm_client(user_keys) if user_keys else get_llm_client()
    raw = state["raw_data"]
    strategy_name = state.get("strategy_focus", "Cost Leadership")
    strategy_context = get_strategy_context(strategy_name)
    company = state["company_name"]
    ticker = state.get("ticker", "")

    # Extract and format metrics for better LLM understanding
    extracted = _extract_key_metrics(raw)
    formatted_data = _format_metrics_for_prompt(extracted)

    # Generate detailed data report (shown before SWOT)
    data_report = _generate_data_report(raw)

    # Log LLM call start
    _add_activity_log(workflow_id, progress_store, "analyzer", f"Calling LLM to generate SWOT analysis...")

    prompt = f"""You are a financial analyst creating a CONCISE SWOT analysis for {company} ({ticker}).

CRITICAL INSTRUCTIONS:
1. ONLY use the data provided below. DO NOT invent or assume any information.
2. Every point MUST cite specific numbers from the data (e.g., "P/E of 21.3", "Beta of 0.88").
3. If data is missing for a category, say "Insufficient data" - do NOT make up information.
4. Focus on what the numbers actually mean for this specific company.

FORMAT REQUIREMENTS - BE CONCISE:
- Each bullet point: 1 sentence MAX (under 25 words)
- 3-5 bullet points per SWOT category
- Focus on the most impactful insights only
- NO lengthy explanations or context paragraphs

Strategic Focus: {strategy_name}
Context: {strategy_context}

=== ACTUAL DATA FROM FINANCIAL SOURCES ===
{formatted_data}

Based ONLY on the data above, provide a SWOT analysis in this format:

Strengths:
- [Single sentence with metric, under 25 words]

Weaknesses:
- [Single sentence with metric, under 25 words]

Opportunities:
- [Single sentence citing macro/market data, under 25 words]

Threats:
- [Single sentence citing risks, under 25 words]

Remember: Every bullet must cite actual data. Keep each point brief and impactful."""
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
        state["draft_report"] = f"Error generating analysis: {error}"
        state["provider_used"] = None
        state["error"] = error  # Signal workflow to abort
        _add_activity_log(workflow_id, progress_store, "analyzer", f"LLM error: {error}")
        _add_activity_log(workflow_id, progress_store, "analyzer", "Workflow aborted - all LLM providers unavailable")
    else:
        # Combine data report (Part 1) with SWOT analysis (Part 2)
        swot_section = f"## SWOT Analysis\n\n{response}"
        full_report = f"{data_report}\n{swot_section}"
        state["draft_report"] = full_report
        state["data_report"] = data_report  # Store separately for frontend flexibility
        state["provider_used"] = provider
        _add_activity_log(workflow_id, progress_store, "analyzer", f"SWOT generated via {provider} ({elapsed:.1f}s)")

    return state
