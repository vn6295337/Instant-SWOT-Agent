# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-agent AI system that generates SWOT analyses for publicly-traded companies using a self-correcting workflow. Python/FastAPI backend with TypeScript/React frontend.

**Live Demo:** https://huggingface.co/spaces/vn6295337/Instant-SWOT-Agent

## Common Commands

### Backend (Python)
```bash
make api                    # Run FastAPI server (port 7860)
make test                   # Run pytest tests
make lint                   # Run flake8 and pylint
make format                 # Format with black
make coverage               # Run tests with coverage
make analyze TICKER=AAPL    # CLI analysis for a ticker
```

### Frontend (TypeScript/React)
```bash
cd frontend
npm run dev                 # Vite dev server (port 5173)
npm run build               # Production build
npm run lint                # ESLint
npm test                    # Vitest unit tests
npm run test:e2e            # Playwright E2E tests
npm run storybook           # Component docs (port 6006)
```

### Full Stack
```bash
make frontend               # Run both backend and React frontend
```

## Architecture

```
User Input → Researcher → [6 MCP Servers] → Raw Data
                                ↓
Raw Data → Analyst → SWOT Draft → Critic → Score
                                    ↓
                   Score < 7 → Editor → Revised Draft → Critic
                   Score ≥ 7 or 3 revisions → Final Output
```

**Agent Workflow (LangGraph):**
1. **Researcher** - Gathers data from MCP servers (fundamentals, volatility, macro, valuation, news, sentiment)
2. **Analyst** - Generates SWOT draft based on strategy focus
3. **Critic** - Scores output 1-10 with rubric-based evaluation
4. **Editor** - Revises based on critique (loops until score ≥ 7 or 3 revisions)

**Key Files:**
- `src/workflow/graph.py` - LangGraph workflow definition
- `src/nodes/` - Agent implementations (researcher, analyzer, critic, editor)
- `src/api/app.py` - FastAPI application
- `src/state.py` - TypedDict for workflow state
- `frontend/src/App.tsx` - Main React component

## API Endpoints

- `POST /analyze` - Start SWOT analysis (returns workflow_id)
- `GET /workflow/{id}/status` - Progress and metrics
- `GET /workflow/{id}/result` - Final results
- `GET /api/stocks/search?q=` - Stock ticker search
- `GET /health` - Health check

## Environment Variables

Required (at least one LLM provider):
- `GROQ_API_KEY` - Primary LLM (Llama 3.1 8B)
- `GEMINI_API_KEY` - Fallback
- `OPENROUTER_API_KEY` - Fallback

Data sources:
- `TAVILY_API_KEY` - Web search
- `FRED_API_KEY` - Macro data
- `FINNHUB_API_KEY` - Sentiment/ratings

## Tech Stack

**Backend:** Python 3.11+, FastAPI, LangGraph, LangChain, Pydantic
**Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Radix UI, React Query
**Testing:** pytest (backend), Vitest + Playwright (frontend)
