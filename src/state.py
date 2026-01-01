from typing import TypedDict, Optional, List, Any

class AgentState(TypedDict):
    company_name: str
    ticker: Optional[str]  # Stock ticker symbol from search
    strategy_focus: str
    raw_data: Optional[str]
    draft_report: Optional[str]
    critique: Optional[str]
    revision_count: int
    score: int
    messages: List[str]
    # Provider tracking
    provider_used: Optional[str]
    data_source: str  # "live" or "mock"
    # MCP source tracking
    sources_failed: Optional[List[str]]  # List of MCP sources that failed
    # LLM provider tracking
    llm_providers_failed: Optional[List[str]]  # List of LLM providers that failed
    # Progress tracking (for granular metrics)
    workflow_id: Optional[str]
    progress_store: Optional[Any]  # Reference to WORKFLOWS dict
    # Error handling - abort workflow on critical failures
    error: Optional[str]  # Set when LLM providers fail, causes workflow to abort
