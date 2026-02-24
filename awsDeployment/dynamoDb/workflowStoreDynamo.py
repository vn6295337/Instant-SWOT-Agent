# DynamoDB adapter for workflow state management
# Replaces in-memory workflow_store.py for AWS deployment

import boto3
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from decimal import Decimal

# DynamoDB client
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
workflows_table = dynamodb.Table('swot-workflows')
cache_table = dynamodb.Table('swot-cache')


class DecimalEncoder(json.JSONEncoder):
    """Handle Decimal types from DynamoDB."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def create_workflow(workflow_id: str, company: str, ticker: str, strategy_focus: str = None) -> Dict:
    """Create new workflow entry in DynamoDB."""
    now = datetime.utcnow()
    expires_at = int((now + timedelta(hours=24)).timestamp())

    item = {
        'workflow_id': workflow_id,
        'company': company,
        'ticker': ticker,
        'strategy_focus': strategy_focus or 'general',
        'status': 'pending',
        'current_step': 'Initializing',
        'revision_count': 0,
        'score': 0,
        'activity_log': [],
        'metrics': [],
        'mcp_status': {},
        'llm_status': {},
        'raw_data': {},
        'draft_report': '',
        'critique': '',
        'created_at': now.isoformat(),
        'updated_at': now.isoformat(),
        'expires_at': expires_at
    }

    workflows_table.put_item(Item=item)
    return item


def get_workflow(workflow_id: str) -> Optional[Dict]:
    """Get workflow state from DynamoDB."""
    try:
        response = workflows_table.get_item(Key={'workflow_id': workflow_id})
        item = response.get('Item')
        if item:
            # Convert Decimals to native types
            return json.loads(json.dumps(item, cls=DecimalEncoder))
        return None
    except Exception as e:
        print(f"Error getting workflow {workflow_id}: {e}")
        return None


def update_workflow(workflow_id: str, updates: Dict[str, Any]) -> None:
    """Update workflow state in DynamoDB."""
    updates['updated_at'] = datetime.utcnow().isoformat()

    update_expr_parts = []
    expr_attr_values = {}
    expr_attr_names = {}

    for i, (key, value) in enumerate(updates.items()):
        placeholder = f":val{i}"
        name_placeholder = f"#attr{i}"
        update_expr_parts.append(f"{name_placeholder} = {placeholder}")
        expr_attr_values[placeholder] = value
        expr_attr_names[name_placeholder] = key

    update_expr = "SET " + ", ".join(update_expr_parts)

    try:
        workflows_table.update_item(
            Key={'workflow_id': workflow_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_attr_values,
            ExpressionAttributeNames=expr_attr_names
        )
    except Exception as e:
        print(f"Error updating workflow {workflow_id}: {e}")
        raise


def add_activity_log(workflow_id: str, step: str, message: str) -> None:
    """Append to workflow activity log."""
    timestamp = datetime.utcnow().isoformat()
    log_entry = {
        'timestamp': timestamp,
        'step': step,
        'message': message
    }

    try:
        workflows_table.update_item(
            Key={'workflow_id': workflow_id},
            UpdateExpression="SET activity_log = list_append(if_not_exists(activity_log, :empty), :entry), updated_at = :now",
            ExpressionAttributeValues={
                ':entry': [log_entry],
                ':empty': [],
                ':now': timestamp
            }
        )
    except Exception as e:
        print(f"Error adding activity log: {e}")


def update_mcp_status(workflow_id: str, mcp_name: str, status: str) -> None:
    """Update MCP server status."""
    try:
        workflows_table.update_item(
            Key={'workflow_id': workflow_id},
            UpdateExpression="SET mcp_status.#mcp = :status, updated_at = :now",
            ExpressionAttributeNames={'#mcp': mcp_name},
            ExpressionAttributeValues={
                ':status': status,
                ':now': datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        print(f"Error updating MCP status: {e}")


def get_cached_analysis(ticker: str) -> Optional[Dict]:
    """Check cache for existing analysis (24h TTL)."""
    try:
        response = cache_table.get_item(Key={'ticker': ticker.upper()})
        item = response.get('Item')
        if item:
            # Check if expired (TTL might not have cleaned up yet)
            expires_at = item.get('expires_at', 0)
            if expires_at > datetime.utcnow().timestamp():
                return json.loads(json.dumps(item, cls=DecimalEncoder))
        return None
    except Exception as e:
        print(f"Error getting cached analysis for {ticker}: {e}")
        return None


def cache_analysis(ticker: str, result: Dict) -> None:
    """Cache completed analysis with 24h TTL."""
    expires_at = int((datetime.utcnow() + timedelta(hours=24)).timestamp())

    item = {
        'ticker': ticker.upper(),
        'result': result,
        'cached_at': datetime.utcnow().isoformat(),
        'expires_at': expires_at
    }

    try:
        cache_table.put_item(Item=item)
    except Exception as e:
        print(f"Error caching analysis for {ticker}: {e}")


def set_workflow_result(workflow_id: str, draft_report: str, critique: str, score: int,
                        revision_count: int, provider_used: str, data_source: str) -> None:
    """Set final workflow result."""
    update_workflow(workflow_id, {
        'status': 'completed',
        'current_step': 'Complete',
        'draft_report': draft_report,
        'critique': critique,
        'score': int(score),
        'revision_count': int(revision_count),
        'provider_used': provider_used,
        'data_source': data_source
    })


def set_workflow_error(workflow_id: str, error: str) -> None:
    """Set workflow error state."""
    update_workflow(workflow_id, {
        'status': 'failed',
        'current_step': 'Error',
        'error': error
    })
