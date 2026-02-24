# AWS Deployment Steps - Instant SWOT Agent

## Overview
Deploy the SWOT Agent to AWS using serverless architecture.
- **Budget**: $100 over 3 months
- **Region**: us-east-1
- **Architecture**: Lambda + Step Functions + API Gateway + S3

---

## Phase 1: Foundation Setup

- [x] 1. Verify AWS CLI is configured and working
  > **Notes:** Ran `aws sts get-caller-identity` to confirm credentials.
  > Account: 691210491730, User: vn6295337

- [x] 2. Create an S3 bucket for Terraform state (optional, for state management)
  > **Notes:** Created `swot-agent-tfstate-691210491730`
  > **Decision:** Include account ID in bucket name for global uniqueness.
  > **Tradeoff:** Not strictly needed for CLI deployment, but good practice for future IaC adoption.

- [x] 3. Create ECR repository for Docker images
  > **Notes:** Created `swot-agent` repository.
  > **Decision:** Kept for future container deployments even though we used zip packaging.
  > **Exclusion:** Didn't push any images yet - using Lambda zip deployment instead.

- [x] 4. Set up Secrets Manager with API keys (GROQ, GEMINI, TAVILY, etc.)
  > **Notes:** Created `swot-agent-api-keys` with 10 API keys from .env file.
  > **Decision:** Single secret with all keys vs individual secrets per key.
  > **Tradeoff:** Simpler management, but less granular access control. For learning purposes, this is acceptable.

---

## Phase 2: Frontend Deployment

- [x] 5. Build the React frontend (`npm run build`) - using existing build
  > **Notes:** Reused existing `frontend/dist/` build from prior development.
  > **Decision:** Skip rebuild to save time.
  > **Tradeoff:** May need rebuild later when updating API base URL.

- [x] 6. Create S3 bucket for static website hosting
  > **Notes:** Created `swot-agent-frontend-691210491730`
  > **Decision:** Named with account ID for uniqueness.

- [x] 7. Upload frontend build files to S3
  > **Notes:** Used `aws s3 sync` to upload 4 files (~408KB total).
  > **Inclusion:** index.html, vite.svg, assets/index-*.js, assets/index-*.css

- [x] 8. Configure S3 bucket policy for public read access
  > **Notes:** Disabled Block Public Access, added public read policy.
  > **Decision:** Public bucket for simplicity.
  > **Tradeoff:** Less secure than CloudFront OAI/OAC. Marked for Phase 9 hardening.

- [x] 9. Create CloudFront distribution pointing to S3 (ID: E1CVZ9XDKUA980)
  > **Notes:** Distribution: d15w0kikwn6a78.cloudfront.net
  > **Decision:** Used PriceClass_100 (US/Canada/Europe only).
  > **Tradeoff:** Lower cost (~$0) vs global edge coverage. Acceptable for demo purposes.
  > **Inclusion:** Custom error response for SPA (404 → index.html).

- [x] 10. Test frontend URL in browser
  > **Notes:** Both URLs return HTTP 200.
  > - S3: http://swot-agent-frontend-691210491730.s3-website-us-east-1.amazonaws.com
  > - CloudFront: https://d15w0kikwn6a78.cloudfront.net

---

## Phase 3: Backend - Lambda Functions

- [x] 11. Create IAM role for Lambda execution (swot-agent-lambda-role)
  > **Notes:** Created role with trust policy for lambda.amazonaws.com
  > **Attached policies:**
  > - AWSLambdaBasicExecutionRole (CloudWatch logs)
  > - AmazonDynamoDBFullAccess (table read/write)
  > - SecretsManagerReadWrite (fetch API keys)
  > - Custom inline policy for Step Functions (start/describe executions)

- [x] 12. Package Python backend code with dependencies (53MB, uploaded to S3)
  > **Notes:** Initial package was 431MB, optimized to 212MB unzipped, 53MB zipped.
  > **Decision:** Upload to S3 because zip exceeds 50MB direct upload limit.
  > **Optimization:** Removed __pycache__, .dist-info, test folders, large .so files.
  > **Exclusion:** Did not include psycopg2 (PostgreSQL) - using DynamoDB instead.

- [x] 13. Create Lambda function for `/analyze` endpoint
  > **Notes:** swot-agent-analyze, 512MB memory, 60s timeout
  > **Decision:** Entry point that triggers Step Functions workflow.

- [x] 14. Create Lambda function for `/workflow/status` endpoint
  > **Notes:** swot-agent-status, 256MB memory, 30s timeout
  > **Decision:** Reads from DynamoDB + queries Step Functions execution status.

- [x] 15. Create Lambda function for `/workflow/result` endpoint
  > **Notes:** swot-agent-result, 256MB memory, 30s timeout
  > **Decision:** Returns final SWOT analysis from DynamoDB.

