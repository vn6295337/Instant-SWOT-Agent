# Lambda handler for POST /analyze endpoint
# Triggers Step Functions workflow

import json
import os
import uuid
import boto3

# Import local modules
from secretsHelper import inject_secrets_to_env
from workflowStoreDynamo import create_workflow, get_cached_analysis, add_activity_log

# Initialize clients
sfn_client = boto3.client('stepfunctions', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# State machine ARN
STATE_MACHINE_ARN = os.environ.get(
    'STATE_MACHINE_ARN',
    'arn:aws:states:us-east-1:691210491730:stateMachine:swot-agent-workflow'
)


def lambda_handler(event, context):
    """
    Starts SWOT analysis workflow.

    Input: { "name": "Apple", "ticker": "AAPL", "strategy_focus": "Differentiation" }
    Output: { "workflow_id": "uuid" }
    """
    # Inject secrets into environment
    inject_secrets_to_env()

    try:
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event.get('body', '{}'))
        else:
            body = event.get('body') or event

        company = body.get('name', '')
        ticker = body.get('ticker', '').upper()
        strategy_focus = body.get('strategy_focus', 'general')
        skip_cache = body.get('skip_cache', False)

        if not company or not ticker:
            return {
                'statusCode': 400,
                'headers': cors_headers(),
                'body': json.dumps({'error': 'Missing required fields: name and ticker'})
            }

        # Check cache first (unless skip_cache is True)
        if not skip_cache:
            cached = get_cached_analysis(ticker)
            if cached:
                return {
                    'statusCode': 200,
                    'headers': cors_headers(),
                    'body': json.dumps({
                        'workflow_id': f"cached-{ticker}",
                        'status': 'completed',
                        'cached': True,
                        'result': cached.get('result')
                    })
                }

        # Generate workflow ID
        workflow_id = str(uuid.uuid4())

        # Create workflow record in DynamoDB
        create_workflow(workflow_id, company, ticker, strategy_focus)
        add_activity_log(workflow_id, 'System', f'Starting analysis for {company} ({ticker})')

        # Start Step Functions execution
        sfn_input = {
            'workflow_id': workflow_id,
            'company': company,
            'ticker': ticker,
            'strategy_focus': strategy_focus,
            'revision_count': 0,
            'raw_data': {},
            'draft_report': '',
            'critique': '',
            'score': 0
        }

        try:
            response = sfn_client.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                name=workflow_id,
                input=json.dumps(sfn_input)
            )
            execution_arn = response['executionArn']
            add_activity_log(workflow_id, 'System', f'Step Functions execution started: {execution_arn}')
        except Exception as e:
            add_activity_log(workflow_id, 'Error', f'Failed to start Step Functions: {str(e)}')
            return {
                'statusCode': 500,
                'headers': cors_headers(),
                'body': json.dumps({'error': f'Failed to start workflow: {str(e)}'})
            }

        return {
            'statusCode': 200,
            'headers': cors_headers(),
            'body': json.dumps({
                'workflow_id': workflow_id,
                'status': 'started',
                'message': f'Analysis started for {company} ({ticker})'
            })
        }

    except Exception as e:
        print(f"Error in analyze handler: {e}")
        return {
            'statusCode': 500,
            'headers': cors_headers(),
            'body': json.dumps({'error': str(e)})
        }


def cors_headers():
    """Return CORS headers."""
    return {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
    }
