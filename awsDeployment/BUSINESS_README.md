# AWS Serverless Deployment - Instant SWOT Agent

## Executive Summary

This AWS deployment demonstrates the migration of a production AI application from a managed platform (HuggingFace Spaces) to **enterprise-grade serverless infrastructure**. The architecture showcases the skills organizations need when deploying AI systems at scale: event-driven compute, managed workflow orchestration, infrastructure-as-code, and cost-optimized resource allocation.

The multi-agent SWOT analysis workflow—originally built with LangGraph—has been re-architected using AWS Step Functions, preserving the self-correcting feedback loop while gaining the observability, scalability, and operational maturity that enterprise deployments require.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND LAYER                                  │
│  ┌─────────────┐         ┌─────────────┐                                    │
│  │  CloudFront │ ──────→ │     S3      │  React SPA                         │
│  │    (CDN)    │         │  (Static)   │                                    │
│  └──────┬──────┘         └─────────────┘                                    │
└─────────┼───────────────────────────────────────────────────────────────────┘
          │ HTTPS
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                               API LAYER                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      API Gateway (HTTP API v2)                       │    │
│  │  POST /analyze  │  GET /status/{id}  │  GET /result/{id}  │  GET /search │
│  └────────┬────────────────┬───────────────────┬─────────────────┬─────┘    │
└───────────┼────────────────┼───────────────────┼─────────────────┼──────────┘
            ▼                ▼                   ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            COMPUTE LAYER (Lambda)                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Analyze    │  │    Status    │  │    Result    │  │ StocksSearch │     │
│  │  (Trigger)   │  │   (Query)    │  │   (Query)    │  │   (Query)    │     │
│  └──────┬───────┘  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────┼───────────────────────────────────────────────────────────────────┘
          │ Start Execution
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      WORKFLOW ORCHESTRATION (Step Functions)                 │
│                                                                              │
│    ┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐    │
│    │ Researcher │ →  │  Analyzer  │ →  │   Critic   │ →  │  Complete  │    │
│    │  (Lambda)  │    │  (Lambda)  │    │  (Lambda)  │    │  (Lambda)  │    │
│    └────────────┘    └─────┬──────┘    └─────┬──────┘    └────────────┘    │
│                            │                 │                              │
│                            │    ┌────────────┘                              │
│                            │    │  Score < 6 AND Revisions < 3              │
│                            │    ▼                                           │
│                            │  ┌──────────────┐                              │
│                            └──│ Revision Loop│ (self-correction)            │
│                               └──────────────┘                              │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            DATA LAYER (DynamoDB)                             │
│  ┌─────────────────────────┐    ┌─────────────────────────┐                 │
│  │    swot-workflows       │    │      swot-cache         │                 │
│  │  (State + Activity Log) │    │  (Results by Ticker)    │                 │
│  │       TTL: 7 days       │    │      TTL: 24 hours      │                 │
│  └─────────────────────────┘    └─────────────────────────┘                 │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SECURITY & SECRETS                                  │
│  ┌─────────────────────────┐    ┌─────────────────────────┐                 │
│  │    Secrets Manager      │    │     IAM Roles           │                 │
│  │  (10 API Keys Stored)   │    │  (Least Privilege)      │                 │
│  └─────────────────────────┘    └─────────────────────────┘                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Problem Statement: Platform Migration Challenges

Moving AI applications from managed platforms to enterprise cloud infrastructure presents three core challenges:

1. **Workflow state management:** Agentic workflows require state persistence across multiple execution steps. In-memory state (suitable for single-server deployments) breaks in serverless architectures where each function invocation is stateless.

2. **Orchestration complexity:** Multi-agent systems with conditional branching and feedback loops require explicit coordination. Without proper orchestration, retry logic, error handling, and state transitions become error-prone and hard to debug.

3. **Cost-performance trade-offs:** Enterprise deployments must balance compute costs against latency and availability requirements—especially for AI workloads with unpredictable execution times.

---

## Solution: Serverless Multi-Agent Architecture

### AWS Step Functions as Workflow Engine

The LangGraph workflow has been translated to AWS Step Functions, preserving the agentic self-correction pattern:

| LangGraph Concept | AWS Step Functions Equivalent |
|-------------------|-------------------------------|
| Graph nodes | Lambda functions |
| Conditional edges | Choice states |
| State dict | JSON payload passed between states |
| `should_continue()` | Choice state with NumericGreaterThanEquals |

**The Self-Correction Loop:**
```
Analyzer → Critic → [Score < 6?] → Yes → Increment Revision → Analyzer
                  → [Score ≥ 6 OR Revisions ≥ 3?] → Yes → Complete
```

This pattern ensures outputs meet quality thresholds before delivery—the same guarantee as the original implementation, now with visual workflow debugging in the AWS console.

### Lambda Functions as Agent Executors

Each agent role runs as an independent Lambda function:

