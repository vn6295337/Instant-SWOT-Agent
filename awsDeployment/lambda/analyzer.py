# Lambda handler for Step Functions Analyzer node
# Generates SWOT analysis from research data

import json
import os
import sys

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from secretsHelper import inject_secrets_to_env
from workflowStoreDynamo import update_workflow, add_activity_log


def lambda_handler(event, context):
    """
    Analyzer agent - generates SWOT analysis.

    Input: { workflow_id, company, ticker, raw_data, revision_count, critique, ... }
    Output: { ..., draft_report: "..." }
    """
    # Inject secrets
    inject_secrets_to_env()

    workflow_id = event.get('workflow_id')
    company = event.get('company')
    ticker = event.get('ticker')
    revision_count = event.get('revision_count', 0)
    critique = event.get('critique', '')

    if revision_count > 0:
        add_activity_log(workflow_id, 'Analyzer', f'Revision {revision_count}: Improving analysis based on feedback')
    else:
        add_activity_log(workflow_id, 'Analyzer', f'Generating SWOT analysis for {company}')

    update_workflow(workflow_id, {'status': 'running', 'current_step': 'Analyzer'})

    try:
        # Import and run the existing analyzer node function
        from src.nodes.analyzer import analyzer_node

        # Get critique_details for revision mode detection (critical for agentic loop)
        critique_details = event.get('critique_details', {})

        # Get metric reference from previous runs (for numeric validation)
        metric_reference = event.get('metric_reference', {})
        metric_reference_hash = event.get('metric_reference_hash', '')

        # Create state for analyzer - must include all fields for revision mode
        state = {
            'company_name': company,
            'ticker': ticker,
            'strategy_focus': event.get('strategy_focus', 'general'),
            'raw_data': event.get('raw_data', {}),
            'critique': critique,
            'critique_details': critique_details,  # CRITICAL: enables revision mode
            'revision_count': revision_count,
            'draft_report': event.get('draft_report', ''),
            'metric_reference': metric_reference,
            'metric_reference_hash': metric_reference_hash
        }

        # Run analyzer
        result = analyzer_node(state, workflow_id=workflow_id)
        draft_report = result.get('draft_report', '')
        provider_used = result.get('provider_used', 'unknown')

        # Get updated metric reference (set during first pass, persists through revisions)
        new_metric_reference = result.get('metric_reference', metric_reference)
        new_metric_reference_hash = result.get('metric_reference_hash', metric_reference_hash)

        add_activity_log(workflow_id, 'Analyzer', f'SWOT analysis generated using {provider_used}')
        update_workflow(workflow_id, {
            'draft_report': draft_report,
            'provider_used': provider_used,
            'llm_status': {provider_used.split(':')[0]: 'completed'}
        })

        # Return updated state for next step
        # Include metric_reference for Critic's numeric validation
        return {
            **event,
            'draft_report': draft_report,
            'provider_used': provider_used,
            'metric_reference': new_metric_reference,
            'metric_reference_hash': new_metric_reference_hash,
            'current_step': 'Analyzer'
        }

    except Exception as e:
        error_msg = f'Analyzer error: {str(e)}'
        add_activity_log(workflow_id, 'Error', error_msg)

        # Return with error but don't fail workflow - critic will catch it
        # Include required fields with defaults to prevent Step Functions errors
        return {
            **event,
            'draft_report': f'Error generating analysis: {str(e)}',
            'metric_reference': event.get('metric_reference', {}),
            'metric_reference_hash': event.get('metric_reference_hash', ''),
            'current_step': 'Analyzer'
        }
