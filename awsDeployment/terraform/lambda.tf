# Lambda functions for SWOT Agent

# IAM role for Lambda execution
resource "aws_iam_role" "lambda_role" {
  name = "swot-agent-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Lambda basic execution policy
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# DynamoDB access policy
resource "aws_iam_role_policy" "lambda_dynamodb" {
  name = "swot-agent-dynamodb-access"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query"
        ]
        Resource = [
          aws_dynamodb_table.workflows.arn,
          aws_dynamodb_table.cache.arn
        ]
      }
    ]
  })
}

# Secrets Manager access policy
resource "aws_iam_role_policy" "lambda_secrets" {
  name = "swot-agent-secrets-access"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:${var.account_id}:secret:swot-agent-*"
      }
    ]
  })
}

# Step Functions invoke policy
resource "aws_iam_role_policy" "lambda_stepfunctions" {
  name = "swot-agent-stepfunctions-access"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "states:StartExecution",
          "states:DescribeExecution"
        ]
        Resource = "*"
      }
    ]
  })
}

# Lambda functions (placeholder - will use zip deployment)
# TODO: Add actual Lambda function resources after packaging

output "lambda_role_arn" {
  value = aws_iam_role.lambda_role.arn
}
