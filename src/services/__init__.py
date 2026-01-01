"""
Shared services for Instant SWOT Agent.
Contains business logic used across API and Streamlit interfaces.
"""

from src.services.swot_parser import parse_swot_text
from src.services.confidence import calculate_confidence
from src.services.workflow_store import (
    WORKFLOWS,
    add_activity_log,
    add_metric,
    update_mcp_status,
    run_workflow_background,
)

__all__ = [
    "parse_swot_text",
    "calculate_confidence",
    "WORKFLOWS",
    "add_activity_log",
    "add_metric",
    "update_mcp_status",
    "run_workflow_background",
]
