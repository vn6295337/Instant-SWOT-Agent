export interface AnalysisRequest {
  company_name: string
}

// Metric with temporal metadata (fiscal year, period end, form type)
export interface TemporalMetric {
  value: number | null
  end_date?: string       // Fiscal period end date, e.g., "2023-09-30"
  fiscal_year?: number    // Fiscal year number, e.g., 2023
  form?: string           // SEC form type: "10-K" (annual) or "10-Q" (quarterly)
}

// News article from MCP
export interface NewsArticle {
  title: string
  url: string
  snippet?: string
  source?: string
  published_date?: string
}

// Sentiment data from MCP
export interface SentimentData {
  analyst_rating?: string
  analyst_target_price?: number
  recommendation_trend?: Record<string, number>
  social_sentiment?: number
  news_sentiment?: number
  insider_sentiment?: string
  [key: string]: unknown
}

// Raw data from all MCP servers
export interface MCPRawData {
  sources_available?: string[]
  sources_failed?: string[]
  metrics?: Record<string, unknown>
  company_info?: {
    sector?: string
    industry?: string
    city?: string
    state?: string
    country?: string
    address?: string
    location?: string
    fullTimeEmployees?: number
    employees?: number
  }
  // Fundamentals MCP (with temporal data for SEC EDGAR metrics)
  fundamentals?: {
    revenue?: TemporalMetric | number
    gross_margin?: number
    operating_margin?: number
    net_margin?: number
    debt_to_equity?: number
    current_ratio?: number
    cash_flow?: TemporalMetric | number
    eps?: TemporalMetric | number
    net_income?: TemporalMetric | number
    free_cash_flow?: TemporalMetric | number
    [key: string]: TemporalMetric | number | unknown
  }
  // Valuation MCP
  valuation?: {
    pe_ratio?: number
    ps_ratio?: number
    pb_ratio?: number
    ev_ebitda?: number
    peg_ratio?: number
    market_cap?: number
    [key: string]: unknown
  }
  // Volatility MCP
  volatility?: {
    beta?: number
    vix?: number
    historical_volatility?: number
    implied_volatility?: number
    [key: string]: unknown
  }
  // Macro MCP
  macro?: {
    gdp_growth?: number
    interest_rate?: number
    inflation_rate?: number
    unemployment_rate?: number
    [key: string]: unknown
  }
  // News MCP
  news?: NewsArticle[]
  // Sentiment MCP
  sentiment?: SentimentData
  // Aggregated SWOT from MCPs
  aggregated_swot?: {
    strengths?: string[]
    weaknesses?: string[]
    opportunities?: string[]
    threats?: string[]
  }
}

export interface AnalysisResponse {
  company_name: string
  score: number
  revision_count: number
  report_length: number
  critique: string
  swot_data: {
    strengths: string[]
    weaknesses: string[]
    opportunities: string[]
    threats: string[]
  }
  raw_data?: MCPRawData
}