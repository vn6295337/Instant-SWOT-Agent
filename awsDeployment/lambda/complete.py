# Lambda handler for Step Functions Complete node
# Saves final result to DynamoDB and cache

import json
import os
import sys

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflowStoreDynamo import (
    update_workflow, add_activity_log, set_workflow_result, cache_analysis
)


def lambda_handler(event, context):
    """
    Complete node - saves final result.

    Input: { workflow_id, draft_report, score, critique, ... }
    Output: { status: "completed", ... }
    """
    workflow_id = event.get('workflow_id')
    ticker = event.get('ticker')
    company = event.get('company')

    add_activity_log(workflow_id, 'Complete', 'Saving final analysis')

    try:
        draft_report = event.get('draft_report', '')
        critique = event.get('critique', '')
        score = event.get('score', 0)
        revision_count = event.get('revision_count', 0)
        provider_used = event.get('provider_used', 'unknown')

        # Save to DynamoDB
        set_workflow_result(
            workflow_id=workflow_id,
            draft_report=draft_report,
            critique=critique,
            score=score,
            revision_count=revision_count,
            provider_used=provider_used,
            data_source='live'
        )

        # Cache the result for future queries
        cache_analysis(ticker, {
            'company': company,
            'ticker': ticker,
            'draft_report': draft_report,
            'critique': critique,
            'score': score,
            'revision_count': revision_count,
            'provider_used': provider_used
        })

        add_activity_log(workflow_id, 'Complete', f'Analysis complete! Score: {score}/10, Revisions: {revision_count}')

        # Return final result
        return {
            'workflow_id': workflow_id,
            'status': 'completed',
            'company': company,
            'ticker': ticker,
            'draft_report': draft_report,
            'critique': critique,
            'score': score,
            'revision_count': revision_count,
            'provider_used': provider_used,
            'data_source': 'live'
        }

    except Exception as e:
        error_msg = f'Complete error: {str(e)}'
        add_activity_log(workflow_id, 'Error', error_msg)
        update_workflow(workflow_id, {'status': 'failed', 'error': error_msg})

        return {
            'workflow_id': workflow_id,
            'status': 'failed',
            'error': error_msg
        }
