import { AnalysisResponse } from './types'

// In production (HF Spaces), API is served from same origin - use empty string
// In development, use localhost:8002
const API_BASE_URL = import.meta.env.VITE_API_URL ?? (import.meta.env.PROD ? '' : 'http://localhost:8002')

// Stock search types
export interface StockResult {
  symbol: string
  name: string
  exchange: string
  match_type: string
}

export interface StockSearchResponse {
  query: string
  results: StockResult[]
}

// Activity log entry
export interface ActivityLogEntry {
  timestamp: string
  step: string
  message: string
}

// Granular metric entry
export interface MetricEntry {
  timestamp: string
  source: string   // "volatility", "valuation", "financials", etc.
  metric: string   // "beta", "P/E", "revenue", etc.
  value: string | number
}

// MCP status for each server (partial = some data but with errors)
export interface MCPStatus {
  financials: 'idle' | 'executing' | 'completed' | 'partial' | 'failed'
  valuation: 'idle' | 'executing' | 'completed' | 'partial' | 'failed'
  volatility: 'idle' | 'executing' | 'completed' | 'partial' | 'failed'
  macro: 'idle' | 'executing' | 'completed' | 'partial' | 'failed'
  news: 'idle' | 'executing' | 'completed' | 'partial' | 'failed'
  sentiment: 'idle' | 'executing' | 'completed' | 'partial' | 'failed'
}

// LLM provider status
export interface LLMStatus {
  groq: 'idle' | 'executing' | 'completed' | 'failed'
  gemini: 'idle' | 'executing' | 'completed' | 'failed'
  openrouter: 'idle' | 'executing' | 'completed' | 'failed'
}

// Workflow status with activity log and MCP status
export interface WorkflowStatus {
  status: 'starting' | 'running' | 'completed' | 'error' | 'aborted'
  current_step: 'input' | 'cache' | 'researcher' | 'analyzer' | 'critic' | 'editor' | 'output' | 'completed'
  revision_count: number
  score: number
  activity_log: ActivityLogEntry[]
  metrics: MetricEntry[]
  mcp_status: MCPStatus
  llm_status: LLMStatus
  provider_used?: string
  data_source?: string
  error?: string  // Error message for error/aborted states
}

export interface WorkflowStartResponse {
  workflow_id: string
}

// Search stocks by query
export async function searchStocks(query: string): Promise<StockSearchResponse> {
  const response = await fetch(`${API_BASE_URL}/api/stocks/search?q=${encodeURIComponent(query)}`)

  if (!response.ok) {
    throw new Error('Failed to search stocks')
  }

  return response.json()
}

// Start analysis with ticker support
export async function startAnalysis(
  companyName: string,
  ticker: string = '',
  strategyFocus: string = 'Competitive Position'
): Promise<WorkflowStartResponse> {
  const response = await fetch(`${API_BASE_URL}/analyze`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      name: companyName,
      ticker: ticker,
      strategy_focus: strategyFocus
    }),
  })

  if (!response.ok) {
    throw new Error('Failed to start analysis')
  }

  return response.json()
}

export async function getWorkflowStatus(workflowId: string): Promise<WorkflowStatus> {
  const response = await fetch(`${API_BASE_URL}/workflow/${workflowId}/status`)

  if (!response.ok) {
    throw new Error('Failed to get workflow status')
  }

  return response.json()
}

export async function getWorkflowResult(workflowId: string): Promise<AnalysisResponse> {
  const response = await fetch(`${API_BASE_URL}/workflow/${workflowId}/result`)

  if (!response.ok) {
    throw new Error('Failed to get workflow result')
  }

  return response.json()
}

export async function checkHealth(): Promise<{ status: string; active_workflows?: number }> {
  const response = await fetch(`${API_BASE_URL}/health`)

  if (!response.ok) {
    throw new Error('API health check failed')
  }

  return response.json()
}
