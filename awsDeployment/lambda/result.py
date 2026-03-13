# Lambda handler for GET /workflow/{id}/result endpoint
# Returns final SWOT analysis

import json

from workflowStoreDynamo import get_workflow, get_cached_analysis
from swot_parser import parse_swot_text


def lambda_handler(event, context):
    """
    Returns completed SWOT analysis.

    Input: path parameter workflow_id
    Output: { "status": "completed", "draft_report": "...", "score": 8, ... }
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
            ticker = workflow_id.replace('cached-', '')
            cached = get_cached_analysis(ticker)
            if cached:
                result = cached.get('result', {})
                # Return the full cached result if it has swot_data
                if result.get('swot_data'):
                    return {
                        'statusCode': 200,
                        'headers': cors_headers(),
                        'body': json.dumps(result)
                    }
                # Fallback for old cache format
                return {
                    'statusCode': 200,
                    'headers': cors_headers(),
                    'body': json.dumps({
                        'company_name': cached.get('company', ''),
                        'ticker': ticker,
                        'score': result.get('score', 0),
                        'revision_count': result.get('revision_count', 0),
                        'report_length': len(result.get('draft_report', '')),
                        'critique': result.get('critique', ''),
                        'swot_data': parse_swot_text(result.get('draft_report', '')),
                        'raw_report': result.get('draft_report', ''),
                        'provider_used': result.get('provider_used', 'cached'),
                        'data_source': 'cached'
                    })
                }
            else:
                return {
                    'statusCode': 404,
                    'headers': cors_headers(),
                    'body': json.dumps({'error': 'Cached result not found or expired'})
                }

        # Get workflow from DynamoDB
        workflow = get_workflow(workflow_id)

        if not workflow:
            return {
                'statusCode': 404,
                'headers': cors_headers(),
                'body': json.dumps({'error': 'Workflow not found'})
            }

        status = workflow.get('status', 'unknown')

        # Check if workflow is complete
        if status == 'completed':
            # Return the full structured result if available
            result = workflow.get('result')
            if result:
                return {
                    'statusCode': 200,
                    'headers': cors_headers(),
                    'body': json.dumps(result)
                }

            # Fallback: parse SWOT from draft_report
            draft_report = workflow.get('draft_report', '')
            swot_data = workflow.get('swot_data') or parse_swot_text(draft_report)

            return {
                'statusCode': 200,
                'headers': cors_headers(),
                'body': json.dumps({
                    'company_name': workflow.get('company', ''),
                    'ticker': workflow.get('ticker', ''),
                    'score': workflow.get('score', 0),
                    'revision_count': workflow.get('revision_count', 0),
                    'report_length': len(draft_report),
                    'critique': workflow.get('critique', ''),
                    'swot_data': swot_data,
                    'raw_report': draft_report,
                    'provider_used': workflow.get('provider_used', ''),
                    'data_source': workflow.get('data_source', 'live'),
                    'raw_data': workflow.get('raw_data', {})
                })
            }
        elif status == 'failed':
            return {
                'statusCode': 200,
                'headers': cors_headers(),
                'body': json.dumps({
                    'workflow_id': workflow_id,
                    'status': 'failed',
                    'error': workflow.get('error', 'Unknown error'),
                    'current_step': workflow.get('current_step', '')
                })
            }
        else:
            # Still running
            return {
                'statusCode': 202,
                'headers': cors_headers(),
                'body': json.dumps({
                    'workflow_id': workflow_id,
                    'status': status,
                    'current_step': workflow.get('current_step', ''),
                    'message': 'Analysis still in progress'
                })
            }

    except Exception as e:
        print(f"Error in result handler: {e}")
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
