# A2A Researcher Agent Architecture

## Overview

The Researcher agent supports two modes:
- **Direct Mode** (default): Calls MCP servers directly from the main process
- **A2A Mode**: Delegates to a standalone A2A server for parallel data fetching

Enable A2A mode by setting `USE_A2A_RESEARCHER=true` in your environment.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Main Orchestrator (LangGraph)                          │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Researcher Node                                 │   │
│  │  (src/nodes/researcher.py)                       │   │
│  │                                                  │   │
│  │  if USE_A2A_RESEARCHER:                          │   │
│  │      → A2A Client (researcher_a2a_client.py)     │   │
│  │  else:                                           │   │
│  │      → Direct MCP calls                          │   │
│  └──────────────────────────────────────────────────┘   │
│       │                                                 │
│       │ JSON-RPC 2.0 over HTTP (A2A mode only)          │
│       ↓                                                 │
└───────┼─────────────────────────────────────────────────┘
        │
┌───────┴─────────────────────────────────────────────────┐
│  Researcher A2A Server (optional, external)             │
│  (a2a/researcher_server.py)                             │
│                                                         │
│  Endpoints:                                             │
│  - GET  /.well-known/agent.json  (Agent Card)           │
│  - POST /  (JSON-RPC: message/send, tasks/get)          │
│                                                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │
│  │ Financials  │ │  Sentiment  │ │    News     │ ...    │
│  │ MCP Server  │ │  MCP Server │ │  MCP Server │        │
│  └─────────────┘ └─────────────┘ └─────────────┘        │
└─────────────────────────────────────────────────────────┘
```

## A2A Protocol

A2A (Agent-to-Agent) is Google's open protocol for agent interoperability.

Reference: https://github.com/google-a2a/A2A

### Agent Card

Served at `/.well-known/agent.json`:

```json
{
  "name": "swot-researcher",
  "version": "1.0.0",
  "description": "Financial research agent for SWOT analysis",
  "capabilities": {
    "streaming": false,
    "pushNotifications": false
  },
  "skills": [{
    "id": "research-company",
    "name": "Company Research",
    "inputModes": ["text"],
    "outputModes": ["text", "data"]
  }]
}
```

### JSON-RPC Methods

| Method | Description |
|--------|-------------|
| `message/send` | Submit research task |
| `tasks/get` | Get task status/results |
| `tasks/cancel` | Cancel running task |

### Task Lifecycle

```
SUBMITTED → WORKING → COMPLETED
                   ↘ FAILED
```

## File Structure

```
a2a/
├── researcher_server.py      # A2A server implementation
├── agent_card.json           # Agent capabilities metadata
└── mcp_aggregator.py         # Calls MCP servers in parallel

src/nodes/
├── researcher.py             # Mode switch (A2A vs Direct)
└── researcher_a2a_client.py  # A2A client wrapper
```

## Benefits of A2A Mode

| Aspect | Direct Mode | A2A Mode |
|--------|-------------|----------|
| Latency | Sequential MCP calls | Parallel MCP calls |
| Scaling | Coupled with orchestrator | Independent scaling |
| Fault Isolation | Shared process | Separate process |
| Reusability | Single workflow | Any A2A client |

## Fallback Behavior

If the A2A server is unavailable, the system falls back to direct mode automatically.
