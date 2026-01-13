from langgraph.graph import StateGraph
from langchain_core.runnables import RunnableLambda
from src.state import AgentState
from src.nodes.researcher import researcher_node
from src.nodes.analyzer import analyzer_node
from src.nodes.critic import critic_node
from src.utils.conditions import should_continue
from langsmith import traceable

# Create the cyclic workflow
workflow = StateGraph(AgentState)

# Add nodes to the workflow (Analyzer handles both initial generation and revisions)
workflow.add_node("Researcher", RunnableLambda(researcher_node))
workflow.add_node("Analyzer", RunnableLambda(analyzer_node))
workflow.add_node("Critic", RunnableLambda(critic_node))

# Define the workflow edges
workflow.set_entry_point("Researcher")
workflow.add_edge("Researcher", "Analyzer")
workflow.add_edge("Analyzer", "Critic")

# Add conditional edges for the self-correcting loop
# Analyzer now handles revisions directly (no separate Editor node)
workflow.add_conditional_edges(
    "Critic",
    should_continue,
    {
        "exit": "__end__",
        "retry": "Analyzer"  # Route back to Analyzer for revisions
    }
)

# Set the finish point
workflow.set_finish_point("Critic")

# Enhanced configuration for better tracing
workflow.config = {
    "project_name": "AI-strategy-agent-cyclic",
    "tags": ["self-correcting", "quality-loop", "swot-analysis"],
    "metadata": {
        "version": "2.0",
        "environment": "development",
        "workflow_type": "researcher-analyzer-critic"
    }
}

# Compile the workflow
app = workflow.compile()

# Wrapped execution with enhanced tracing
@traceable(name="Run - Self-Correcting SWOT Analysis", tags=["cyclic", "quality-control", "demo"], metadata={"purpose": "iterative_improvement"})
def run_self_correcting_workflow(company_name="Tesla", strategy_focus="Cost Leadership", workflow_id=None, progress_store=None):
    """Execute the complete self-correcting SWOT analysis workflow"""

    # Initialize state with default values
    initial_state = {
        "company_name": company_name,
        "strategy_focus": strategy_focus,
        "raw_data": None,
        "draft_report": None,
        "critique": None,
        "revision_count": 0,
        "messages": [],
        "score": 0,
        "data_source": "live",
        "provider_used": None,
        "sources_failed": [],
        "workflow_id": workflow_id,
        "progress_store": progress_store,
        "error": None  # Set when LLM providers fail
    }
    
    # Execute the workflow
    output = app.invoke(initial_state, config={
        "configurable": {
            "workflow_id": workflow_id,
            "progress_store": progress_store
        }
    })
    
    return output

# Main execution
if __name__ == "__main__":
    # Test with Tesla as the default company
    target_company = "Tesla"
    
    print(f"🔍 Running Self-Correcting SWOT Analysis for {target_company}...")
    print("📝 This workflow includes: Researcher → Analyzer → Critic → Analyzer (revision loop)")
    print("🎯 Loop continues until score ≥ 7 or 3 revisions attempted\n")
    
    # Execute the workflow
    result = run_self_correcting_workflow(target_company)
    
    # Display results (with safe fallbacks)
    print(f"🏁 Analysis completed for {target_company}!")
    final_score = result.get('score', 'N/A')
    final_revision_count = result.get('revision_count', 0)
    final_critique = result.get('critique', 'No critique available')
    
    print(f"📊 Final Score: {final_score}/10")
    print(f"🔄 Revision Count: {final_revision_count}")
    print(f"💬 Critique: {final_critique}")
    print(f"\n📄 Final SWOT Analysis:")
    print(result['draft_report'])
    
    # Summary
    print(f"\n✅ Self-Correcting Workflow Summary:")
    print(f"   - Company: {target_company}")
    print(f"   - Initial Quality: Improved from unknown to {final_score}/10")
    print(f"   - Revisions Made: {final_revision_count}")
    print(f"   - Final Report Length: {len(result['draft_report'])} characters")
    print(f"   - Workflow: Researcher → Analyzer → Critic → Analyzer (revision loop)")
    print(f"   - Tracing: Enhanced LangSmith traces available")
    
    # Quality assessment
    print(f"   - Quality Score: {final_score}/10")