- [x] 16. Create Lambda function for `/stocks/search` endpoint
  > **Notes:** swot-agent-stocks-search, 256MB memory, 30s timeout
  > **Decision:** Included fallback list of 30 popular stocks if full search fails.
  > **Tradeoff:** Hardcoded list vs dynamic NASDAQ fetch. Simpler, works offline.

- [x] 17. Configure Lambda environment variables (from Secrets Manager)
  > **Notes:** Set SECRETS_ARN and AWS_REGION_NAME for all functions.
  > **Decision:** Fetch secrets at runtime vs baking into package.
  > **Tradeoff:** Slight cold start overhead, but more secure and easier to rotate keys.

- [x] 18. Test each Lambda function individually
  > **Notes:** All Lambda functions tested successfully:
  > - stocks-search: Returns AAPL, MSFT etc. ✅
  > - analyze: Starts workflow, returns workflow_id ✅
  > - status: Returns workflow status with activity log ✅
  > - result: Returns completed SWOT analysis ✅
  > - researcher, analyzer, critic, complete: Tested via Step Functions ✅

---

## Phase 4: API Gateway

- [x] 19. Create REST API in API Gateway (ID: irue5atrlj)
  > **Notes:** Created HTTP API (v2), not REST API (v1).
  > **Decision:** HTTP API is cheaper, faster, and sufficient for this use case.
  > **Tradeoff:** Fewer features (no usage plans, request validation) vs cost savings.

- [x] 20. Create resources: `/analyze`, `/workflow/{id}/status`, `/workflow/{id}/result`, `/api/stocks/search`
  > **Notes:** Created 4 routes with Lambda integrations.
  > **Decision:** Path parameter `{id}` for workflow identification.

- [x] 21. Create methods (POST/GET) and link to Lambda functions
  > **Notes:** POST /analyze, GET for others. Added Lambda invoke permissions.
  > **Inclusion:** Payload format version 2.0 for simpler event structure.

- [x] 22. Enable CORS for frontend access
  > **Notes:** Configured at API level: AllowOrigins=*, AllowMethods=GET,POST,OPTIONS
  > **Decision:** Allow all origins for development flexibility.
  > **Tradeoff:** Less secure; should restrict to CloudFront domain in production.

- [x] 23. Deploy API to a stage (e.g., `prod`)
  > **Notes:** Created `prod` stage with auto-deploy enabled.
  > **Decision:** Auto-deploy for faster iteration during development.

- [x] 24. Note the API Gateway invoke URL: https://irue5atrlj.execute-api.us-east-1.amazonaws.com/prod
  > **Notes:** Base URL for all API calls. Frontend needs to be configured with this.

---

## Phase 5: Step Functions (Agentic Workflow)

- [x] 25. Create IAM role for Step Functions execution
  > **Notes:** swot-agent-stepfunctions-role with lambda:InvokeFunction permission.
  > **Decision:** Scoped to swot-agent-* functions only (least privilege).

- [x] 26. Define state machine JSON (Researcher → Analyzer → Critic → conditional loop)
  > **Notes:** workflow.asl.json with 6 states: Researcher, Analyzer, Critic, CheckScore, IncrementRevision, Complete.
  > **Decision:** Used Choice state for score-based branching (score >= 7 OR revisions >= 3).
  > **Tradeoff:** Step Functions visual debugging vs keeping workflow in code (LangGraph).
  > **Key insight:** This is the "agentic" showcase - multi-agent with self-correction.

- [x] 27. Create Step Functions state machine (swot-agent-workflow)
  > **Notes:** STANDARD type, not EXPRESS.
  > **Decision:** STANDARD supports long-running executions (up to 1 year).
  > **Tradeoff:** More expensive than EXPRESS, but needed for >5 min analyses.
  > **Created 4 additional Lambda functions:** researcher, analyzer, critic, complete.

- [x] 28. Update `/analyze` Lambda to trigger Step Functions instead of in-memory workflow
  > **Notes:** Handler triggers sfn_client.start_execution() successfully.
  > **Tested:** Workflow starts and returns workflow_id. ✅

- [x] 29. Update `/workflow/status` Lambda to read Step Functions execution status
  > **Notes:** Handler queries DynamoDB for workflow state.
  > **Tested:** Returns status, activity_log, mcp_status, llm_status. ✅

- [x] 30. Test full workflow execution
  > **Tested:** Microsoft (MSFT) analysis completed successfully!
  > - Duration: ~5 minutes
  > - Score: 5/10 (after 3 revisions)
  > - Provider: groq:llama-3.1-8b-instant
  > - All 6 MCP data sources fetched ✅

---

## Phase 6: Database (DynamoDB)

- [x] 31. Create DynamoDB table for workflow state (`swot-workflows`)
  > **Notes:** Partition key: workflow_id (String).
  > **Decision:** PAY_PER_REQUEST billing mode.
  > **Tradeoff:** No capacity planning needed, but costs scale with usage. Ideal for unpredictable demo traffic.

