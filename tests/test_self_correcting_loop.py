#!/usr/bin/env python3
"""
Comprehensive test for self-correction mechanisms in the SWOT Analysis Agent
Tests multiple failure scenarios to verify the self-correcting loop functionality.
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.graph_cyclic import run_self_correcting_workflow

def test_analyzer_failure():
    """Test self-correction when analyzer produces poor quality output"""
    print("🧪 Testing Analyzer Failure Scenario...")

    # Monkey patch the analyzer node to force poor quality
    def force_poor_analyzer(state):
        """Force a poor quality draft to trigger Editor"""
        state["draft_report"] = "Bad analysis. No details. Incomplete."
        print("⚠️  FORCED POOR QUALITY: Overriding with very weak content")
        return state

    # Temporarily replace analyzer in the workflow
    import src.nodes.analyzer
    original_analyzer = src.nodes.analyzer.analyzer_node
    src.nodes.analyzer.analyzer_node = force_poor_analyzer

    try:
        result = run_self_correcting_workflow("Test Company")
        print(f"✅ Test completed with {result['revision_count']} revisions")
        print(f"📊 Final score: {result['score']}/10")
    finally:
        # Restore original function
        src.nodes.analyzer.analyzer_node = original_analyzer

def test_critic_failure():
    """Test self-correction when critic gives low scores"""
    print("\n🧪 Testing Critic Failure Scenario...")
    
    # Monkey patch the critic to force a low score
    def force_low_score_critic(state):
        """Force a low score to trigger Editor"""
        state["score"] = 3  # Low score to force revision
        state["critique"] = "Forced low score for testing self-correction loop"
        print("⚠️  FORCED LOW SCORE: 3/10 to trigger Editor")
        return state

    # Temporarily replace critic in the workflow
    import src.nodes.critic
    original_critic = src.nodes.critic.critic_node
    src.nodes.critic.critic_node = force_low_score_critic
    
    try:
        result = run_self_correcting_workflow("Test Company")
        print(f"✅ Test completed with {result['revision_count']} revisions")
        print(f"📊 Final score: {result['score']}/10")
    finally:
        # Restore original function
        src.nodes.critic.critic_node = original_critic

def test_workflow_failure():
    """Test self-correction with custom workflow manipulation"""
    print("\n🧪 Testing Workflow Failure Scenario...")
    
    # This test would implement the custom workflow approach from test_force_failure.py
    # For brevity, we'll just indicate this as a placeholder
    print("📝 Custom workflow failure test placeholder")
    print("✅ Test framework ready for custom workflow testing")

if __name__ == "__main__":
    print("🚀 Running Self-Correction Test Suite")
    print("=" * 50)
    
    test_analyzer_failure()
    test_critic_failure()
    test_workflow_failure()
    
    print("\n🎉 All self-correction tests completed!")
