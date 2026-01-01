---
title: Instant SWOT Agent
emoji: 📊
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
short_description: Instant SWOT Agent with self-correcting feedback
---

# Instant SWOT Agent

**Multi-agent workflow with self-correcting quality control for strategic analysis.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

| Resource | Link |
|----------|------|
| Live Demo | [huggingface.co/spaces/vn6295337/Instant-SWOT-Agent](https://huggingface.co/spaces/vn6295337/Instant-SWOT-Agent) |
| Product Demo Video | [Pre-recorded Demo](https://github.com/vn6295337/Instant-SWOT-Agent/issues/1) |
| Business Guide | [BUSINESS_README.md](BUSINESS_README.md) |

---

## The Problem

Strategic analysis is time-consuming and quality varies widely. Analysts spend hours gathering data and drafting reports, with no systematic quality checks until peer review—often too late in the process.

## The Solution

This demo implements an **agentic AI pattern** where specialized agents collaborate autonomously: one gathers data, another drafts analysis, a third evaluates quality, and a fourth revises until standards are met. The self-correcting loop eliminates the "first draft = final draft" problem common in LLM applications.

## Why This Matters

Most enterprise AI deployments fail not from bad models, but from lack of quality gates. This architecture demonstrates how to build reliability into AI workflows—a pattern applicable to any domain requiring consistent output quality.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                                  │
│                             (React + Vite)                                  │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ORCHESTRATION (LangGraph)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Researcher  │─▶│   Analyst    │─▶│    Critic    │─▶│    Editor    │    │
│  │              │  │  (SWOT Gen)  │  │  (Scoring)   │  │  (Revision)  │    │
│  └──────────────┘  └──────────────┘  └──────┬───────┘  └───────┬──────┘    │
│                                             │   score < 7      │           │
│                                             │◀─────────────────┘           │
│                                             ▼                              │
│                                      score ≥ 7 or 3 revisions → [END]      │
└─────────────────────────────────────────────┬───────────────────────────────┘
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    │                         │                         │
                    ▼                         ▼                         ▼
┌───────────────────────────┐ ┌───────────────────────────┐ ┌───────────────────────────┐
│  1. FINANCIALS BASKET     │ │  2. VOLATILITY BASKET     │ │  3. MACRO BASKET          │
│     (MCP Server) ✓        │ │     (MCP Server) ✓        │ │     (MCP Server) ✓        │
├───────────────────────────┤ ├───────────────────────────┤ ├───────────────────────────┤
│ • get_financials          │ │ • get_vix                 │ │ • get_gdp                 │
│ • get_debt_metrics        │ │ • get_beta                │ │ • get_interest_rates      │
│ • get_cash_flow           │ │ • get_historical_vol      │ │ • get_cpi                 │
│ • get_material_events     │ │ • get_implied_vol         │ │ • get_unemployment        │
│ • get_ownership_filings   │ │ • get_volatility_basket   │ │ • get_macro_basket        │
│ • get_going_concern       │ │                           │ │                           │
│ • get_sec_fundamentals    │ │                           │ │                           │
└─────────────┬─────────────┘ └─────────────┬─────────────┘ └─────────────┬─────────────┘
              │                             │                             │
              ▼                             ▼                             ▼
┌───────────────────────────┐ ┌───────────────────────────┐ ┌───────────────────────────┐
│      SEC EDGAR API        │ │  FRED API + Yahoo Finance │ │         FRED API          │
│      (Free, Public)       │ │  (Free with API Key)      │ │      (Free with Key)      │
└───────────────────────────┘ └───────────────────────────┘ └───────────────────────────┘

┌───────────────────────────┐ ┌───────────────────────────┐ ┌───────────────────────────┐
│  4. VALUATION BASKET      │ │  5. NEWS BASKET           │ │  6. SENTIMENT BASKET      │
│     (MCP Server) ✓        │ │     (MCP Server) ✓        │ │     (MCP Server) ✓        │
├───────────────────────────┤ ├───────────────────────────┤ ├───────────────────────────┤
│ • get_pe_ratio            │ │ • search_company_news     │ │ • get_social_sentiment    │
│ • get_ps_ratio            │ │ • search_going_concern    │ │ • get_analyst_ratings     │
│ • get_pb_ratio            │ │ • search_industry_trends  │ │                           │
│ • get_ev_ebitda           │ │ • search_competitor_news  │ │                           │
│ • get_valuation_basket    │ │ • tavily_search           │ │                           │
└─────────────┬─────────────┘ └─────────────┬─────────────┘ └─────────────┬─────────────┘
              │                             │                             │
              ▼                             ▼                             ▼
┌───────────────────────────┐ ┌───────────────────────────┐ ┌───────────────────────────┐
│    Yahoo + SEC EDGAR      │ │       Tavily API          │ │     Finnhub API           │
│      (Free/Public)        │ │  (Free 1,000/month)       │ │   (Free with API Key)     │
└───────────────────────────┘ └───────────────────────────┘ └───────────────────────────┘

```

### MCP Baskets Summary

| # | Basket | Status | Source | Key Metrics |
|---|--------|--------|--------|-------------|
| 1 | Financials | ✓ Done | SEC EDGAR | Revenue, Margins, Debt, Cash Flow, 8-K, Ownership |
| 2 | Volatility | ✓ Done | FRED + Yahoo | VIX, Beta, Historical Vol, Implied Vol |
| 3 | Macro | ✓ Done | FRED | GDP, CPI, Interest Rates, Unemployment |
| 4 | Valuation | ✓ Done | Yahoo + SEC | P/E, P/S, P/B, EV/EBITDA, PEG |
| 5 | News | ✓ Done | Tavily | Company News, Industry Trends, Competitors |
| 6 | Sentiment | ✓ Done | Finnhub | Social Sentiment, Analyst Ratings |

### Data Flow

```
User Input (Company) → Researcher → [MCP Servers] → Raw Data
                                         ↓
Raw Data → Analyst → SWOT Draft → Critic → Score
                                     ↓
                        Score < 7 → Editor → Revised Draft → Critic
                        Score ≥ 7 → Final Output → User
```

## Features

| Agent | Role | Implementation |
|-------|------|----------------|
| **Researcher** | Gathers real-time company data | 6 MCP servers (financials, volatility, macro, valuation, news, sentiment) |
| **Analyst** | Drafts SWOT based on selected strategy | Prompt-engineered generation |
| **Critic** | Scores output 1-10 with reasoning | Rubric-based evaluation |
| **Editor** | Revises based on critique | Targeted improvement |

**Supported Strategies:** Cost Leadership, Differentiation, Focus/Niche

## MCP Data Servers

Model Context Protocol (MCP) servers provide structured data access for AI agents. See [BUSINESS_README.md](BUSINESS_README.md) for detailed explanation.

### Financials Basket

| Location | Metric | Tool |
|----------|--------|------|
| `mcp-servers/financials-basket/` | Revenue, Net Income, Margins | `get_financials` |
| | Debt, Debt-to-Equity | `get_debt_metrics` |
| | Operating CF, CapEx, FCF, R&D | `get_cash_flow` |
| | 8-K Material Events | `get_material_events` |
| | 13D/13G, Form 4 (Ownership) | `get_ownership_filings` |
| | Going Concern Warnings | `get_going_concern` |
| | All Metrics + SWOT | `get_sec_fundamentals` |

### Volatility Basket

| Location | Metric | Tool |
|----------|--------|------|
| `mcp-servers/volatility-basket/` | VIX Index | `get_vix` |
| | Beta (vs S&P 500) | `get_beta` |
| | Historical Volatility | `get_historical_volatility` |
| | Implied Volatility | `get_implied_volatility` |
| | All Metrics + SWOT | `get_volatility_basket` |

### Macro Basket

| Location | Metric | Tool |
|----------|--------|------|
| `mcp-servers/macro-basket/` | GDP Growth Rate | `get_gdp` |
| | Federal Funds Rate | `get_interest_rates` |
| | CPI / Inflation | `get_cpi` |
| | Unemployment Rate | `get_unemployment` |
| | All Metrics + SWOT | `get_macro_basket` |

### Valuation Basket

| Location | Metric | Tool |
|----------|--------|------|
| `mcp-servers/valuation-basket/` | P/E Ratio | `get_pe_ratio` |
| | P/S Ratio | `get_ps_ratio` |
| | P/B Ratio | `get_pb_ratio` |
| | EV/EBITDA | `get_ev_ebitda` |
| | PEG Ratio | `get_peg_ratio` |
| | All Metrics + SWOT | `get_valuation_basket` |

### News Basket

| Location | Metric | Tool |
|----------|--------|------|
| `mcp-servers/news-basket/` | General Web Search | `tavily_search` |
| | Company News | `search_company_news` |
| | Going Concern News | `search_going_concern_news` |
| | Industry Trends | `search_industry_trends` |
| | Competitor News | `search_competitor_news` |

### Sentiment Basket

| Location | Metric | Tool |
|----------|--------|------|
| `mcp-servers/sentiment-basket/` | Social Sentiment | `get_social_sentiment` |
| | Analyst Ratings | `get_analyst_ratings` |

### API Endpoints

| MCP Server | API | Endpoint | Auth |
|------------|-----|----------|------|
| **Financials Basket** | SEC EDGAR | `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json` | None (free) |
| | | `https://data.sec.gov/submissions/CIK{cik}.json` | |
| **Volatility Basket** | FRED | `https://api.stlouisfed.org/fred/series/observations` | API Key |
| | Yahoo Finance | `https://query1.finance.yahoo.com/v8/finance/chart/{ticker}` | None |
| **Macro Basket** | FRED | `https://api.stlouisfed.org/fred/series/observations` | API Key |
| **Valuation Basket** | Yahoo Finance | `https://query1.finance.yahoo.com/v10/finance/quoteSummary/{ticker}` | None |
| **News Basket** | Tavily | `https://api.tavily.com/search` | API Key |
| **Sentiment Basket** | Finnhub | `https://finnhub.io/api/v1/` | API Key |

### API Keys

| Key | Environment Variable | Get From |
|-----|---------------------|----------|
| FRED | `FRED_VIX_API_KEY` | https://fred.stlouisfed.org/docs/api/api_key.html |
| Tavily | `TAVILY_API_KEY` | https://tavily.com |
| Finnhub | `FINNHUB_API_KEY` | https://finnhub.io |

Store in `.env`:
```
FRED_VIX_API_KEY=your_key
TAVILY_API_KEY=tvly-your_key
FINNHUB_API_KEY=your_key
```

## Installation & Setup

### Local Development

```bash
# Clone the repository
git clone https://github.com/vn6295337/Instant-SWOT-Agent.git
cd Instant-SWOT-Agent

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# Run the application (FastAPI + React UI)
python -m src.main api
# Or use make
make api
```

### Hugging Face Spaces Deployment

1. **Create a new Space** (Docker SDK)
2. **Add this repository** as the source
3. **Set up Secrets** (at least one LLM provider required):
   - `GROQ_API_KEY` (primary, recommended)
   - `GEMINI_API_KEY` (fallback)
   - `OPENROUTER_API_KEY` (fallback)
   - `TAVILY_API_KEY` (for live search data)
4. The system automatically falls back through providers if one fails

## Requirements

- Python 3.11+
- At least one LLM API key (Groq, Gemini, or OpenRouter)
- Tavily API key (optional, for live search data)

## Usage Examples

### Web UI
```bash
# Start the FastAPI server with React frontend
python -m src.main api
```
Open http://localhost:7860, enter a company name (e.g., "Tesla", "NVIDIA", "Microsoft") and click "Generate SWOT".

### CLI Usage
```bash
# Analyze a company from command line
python -m src.main analyze --company "Apple" --strategy "Differentiation"
```

### Programmatic Usage
```python
from src.workflow.runner import run_self_correcting_workflow

# Generate SWOT analysis with specific strategy
result = run_self_correcting_workflow(company_name="Apple", strategy_focus="Differentiation")

print(f"Score: {result['score']}/10")
print(f"Revisions: {result['revision_count']}")
print(f"SWOT Analysis:\n{result['draft_report']}")
```

## Testing

```bash
# Run tests
make test
# Or directly
python3 tests/test_self_correcting_loop.py
```

## Technical Characteristics

- **Analysis Time**: Typically under 10 seconds (depends on API latency)
- **Quality Loop**: Iterates until score ≥ 7/10 or max 3 revisions
- **LLM Providers**: Groq (primary) → Gemini → OpenRouter (cascading fallback)
- **Data Sources**: 6 MCP servers aggregating SEC EDGAR, FRED, Yahoo Finance, Tavily, and Finnhub APIs
- **Frontend**: React + TypeScript + Vite + Tailwind CSS
- **Backend**: FastAPI with async workflow execution

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Orchestration** | LangGraph | Native support for cyclic workflows; cleaner than raw LangChain for multi-agent patterns |
| **LLM Provider** | Groq (Llama 3.1 8B) | Sub-second inference enables tight feedback loops; cost-effective for demos |
| **Quality Threshold** | 7/10 | Balances quality vs. latency; lower values cause excessive loops, higher values rarely achievable |
| **Max Revisions** | 3 | Empirically, quality plateaus after 2-3 iterations; prevents infinite loops |
| **Same Model for Critic** | Intentional tradeoff | Production would use a stronger model for evaluation; kept simple for demo cost management |
| **Web Search** | Tavily API | Purpose-built for LLM applications; returns clean, structured content |

### Known Limitations

- **Self-evaluation bias**: The critic uses the same model family as the analyst. A production system would use a more capable evaluator model or human-in-the-loop for high-stakes decisions.
- **Mock data visibility**: When Tavily API is unavailable, the UI clearly indicates cached data is being used.

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License.

---