- [x] 32. Create DynamoDB table for analysis cache (`swot-cache`)
  > **Notes:** Partition key: ticker (String).
  > **Decision:** Cache by ticker symbol for quick lookups.
  > **Exclusion:** No sort key - one cached result per ticker.

- [x] 33. Update Lambda functions to use DynamoDB instead of in-memory storage
  > **Notes:** workflowStoreDynamo.py implemented and working:
  > - create_workflow: Creates workflow entry with TTL ✅
  > - get_workflow: Retrieves workflow state ✅
  > - update_workflow: Updates status, score, report ✅
  > - add_activity_log: Appends to activity log list ✅
  > - cache_analysis: Caches completed results by ticker ✅

- [x] 34. Configure TTL on cache table (24 hours)
  > **Notes:** TTL attribute: expires_at (Unix timestamp).
  > **Decision:** 24-hour cache matches original Supabase implementation.
  > **Tradeoff:** Automatic cleanup vs potential stale data re-fetch.
  > **Also enabled on workflows table** for automatic cleanup of old workflows.

---

## Phase 7: Connect Frontend to Backend

- [x] 35. Update frontend API base URL to API Gateway URL
  > **Notes:** Created `frontend/.env.production` with:
  > ```
  > VITE_API_URL=https://irue5atrlj.execute-api.us-east-1.amazonaws.com/prod
  > ```

- [x] 36. Rebuild and redeploy frontend to S3
  > **Notes:** `npm run build` + `aws s3 sync dist/ s3://bucket/`
  > **Built:** index.html (0.46KB), index.js (344KB), index.css (67KB)

- [x] 37. Invalidate CloudFront cache
  > **Notes:** Invalidation ID: IASEF1N6ACFNTW7M8S47HUVYJI
  > **Command:** `aws cloudfront create-invalidation --distribution-id E1CVZ9XDKUA980 --paths "/*"`

- [ ] 38. Test end-to-end flow from browser
  > **URL:** https://d15w0kikwn6a78.cloudfront.net
  > **Test:** search stock → start analysis → poll status → view result

---

## Phase 8: Monitoring & Alerts

- [x] 39. Create CloudWatch dashboard for Lambda metrics
  > **Notes:** Dashboard: swot-agent-dashboard with 4 widgets.
  > **Widgets:** Lambda Invocations, Lambda Errors, Lambda Duration, API Gateway Requests.
  > **Decision:** Essential metrics only, can extend later.

- [x] 40. Set up CloudWatch alarms (error rate > 5%, latency > 30s)
  > **Notes:** Created 2 alarms: swot-agent-analyze-errors, swot-agent-high-latency.
  > **Decision:** No SNS topic/email notifications configured.
  > **Tradeoff:** Saves complexity; must check console manually for alerts.

- [ ] 41. Enable X-Ray tracing for Lambda functions (optional)
  > **Notes:** Deferred - adds cost and complexity.
  > **Decision:** Skip for now, enable if debugging distributed issues.

- [x] 42. Review CloudWatch logs for debugging (auto-enabled)
  > **Notes:** Lambda automatically creates log groups /aws/lambda/swot-agent-*.
  > **Inclusion:** print() statements in handlers write to CloudWatch Logs.

---

## Phase 9: Security Hardening

- [ ] 43. Restrict S3 bucket access to CloudFront only (OAI/OAC)
  > **Notes:** Currently public. Should create Origin Access Control (OAC).
  > **Priority:** Medium - not critical for demo, but recommended for production.

- [ ] 44. Add API Gateway usage plan and API key (optional)
  > **Notes:** Would prevent abuse. HTTP API doesn't support usage plans directly.
  > **Alternative:** Could add Lambda authorizer or WAF.

- [ ] 45. Enable WAF on API Gateway (optional)
  > **Notes:** AWS WAF adds ~$5/month + per-request costs.
  > **Decision:** Skip for budget reasons.

- [ ] 46. Review IAM policies for least privilege
  > **Notes:** Current policies are broad (FullAccess). Should scope down.
  > **Priority:** Low for learning project, high for production.

---

## Phase 10: Cost Monitoring

- [ ] 47. Set up AWS Budgets alert at $30 (via Console - needs Billing permission)
  > **Notes:** CLI command failed - requires budgets:ModifyBudget permission.
  > **Workaround:** Set up manually via AWS Console → Billing → Budgets.

- [ ] 48. Set up AWS Budgets alert at $70 (via Console)
  > **Notes:** Second threshold at 70% of $100 budget.

- [ ] 49. Review Cost Explorer weekly
  > **Notes:** Check Console → Billing → Cost Explorer for spend breakdown.

