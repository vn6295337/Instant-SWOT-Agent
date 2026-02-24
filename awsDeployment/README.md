# AWS Deployment - Instant SWOT Agent

This directory contains AWS-specific deployment configurations for the SWOT Agent.

## Structure

```
awsDeployment/
├── README.md                 # This file
├── awsDeploymentSteps.md     # Step-by-step deployment checklist
├── faq.md                    # Frequently asked questions
├── lambda/                   # Lambda function handlers
│   ├── analyze.py            # POST /analyze
│   ├── status.py             # GET /workflow/{id}/status
│   ├── result.py             # GET /workflow/{id}/result
│   └── stocksSearch.py       # GET /api/stocks/search
├── stepFunctions/            # Step Functions definitions
│   └── workflow.asl.json     # State machine (ASL)
├── dynamoDb/                 # DynamoDB adapters
│   └── workflowStoreDynamo.py
├── terraform/                # Infrastructure as Code
│   ├── main.tf               # Provider & variables
│   ├── s3.tf                 # Frontend hosting
│   ├── dynamodb.tf           # Database tables
│   ├── lambda.tf             # Lambda functions & IAM
│   ├── api_gateway.tf        # REST API
│   ├── stepfunctions.tf      # Workflow orchestration
│   ├── secrets.tf            # Secrets Manager
│   └── cloudwatch.tf         # Monitoring & budgets
└── scripts/                  # Deployment automation
    ├── deploy.sh             # Main deployment script
    ├── packageLambda.sh      # Lambda packaging
    └── tearDown.sh           # Resource cleanup
```

## Quick Start

```bash
# 1. Configure AWS CLI
aws configure

# 2. Initialize Terraform
cd terraform && terraform init

# 3. Deploy infrastructure
terraform apply

# 4. Deploy application
cd ../scripts && ./deploy.sh all
```

## Architecture

```
CloudFront → S3 (Frontend)
     ↓
API Gateway → Lambda (Handlers)
     ↓
Step Functions (Workflow: Researcher → Analyzer → Critic)
     ↓
DynamoDB (State & Cache)
```

## Cost Estimate

~$25-45 total for 3 months (within $100 budget)

## Related Docs

- [Deployment Steps](./awsDeploymentSteps.md) - Detailed checklist
- [FAQ](./faq.md) - Common questions answered
