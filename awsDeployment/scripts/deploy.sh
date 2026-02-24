#!/bin/bash
# Deploy SWOT Agent to AWS
# Usage: ./deploy.sh [phase]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SWOT_ROOT="$(dirname "$PROJECT_ROOT")"

echo "=== SWOT Agent AWS Deployment ==="
echo "Project root: $SWOT_ROOT"
echo "AWS Deployment: $PROJECT_ROOT"

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI not installed"
    exit 1
fi

# Verify AWS credentials
echo "Verifying AWS credentials..."
aws sts get-caller-identity

PHASE=${1:-all}

case $PHASE in
    frontend)
        echo "=== Deploying Frontend ==="
        cd "$SWOT_ROOT/frontend"
        npm install
        npm run build
        aws s3 sync dist/ s3://swot-agent-frontend-691210491730/ --delete
        echo "Frontend deployed!"
        ;;

    terraform)
        echo "=== Running Terraform ==="
        cd "$PROJECT_ROOT/terraform"
        terraform init
        terraform plan
        terraform apply -auto-approve
        ;;

    lambda)
        echo "=== Packaging Lambda ==="
        "$SCRIPT_DIR/packageLambda.sh"
        ;;

    all)
        echo "=== Full Deployment ==="
        $0 terraform
        $0 lambda
        $0 frontend
        echo "=== Deployment Complete ==="
        ;;

    *)
        echo "Usage: $0 [frontend|terraform|lambda|all]"
        exit 1
        ;;
esac
