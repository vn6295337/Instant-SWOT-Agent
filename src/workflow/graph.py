"""
LangGraph workflow definition for self-correcting SWOT analysis.
Defines the cyclic workflow: Researcher -> Analyzer -> Critic -> Editor (loop)
"""

from langgraph.graph import StateGraph
from langchain_core.runnables import RunnableLambda

from src.state import AgentState
from src.nodes.researcher import researcher_node
from src.nodes.analyzer import analyzer_node
from src.nodes.critic import critic_node
from src.nodes.editor import editor_node
from src.utils.conditions import should_continue

# Create the cyclic workflow
workflow = StateGraph(AgentState)

# Add all nodes to the workflow
workflow.add_node("Researcher", RunnableLambda(researcher_node))
workflow.add_node("Analyzer", RunnableLambda(analyzer_node))
workflow.add_node("Critic", RunnableLambda(critic_node))
workflow.add_node("Editor", RunnableLambda(editor_node))

# Define the workflow edges
workflow.set_entry_point("Researcher")
workflow.add_edge("Researcher", "Analyzer")
workflow.add_edge("Analyzer", "Critic")

# Add conditional edges for the self-correcting loop
workflow.add_conditional_edges(
    "Critic",
    should_continue,
    {
        "exit": "__end__",
        "retry": "Editor"
    }
)

# Complete the loop: Editor -> Critic
workflow.add_edge("Editor", "Critic")

# Set the finish point
workflow.set_finish_point("Critic")

# Enhanced configuration for better tracing
workflow.config = {
    "project_name": "AI-strategy-agent-cyclic",
    "tags": ["self-correcting", "quality-loop", "swot-analysis"],
    "metadata": {
        "version": "1.0",
        "environment": "development",
        "workflow_type": "researcher-analyzer-critic-editor"
    }
}

# Compile the workflow
app = workflow.compile()
