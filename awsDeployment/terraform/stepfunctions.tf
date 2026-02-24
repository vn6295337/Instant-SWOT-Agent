# Step Functions state machine for SWOT Agent workflow

# IAM role for Step Functions
resource "aws_iam_role" "stepfunctions_role" {
  name = "swot-agent-stepfunctions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
      }
    ]
  })
}

# Allow Step Functions to invoke Lambda
resource "aws_iam_role_policy" "stepfunctions_lambda" {
  name = "swot-agent-stepfunctions-lambda"
  role = aws_iam_role.stepfunctions_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "lambda:InvokeFunction"
        Resource = "arn:aws:lambda:${var.aws_region}:${var.account_id}:function:swot-agent-*"
      }
    ]
  })
}

# State machine (uses ASL definition from stepfunctions/workflow.asl.json)
# TODO: Create after Lambda functions are deployed

output "stepfunctions_role_arn" {
  value = aws_iam_role.stepfunctions_role.arn
}
