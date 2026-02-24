# API Gateway for SWOT Agent REST API

resource "aws_apigatewayv2_api" "api" {
  name          = "swot-agent-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]  # Restrict in production
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization"]
    max_age       = 300
  }
}

resource "aws_apigatewayv2_stage" "prod" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "prod"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      responseLength = "$context.responseLength"
    })
  }
}

resource "aws_cloudwatch_log_group" "api_logs" {
  name              = "/aws/apigateway/swot-agent-api"
  retention_in_days = 7
}

# TODO: Add routes and Lambda integrations after Lambda functions are created

output "api_endpoint" {
  value = aws_apigatewayv2_stage.prod.invoke_url
}
