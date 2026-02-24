#!/bin/bash
# Teardown all AWS resources (rollback)
# Usage: ./teardown.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== SWOT Agent AWS Teardown ==="
echo "WARNING: This will delete ALL AWS resources for this project!"
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

# Empty S3 bucket first (required before deletion)
echo "Emptying S3 bucket..."
aws s3 rm s3://swot-agent-frontend-691210491730/ --recursive 2>/dev/null || true

# Terraform destroy
echo "Running Terraform destroy..."
cd "$PROJECT_ROOT/terraform"
terraform destroy -auto-approve

echo "=== Teardown Complete ==="
