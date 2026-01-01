export interface AnalysisRequest {
  company_name: string
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
}