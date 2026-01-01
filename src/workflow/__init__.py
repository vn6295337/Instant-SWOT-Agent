"""
Workflow module for Instant SWOT Agent.
Contains LangGraph workflow definitions and execution.
"""

from src.workflow.graph import app, workflow
from src.workflow.runner import run_self_correcting_workflow

__all__ = ["app", "workflow", "run_self_correcting_workflow"]
