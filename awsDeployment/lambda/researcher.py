# Lambda handler for Step Functions Researcher node
# Gathers data from external APIs (financial, news, sentiment)

import json
import os
import sys

# Add paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from secretsHelper import inject_secrets_to_env
from workflowStoreDynamo import update_workflow, add_activity_log, update_mcp_status


def lambda_handler(event, context):
    """
    Researcher agent - gathers data from MCP servers.

    Input: { workflow_id, company, ticker, strategy_focus, ... }
    Output: { ..., raw_data: {...} }
    """
    # Inject secrets
    inject_secrets_to_env()

    workflow_id = event.get('workflow_id')
    company = event.get('company')
    ticker = event.get('ticker')

    add_activity_log(workflow_id, 'Researcher', f'Starting research for {company} ({ticker})')
    update_workflow(workflow_id, {'status': 'running', 'current_step': 'Researcher'})

    try:
        # Import and run the existing researcher node function
        from src.nodes.researcher import researcher_node

        # Create initial state
        state = {
            'company_name': company,
            'ticker': ticker,
            'strategy_focus': event.get('strategy_focus', 'general'),
            'raw_data': {},
            'activity_log': [],
            'mcp_status': {}
        }

        # Run researcher
        add_activity_log(workflow_id, 'Researcher', 'Gathering financial data...')
        update_mcp_status(workflow_id, 'fundamentals', 'running')

        result = researcher_node(state, workflow_id=workflow_id)
        raw_data = result.get('raw_data', {})

        # Update MCP status
        for mcp_name in ['fundamentals', 'valuation', 'volatility', 'macro', 'news', 'sentiment']:
            status = 'completed' if mcp_name in raw_data else 'skipped'
            update_mcp_status(workflow_id, mcp_name, status)

        add_activity_log(workflow_id, 'Researcher', f'Research complete. Gathered {len(raw_data)} data sources.')
        update_workflow(workflow_id, {'raw_data': raw_data})

        # Return updated state for next step
        return {
            **event,
            'raw_data': raw_data,
            'current_step': 'Researcher'
        }

    except Exception as e:
        error_msg = f'Researcher error: {str(e)}'
        add_activity_log(workflow_id, 'Error', error_msg)
        update_workflow(workflow_id, {'status': 'failed', 'error': error_msg})

        # Return with empty data to allow workflow to continue or fail gracefully
        return {
            **event,
            'raw_data': {'error': str(e)},
            'current_step': 'Researcher'
        }
