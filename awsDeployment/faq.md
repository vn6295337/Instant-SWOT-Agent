# AWS Deployment FAQ

Frequently asked questions about deploying Instant SWOT Agent to AWS.

---

## General

### Q1: Can I manage my AWS account from Claude Code or the terminal?
**Yes.** You use the AWS CLI (Command Line Interface) to interact with AWS services directly from the terminal. Install it with:
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
unzip -q /tmp/awscliv2.zip -d /tmp
sudo /tmp/aws/install
```
Then configure with `aws configure` using your Access Key ID and Secret Access Key.

---

## Region Selection

### Q2: Should I use us-east-1 even though I'm operating from India? Won't there be latency issues?
**For development**: Latency doesn't matter much (~200-300ms extra for CLI commands).

**For the deployed app**:
- `ap-south-1` (Mumbai) offers ~10-30ms latency from India
- `us-east-1` offers ~200-250ms latency from India

**Recommendation**: Mumbai works fine for your use case. The ~200ms latency to US is acceptable for recruiter demos.

### Q3: Are all the services available in us-east-1 also available in Mumbai and Singapore?
**Not all, but all you need are available.**

| Service | us-east-1 | ap-south-1 (Mumbai) |
|---------|-----------|---------------------|
| Lambda | ✅ | ✅ |
| Step Functions | ✅ | ✅ |
| API Gateway | ✅ | ✅ |
| DynamoDB | ✅ | ✅ |
| S3 | ✅ | ✅ |
| CloudFront | ✅ | ✅ (Global) |
| Bedrock | ✅ All models | ⚠️ Limited models |

**Key difference**: Bedrock Claude 3 Opus is only in us-east-1. Claude Haiku and Sonnet are available in Mumbai.

---

## Deployment Approach

### Q4: Is this a brand new development, or are we customizing the existing code for AWS?
**Hybrid approach - adapting existing code to AWS infrastructure.**

| Component | Approach |
|-----------|----------|
| Frontend | Deploy as-is to S3 (no changes) |
| Backend logic | Keep Python code, wrap in Lambda |
| Workflow | Convert LangGraph → Step Functions |
| State | Replace in-memory → DynamoDB |
| Config | Environment vars → Secrets Manager |

**Code changes needed**: ~200-300 lines (Lambda handlers, DynamoDB adapter)
**Unchanged code**: ~90% of existing codebase

### Q5: For the reusable code we already have, will you port it to the awsDeployment directory, create a copy there, or reference the original code?
**Reference the original code - no duplication.**

```
~/instantSWOTAgent/
├── src/                    # Existing code (UNCHANGED)
├── frontend/               # Existing React app (UNCHANGED)
└── awsDeployment/          # NEW - AWS-specific only
    ├── lambda/             # Lambda wrappers (import from src/)
    ├── stepfunctions/      # State machine definition
    ├── dynamodb/           # DynamoDB adapter
    └── terraform/          # Infrastructure as Code
```

Lambda handlers import existing code:
```python
from src.nodes.researcher import ResearcherNode
from src.nodes.analyzer import AnalyzerNode
```

### Q6: So the existing code remains untouched, and both the HuggingFace Spaces frontend and the AWS deployment will coexist?
**Yes, both deployments will coexist.**

| Environment | URL | Purpose |
|-------------|-----|---------|
| HuggingFace | Existing URL | Free demo, already live |
| AWS | CloudFront URL | Portfolio showcase, recruiter demos |

**Benefits**:
- No risk - HF deployment keeps working
- A/B comparison - Show recruiters both deployments
- Talking point - "I migrated from PaaS to AWS serverless"
- Fallback - If AWS credits run out, HF still works

---

## Cost & Budget

### Q7: Is deploying this project on AWS feasible with $100 in credits over 3 months?
**Yes.** Estimated costs for SWOT Agent on AWS:

| Service | Monthly | 3-Month Total |
|---------|---------|---------------|
| Lambda | ~Free | $0 |
| Step Functions | ~Free | $0 |
| API Gateway | ~Free | $0 |
| S3 + CloudFront | $1 | $3 |
| DynamoDB | ~Free | $0 |
| Bedrock (optional) | $5-10 | $15-30 |
| Secrets Manager | $1 | $3 |
| CloudWatch | $2 | $6 |

**Total: $25-45 for 3 months** - well under $100 budget.

---

## Project Comparison

### Q8: Which project is more suitable for showcasing my AWS skills - the RAG Document Assistant or the SWOT Agent?
**SWOT Agent wins** for AWS learning and recruiter demos.

| Criteria | RAG Assistant | SWOT Agent |
|----------|---------------|------------|
| Local ML Models | Yes (needs 2-4GB RAM) | None (external APIs) |
| Lambda compatible | ❌ No | ✅ Yes |
| Agentic patterns | Basic pipeline | Multi-agent + self-correction |
| Monthly cost | $15-20+ | $0-10 |
| Recruiter appeal | Good | Better (visual workflow) |

SWOT Agent's multi-agent architecture with self-correcting feedback loop is more impressive for demonstrating agentic AI skills.

---

*Last updated: 2024*
