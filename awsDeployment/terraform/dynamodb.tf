# DynamoDB tables for workflow state and caching

resource "aws_dynamodb_table" "workflows" {
  name         = "swot-workflows"
  billing_mode = "PAY_PER_REQUEST"  # On-demand pricing (free tier friendly)
  hash_key     = "workflow_id"

  attribute {
    name = "workflow_id"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = {
    Name = "swot-workflows"
  }
}

resource "aws_dynamodb_table" "cache" {
  name         = "swot-cache"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "ticker"

  attribute {
    name = "ticker"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = {
    Name = "swot-cache"
  }
}

output "workflows_table_name" {
  value = aws_dynamodb_table.workflows.name
}

output "cache_table_name" {
  value = aws_dynamodb_table.cache.name
}
