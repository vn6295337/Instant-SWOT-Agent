# Instant SWOT Agent - React Frontend

## Overview

React-based frontend for Instant SWOT Agent, providing a modern UI for SWOT analysis with real-time workflow visualization.

## Tech Stack

- **React 18** with TypeScript
- **Vite** build system
- **Tailwind CSS** + shadcn/ui components
- **TanStack Query** for data fetching
- **React Router** for routing

## Core Components

| Component | Purpose |
|-----------|---------|
| `App.tsx` | Main layout, workflow orchestration, state management |
| `ProcessFlow.tsx` | SVG-based visual workflow diagram |
| `StockSearch.tsx` | Autocomplete search with keyboard navigation |
| `ActivityLog.tsx` | Real-time log viewer with auto-scroll |

## Installation

```bash
cd frontend
npm install
```

## Development

```bash
# Start dev server (port 5173)
npm run dev

# Run tests
npm test

# Type check
npx tsc --noEmit

# Build for production
npm run build
```

## API Integration

The frontend connects to the FastAPI backend. API endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/stocks/search` | GET | Stock autocomplete |
| `/analyze` | POST | Start analysis workflow |
| `/workflow/{id}/status` | GET | Workflow status polling |
| `/workflow/{id}/result` | GET | Get final results |

### Environment Variables

Create `.env` for local development:

```bash
VITE_API_URL=http://localhost:8002
```

Production builds auto-detect the API URL.

## Production Deployment

The frontend is pre-built and served from `/static/` by the FastAPI backend:

```bash
# Build production bundle
npm run build

# Copy to static directory
cp -r dist/* ../static/
```

The Dockerfile uses pre-built static files for HuggingFace Spaces deployment.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Dependencies fail | `rm -rf node_modules && npm install` |
| TypeScript errors | `npx tsc --noEmit` to check |
| Port in use | `npm run dev -- --port 3000` |
