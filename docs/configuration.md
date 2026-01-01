# Configuration Guide

## Quick Start

```bash
cp .env.example .env
# Edit .env with your API keys
```

## Environment Variables

### LLM Providers (at least one required)

The system uses a fallback chain: Groq → Gemini → OpenRouter

| Variable | Description | Required |
|----------|-------------|----------|
| `GROQ_API_KEY` | Groq API key (primary, fastest) | Recommended |
| `GROQ_MODEL` | Model name (default: `llama-3.1-8b-instant`) | No |
| `GEMINI_API_KEY` | Google Gemini API key (fallback 1) | No |
| `GEMINI_MODEL` | Model name (default: `gemini-2.0-flash-exp`) | No |
| `OPENROUTER_API_KEY` | OpenRouter API key (fallback 2) | No |
| `OPENROUTER_MODEL` | Model name (default: `google/gemini-2.0-flash-exp:free`) | No |

### Search API

| Variable | Description | Required |
|----------|-------------|----------|
| `TAVILY_API_KEY` | Tavily search API for live company data | Yes |

### MCP Server APIs (optional)

| Variable | Description | Source |
|----------|-------------|--------|
| `FRED_API_KEY` | Federal Reserve data (VIX) | [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html) |
| `ALPHA_VANTAGE_API_KEY` | Options implied volatility | [alphavantage.co](https://www.alphavantage.co/support/#api-key) |
| `FINNHUB_API_KEY` | News sentiment data | [finnhub.io](https://finnhub.io/register) |

### A2A Protocol (optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_A2A_RESEARCHER` | `false` | Enable A2A mode for Researcher |
| `A2A_RESEARCHER_URL` | HuggingFace Spaces URL | Researcher A2A server endpoint |
| `A2A_TIMEOUT` | `60` | Request timeout in seconds |

### Observability (optional)

| Variable | Description |
|----------|-------------|
| `LANGCHAIN_API_KEY` | LangSmith API key |
| `LANGCHAIN_TRACING_V2` | Enable tracing (`true`/`false`) |
| `LANGCHAIN_PROJECT` | Project name in LangSmith |

## Deployment Environments

### Local Development

```bash
cp .env.example .env
# Add your API keys

# Run Streamlit UI
streamlit run streamlit_app.py

# Or run FastAPI backend (serves React frontend at localhost:8002)
python -m src.main api
```

### Docker

```bash
docker run --env-file .env -p 7860:7860 ai-strategy-copilot
```

### Hugging Face Spaces

Add secrets in Space Settings → Repository secrets:
- `GROQ_API_KEY`
- `TAVILY_API_KEY`
- (other optional keys)

## Troubleshooting

| Error | Solution |
|-------|----------|
| `No LLM provider configured` | Set at least one of: GROQ_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY |
| `TAVILY_API_KEY missing` | Required for live company research |
| `MCP server timeout` | Check individual API keys for MCP servers |
