# Lambda handler for Step Functions Critic node
# Evaluates SWOT quality and assigns score

import json
import os
import sys

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from secretsHelper import inject_secrets_to_env
from workflowStoreDynamo import update_workflow, add_activity_log


def lambda_handler(event, context):
    """
    Critic agent - evaluates SWOT quality.

    Input: { workflow_id, draft_report, revision_count, ... }
    Output: { ..., score: 8, critique: "..." }
    """
    # Inject secrets
    inject_secrets_to_env()

    workflow_id = event.get('workflow_id')
    revision_count = event.get('revision_count', 0)
    draft_report = event.get('draft_report', '')

    add_activity_log(workflow_id, 'Critic', f'Evaluating SWOT analysis (revision {revision_count})')
    update_workflow(workflow_id, {'status': 'running', 'current_step': 'Critic'})

    try:
        # Import and run the existing critic node function
        from src.nodes.critic import critic_node

        # Get metric_reference from Analyzer output (needed for numeric validation)
        metric_reference = event.get('metric_reference', {})
        metric_reference_hash = event.get('metric_reference_hash', '')

        # Create state for critic - include metric_reference for validation
        state = {
            'company_name': event.get('company'),
            'ticker': event.get('ticker'),
            'strategy_focus': event.get('strategy_focus', 'general'),
            'raw_data': event.get('raw_data', {}),
            'draft_report': draft_report,
            'revision_count': revision_count,
            'metric_reference': metric_reference,
            'metric_reference_hash': metric_reference_hash
        }

        # Run critic
        result = critic_node(state, workflow_id=workflow_id)
        score = result.get('score', 0)
        critique = result.get('critique', '')

        add_activity_log(workflow_id, 'Critic', f'Score: {score}/10')

        if score < 7 and revision_count < 3:
            add_activity_log(workflow_id, 'Critic', f'Score below threshold. Requesting revision.')
        elif score >= 7:
            add_activity_log(workflow_id, 'Critic', f'Score meets threshold. Analysis approved.')
        else:
            add_activity_log(workflow_id, 'Critic', f'Max revisions reached. Accepting current analysis.')

        # Get critique_details for revision loop (critical for analyzer revision mode)
        critique_details = result.get('critique_details', {})

        update_workflow(workflow_id, {
            'score': score,
            'critique': critique,
            'revision_count': revision_count
        })

        # Return updated state for CheckScore step
        # CRITICAL: Include critique_details for analyzer revision mode
        return {
            **event,
            'score': score,
            'critique': critique,
            'critique_details': critique_details,
            'metric_reference': metric_reference,
            'metric_reference_hash': metric_reference_hash,
            'revision_count': revision_count,
            'current_step': 'Critic'
        }

    except Exception as e:
        error_msg = f'Critic error: {str(e)}'
        add_activity_log(workflow_id, 'Error', error_msg)

        # Return with low score to trigger revision or completion
        # Include all required fields with defaults to prevent Step Functions errors
        return {
            **event,
            'score': 5,  # Low score to potentially trigger revision
            'critique': f'Evaluation error: {str(e)}',
            'critique_details': {'status': 'REJECTED', 'error': str(e)},
            'metric_reference': event.get('metric_reference', {}),
            'metric_reference_hash': event.get('metric_reference_hash', ''),
            'current_step': 'Critic'
        }
