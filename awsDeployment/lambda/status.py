# Lambda handler for GET /workflow/{id}/status endpoint
# Reads workflow state from DynamoDB

import json
import os
import boto3

from workflowStoreDynamo import get_workflow

# Step Functions client for execution status
sfn_client = boto3.client('stepfunctions', region_name=os.environ.get('AWS_REGION', 'us-east-1'))


def lambda_handler(event, context):
    """
    Returns workflow status.

    Input: path parameter workflow_id
    Output: { "status": "running", "current_step": "Analyzer", "score": 0, ... }
    """
    try:
        # Get workflow_id from path parameters
        path_params = event.get('pathParameters', {}) or {}
        workflow_id = path_params.get('id')

        if not workflow_id:
            return {
                'statusCode': 400,
                'headers': cors_headers(),
                'body': json.dumps({'error': 'Missing workflow_id'})
            }

        # Handle cached results
        if workflow_id.startswith('cached-'):
            return {
                'statusCode': 200,
                'headers': cors_headers(),
                'body': json.dumps({
                    'workflow_id': workflow_id,
                    'status': 'completed',
                    'current_step': 'Complete',
                    'cached': True
                })
            }

        # Get workflow from DynamoDB
        workflow = get_workflow(workflow_id)

        if not workflow:
            return {
                'statusCode': 404,
                'headers': cors_headers(),
                'body': json.dumps({'error': 'Workflow not found'})
            }

        # Check Step Functions execution status if still running
        if workflow.get('status') not in ['completed', 'failed']:
            try:
                execution_arn = f"arn:aws:states:us-east-1:691210491730:execution:swot-agent-workflow:{workflow_id}"
                response = sfn_client.describe_execution(executionArn=execution_arn)
                sfn_status = response.get('status', 'UNKNOWN')

                # Map Step Functions status to workflow status
                if sfn_status == 'RUNNING':
                    workflow['status'] = 'running'
                elif sfn_status == 'SUCCEEDED':
                    workflow['status'] = 'completed'
                elif sfn_status in ['FAILED', 'TIMED_OUT', 'ABORTED']:
                    workflow['status'] = 'failed'
                    workflow['error'] = response.get('cause', 'Execution failed')
            except Exception as e:
                # Step Functions execution might not exist yet or already cleaned up
                print(f"Could not get Step Functions status: {e}")

        # Return status response
        return {
            'statusCode': 200,
            'headers': cors_headers(),
            'body': json.dumps({
                'workflow_id': workflow_id,
                'status': workflow.get('status', 'unknown'),
                'current_step': workflow.get('current_step', ''),
                'revision_count': workflow.get('revision_count', 0),
                'score': workflow.get('score', 0),
                'activity_log': workflow.get('activity_log', [])[-10:],  # Last 10 entries
                'metrics': workflow.get('metrics', []),
                'mcp_status': workflow.get('mcp_status', {}),
                'llm_status': workflow.get('llm_status', {}),
                'created_at': workflow.get('created_at'),
                'updated_at': workflow.get('updated_at')
            })
        }

    except Exception as e:
        print(f"Error in status handler: {e}")
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
