"""
Pydantic models for API request/response schemas.
"""

from pydantic import BaseModel


class AnalysisRequest(BaseModel):
    """Request model for starting a SWOT analysis."""
    name: str
    ticker: str = ""
    strategy_focus: str = "Competitive Position"


class StockSearchResult(BaseModel):
    """Single stock search result."""
    symbol: str
    name: str
    exchange: str
    match_type: str


class WorkflowStartResponse(BaseModel):
    """Response model for workflow start."""
    workflow_id: str


class WorkflowStatus(BaseModel):
    """Workflow status model."""
    status: str  # 'running', 'completed', 'error'
    current_step: str  # 'starting', 'Researcher', 'Analyzer', 'Critic', 'Editor'
    revision_count: int
    score: int


class SwotData(BaseModel):
    """SWOT analysis data structure."""
    strengths: list[str]
    weaknesses: list[str]
    opportunities: list[str]
    threats: list[str]


class AnalysisResult(BaseModel):
    """Final analysis result model."""
    company_name: str
    score: int
    revision_count: int
    report_length: int
    critique: str
    swot_data: SwotData
