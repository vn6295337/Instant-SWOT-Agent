# Architecture Documentation

## System Overview

Instant SWOT Agent is an AI-powered strategic analysis system that generates comprehensive SWOT analyses for companies with automatic quality improvement through a self-correcting loop.

## High-Level Architecture

```
User Input (Company Name)
         ↓
┌────────────────────────────────────────┐
│           USER INTERFACE               │
│    Streamlit (streamlit_app.py)        │
│    React (frontend/) via FastAPI       │
└────────────────────────────────────────┘
         ↓
┌────────────────────────────────────────┐
│     FastAPI Backend (src/api/app.py)   │
│   Routes: analysis.py, stocks.py       │
└────────────────────────────────────────┘
         ↓
   Workflow Engine (LangGraph)
   src/workflow/graph.py
         ↓
   Node Orchestration
   ↙  ↓  ↓  ↓  ↘
Researcher → Analyzer → Critic → Editor
                 ↘________↗ (loop until score ≥7 or 3 revisions)
         ↓
   Final SWOT Analysis
```

## Directory Structure

```
src/
├── api/                    # FastAPI backend
│   ├── app.py              # Application factory
│   ├── schemas.py          # Pydantic models
│   └── routes/
│       ├── analysis.py     # Workflow endpoints
│       └── stocks.py       # Stock search endpoint
├── workflow/               # LangGraph workflow
│   ├── graph.py            # Workflow definition
│   └── runner.py           # Execution wrapper
├── nodes/                  # Workflow nodes
├── services/               # Shared services
│   ├── swot_parser.py      # SWOT text parsing
│   ├── confidence.py       # Confidence calculation
│   └── workflow_store.py   # Workflow state management
├── utils/                  # Utilities
└── main.py                 # CLI entry point
```

## Core Components

### 1. Workflow Engine

Located in `src/workflow/graph.py`, implements the self-correcting workflow:

- **Entry**: Researcher node
- **Flow**: Researcher → Analyzer → Critic → (conditional) Editor
- **Exit**: Score ≥ 7 OR revision_count ≥ 3

### 2. Workflow Nodes

Located in `src/nodes/`:

| Node | File | Responsibility |
|------|------|----------------|
| Researcher | `researcher.py` | Gathers data via MCP servers, summarizes with LLM |
| Analyzer | `analyzer.py` | Generates SWOT analysis draft |
| Critic | `critic.py` | Evaluates quality (1-10 score) using rubric |
| Editor | `editor.py` | Revises draft based on critique |

### 3. MCP Servers

Located in `mcp-servers/`, providing data aggregation:

| Server | Data Source | Output |
|--------|-------------|--------|
| financials-basket | SEC EDGAR | Financial statements |
| volatility-basket | Yahoo Finance, FRED | VIX, Beta, IV |
| macro-basket | FRED | GDP, rates, CPI |
| valuation-basket | Yahoo Finance, SEC | P/E, P/B, EV/EBITDA |
| news-basket | Tavily | News articles |
| sentiment-basket | Finnhub | Sentiment scores |

### 4. State Management

Defined in `src/state.py`, the workflow state flows through each node:

```python
state = {
    "company_name": str,
    "strategy_focus": str,
    "raw_data": str,
    "draft_report": str,
    "critique": str,
    "score": int,
    "revision_count": int,
    "error": str | None
}
```

## Data Flow

1. **Input**: User enters company name via Streamlit UI
2. **Research**: Researcher node queries MCP servers for financial data
3. **Analysis**: Analyzer generates initial SWOT draft
4. **Evaluation**: Critic scores draft (1-10) against rubric
5. **Improvement**: If score < 7 and revisions < 3, Editor revises
6. **Output**: Final SWOT displayed with quality metrics

## Quality Evaluation

The Critic node uses a rubric-based system:

- **Completeness** (25%): All SWOT sections populated
- **Specificity** (25%): Concrete, actionable insights with data
- **Relevance** (25%): Aligned with company context
- **Depth** (25%): Strategic sophistication

Threshold: Score ≥ 7/10 to pass without revision.

## Extending the System

### Adding a New Node

1. Create `src/nodes/new_node.py`:
```python
def new_node(state: dict) -> dict:
    # Process state
    state["new_field"] = result
    return state
```

2. Register in `src/workflow/graph.py`:
```python
workflow.add_node("NewNode", RunnableLambda(new_node))
workflow.add_edge("PreviousNode", "NewNode")
```

### Adding a New MCP Server

1. Create directory `mcp-servers/new-basket/`
2. Implement server with tool registration
3. Update Researcher node to call new server

## Observability

- **LangSmith**: End-to-end workflow tracing (configure via environment variables)
- **Logging**: Python standard logging at INFO/DEBUG levels

## Error Handling

- MCP server failures: Graceful degradation, continue with available data
- LLM failures: Retry with fallback providers
- Quality failures: Maximum 3 revision attempts before accepting result