- [ ] 50. Document monthly spend breakdown
  > **Notes:** Track which services consume most budget (expected: Lambda, API Gateway minimal; CloudFront ~$0; DynamoDB minimal).

---

## Phase 11: Optional Enhancements

- [ ] 51. Add Bedrock integration (replace Groq with Claude Haiku)
  > **Notes:** Would showcase AWS AI services. Adds ~$5-10/month.
  > **Decision:** Deferred - Groq free tier sufficient for demo.

- [ ] 52. Add Cognito for user authentication
  > **Notes:** Would add login/signup flow. Significant frontend changes needed.
  > **Decision:** Deferred - not required for portfolio demo.

- [ ] 53. Add custom domain with Route 53
  > **Notes:** Would give professional URL like swot.yourdomain.com.
  > **Cost:** ~$12/year for domain + $0.50/month for hosted zone.

- [ ] 54. Set up CI/CD with CodePipeline
  > **Notes:** Auto-deploy on git push. Would be impressive for portfolio.
  > **Decision:** Deferred - manual deployment sufficient for now.

---

## Quick Reference

| Resource | Name/ID | Status |
|----------|---------|--------|
| S3 (frontend) | `swot-agent-frontend-691210491730` | ✅ Live |
| S3 (terraform state) | `swot-agent-tfstate-691210491730` | ✅ Created |
| ECR | `swot-agent` | ✅ Created (unused) |
| Secrets Manager | `swot-agent-api-keys` | ✅ 10 keys stored |
| CloudFront | `d15w0kikwn6a78.cloudfront.net` (E1CVZ9XDKUA980) | ✅ Deployed |
| Lambda (API) | `swot-agent-{analyze,status,result,stocks-search}` | ✅ Created |
| Lambda (Agents) | `swot-agent-{researcher,analyzer,critic,complete}` | ✅ Created |
| API Gateway | `irue5atrlj` | ✅ Deployed (prod) |
| Step Functions | `swot-agent-workflow` | ✅ Created |
| DynamoDB | `swot-workflows`, `swot-cache` | ✅ Created |
| IAM Roles | `swot-agent-lambda-role`, `swot-agent-stepfunctions-role` | ✅ Created |
| CloudWatch | Dashboard + 2 alarms | ✅ Configured |

---

## Key Decisions Summary

| Decision | Choice Made | Why |
|----------|-------------|-----|
| Region | us-east-1 | Full service availability, Bedrock access |
| Compute | Lambda (not ECS/Fargate) | Serverless, pay-per-use, lower cost |
| API | HTTP API v2 (not REST) | Cheaper, faster, simpler |
| Database | DynamoDB (not RDS) | Serverless, no connection pooling, TTL support |
| Workflow | Step Functions (not just Lambda) | Visual debugging, recruiter demo appeal |
| State | Replaced in-memory with DynamoDB | Persistence across Lambda invocations |
| Secrets | Secrets Manager (not env vars) | Secure, rotatable, auditable |
| Frontend hosting | S3 + CloudFront | Standard pattern, HTTPS, CDN caching |

---

## Rollback Plan

To tear down all resources (run in order):

```bash
# 1. CloudFront (takes ~15 min to disable)
aws cloudfront update-distribution --id E1CVZ9XDKUA980 --distribution-config file://disable.json
aws cloudfront delete-distribution --id E1CVZ9XDKUA980 --if-match <ETAG>

# 2. S3 buckets
aws s3 rm s3://swot-agent-frontend-691210491730 --recursive
aws s3 rb s3://swot-agent-frontend-691210491730
aws s3 rm s3://swot-agent-tfstate-691210491730 --recursive
aws s3 rb s3://swot-agent-tfstate-691210491730

# 3. Lambda functions
for f in analyze status result stocks-search researcher analyzer critic complete; do
  aws lambda delete-function --function-name swot-agent-$f
done

# 4. API Gateway
aws apigatewayv2 delete-api --api-id irue5atrlj

# 5. Step Functions
aws stepfunctions delete-state-machine --state-machine-arn arn:aws:states:us-east-1:691210491730:stateMachine:swot-agent-workflow

# 6. DynamoDB
aws dynamodb delete-table --table-name swot-workflows
aws dynamodb delete-table --table-name swot-cache

# 7. IAM roles (detach policies first)
aws iam delete-role --role-name swot-agent-lambda-role
aws iam delete-role --role-name swot-agent-stepfunctions-role

# 8. Secrets Manager
aws secretsmanager delete-secret --secret-id swot-agent-api-keys --force-delete-without-recovery

# 9. ECR
aws ecr delete-repository --repository-name swot-agent --force

# 10. CloudWatch (optional - logs auto-expire)
aws cloudwatch delete-dashboard --dashboard-name swot-agent-dashboard
aws cloudwatch delete-alarms --alarm-names swot-agent-analyze-errors swot-agent-high-latency
```