| Function | Role | Memory | Timeout |
|----------|------|--------|---------|
| `swot-agent-researcher` | Aggregates data from 6 MCP servers | 512MB | 120s |
| `swot-agent-analyzer` | Generates/revises SWOT drafts | 512MB | 60s |
| `swot-agent-critic` | Scores output quality (hybrid evaluation) | 512MB | 60s |
| `swot-agent-complete` | Persists final results | 256MB | 30s |

Lambda functions import the original `src/nodes/` code, ensuring behavior parity while adding AWS-specific concerns (secrets injection, DynamoDB persistence).

### DynamoDB for Distributed State

The workflow state that LangGraph managed in-memory is now persisted in DynamoDB:

- **Workflow table:** Tracks status, activity log, MCP data status, revision count, and final results
- **Cache table:** Stores completed analyses by ticker with 24-hour TTL for instant repeat queries
- **TTL-based cleanup:** Automatic expiration eliminates manual data management

---

## Enterprise Deployment Patterns Demonstrated

### Event-Driven Architecture
- API Gateway triggers Lambda on-demand
- Step Functions coordinate asynchronous agent execution
- No idle compute costs between requests

### Infrastructure as Code
- Terraform modules define all resources declaratively
- Reproducible deployments across environments
- Version-controlled infrastructure changes

### Secrets Management
- API keys stored in AWS Secrets Manager (not environment variables)
- Runtime injection prevents secrets from appearing in Lambda configuration
- Supports key rotation without redeployment

### Observability
- CloudWatch Logs for all Lambda executions
- Step Functions execution history with visual timeline
- CloudWatch dashboard with key metrics (invocations, errors, duration)
- CloudWatch alarms for error rate and latency thresholds

### Cost Optimization
- Pay-per-use Lambda pricing (no idle costs)
- DynamoDB on-demand capacity (no capacity planning)
- CloudFront PriceClass_100 (US/Canada/Europe only)
- **Total estimated cost: $25-45 for 3 months** (well under $100 budget)

---

## Design Decisions & Trade-offs

| Challenge | Decision | Trade-off |
|-----------|----------|-----------|
| API type | HTTP API v2 (not REST API v1) | Cheaper and faster, but fewer features (no usage plans) |
| Compute | Lambda (not ECS/Fargate) | Serverless simplicity vs. container flexibility |
| Database | DynamoDB (not RDS) | No connection pooling needed, but less query flexibility |
| Workflow engine | Step Functions (not Lambda-only) | Visual debugging for recruiters, but vendor lock-in |
| State passing | Explicit field mapping in Step Functions | Verbose, but ensures no implicit state coupling |
| Caching | DynamoDB with TTL (not ElastiCache) | Simpler, cheaper for low-volume demo traffic |
| CDN | CloudFront with S3 origin | Standard pattern, but S3 bucket is currently public |

### Critical Bug Fix: Preserving Agentic Behavior

The initial Lambda wrappers inadvertently broke the revision loop. The original LangGraph workflow passed `critique_details` (a structured dict with scores and feedback) between Critic and Analyzer to detect revision mode. The Lambda wrappers initially only passed the `critique` string, causing the Analyzer to regenerate from scratch instead of revising.

**Fix:** Updated all state transitions to explicitly preserve `critique_details`, `metric_reference`, and `metric_reference_hash` through the revision loop—a lesson in how agentic patterns require careful state management when decomposed into microservices.

---

## Capabilities Demonstrated

- **Cloud architecture design** — Mapping application requirements to AWS services
- **Serverless compute** — Lambda function design, packaging, and configuration
- **Workflow orchestration** — Step Functions state machine definition (ASL)
- **Event-driven patterns** — API Gateway + Lambda integration
- **NoSQL data modeling** — DynamoDB table design with TTL and access patterns
- **Security best practices** — Secrets Manager, IAM roles with least privilege
- **Infrastructure as Code** — Terraform modules for reproducible deployment
- **Cost management** — Service selection optimized for budget constraints
- **Debugging distributed systems** — Tracing state through multi-step workflows
- **Migration strategy** — Adapting existing code to new infrastructure without rewrites

---

## Quick Reference

| Resource | Identifier |
|----------|------------|
| CloudFront URL | `https://d15w0kikwn6a78.cloudfront.net` |
| API Gateway | `https://irue5atrlj.execute-api.us-east-1.amazonaws.com/prod` |
| Region | `us-east-1` |
| Step Functions | `swot-agent-workflow` |
| DynamoDB Tables | `swot-workflows`, `swot-cache` |
| Secrets | `swot-agent-api-keys` |

---

## Related Documentation

- [Deployment Steps](./awsDeploymentSteps.md) — Detailed deployment checklist with decisions and lessons learned
- [Technical README](./README.md) — Architecture diagram and quick start
- [FAQ](./faq.md) — Common questions about AWS deployment
- [Root BUSINESS_README](../BUSINESS_README.md) — Overall project business context
