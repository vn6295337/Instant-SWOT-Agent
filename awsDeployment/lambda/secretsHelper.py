# Helper to fetch secrets from AWS Secrets Manager

import boto3
import json
import os
from functools import lru_cache

@lru_cache(maxsize=1)
def get_secrets() -> dict:
    """Fetch API keys from Secrets Manager (cached)."""
    secrets_arn = os.environ.get('SECRETS_ARN')
    if not secrets_arn:
        print("Warning: SECRETS_ARN not set, using environment variables")
        return {}

    client = boto3.client('secretsmanager', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

    try:
        response = client.get_secret_value(SecretId=secrets_arn)
        secret_string = response.get('SecretString', '{}')
        return json.loads(secret_string)
    except Exception as e:
        print(f"Error fetching secrets: {e}")
        return {}


def get_secret(key: str, default: str = None) -> str:
    """Get a specific secret value."""
    secrets = get_secrets()
    return secrets.get(key, os.environ.get(key, default))


def inject_secrets_to_env():
    """Inject secrets into environment variables for existing code compatibility."""
    secrets = get_secrets()
    for key, value in secrets.items():
        if key not in os.environ:
            os.environ[key] = value
