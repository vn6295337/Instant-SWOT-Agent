# Secrets Manager for API keys

resource "aws_secretsmanager_secret" "api_keys" {
  name        = "swot-agent-api-keys"
  description = "API keys for SWOT Agent (Groq, Gemini, Tavily, etc.)"
}

# Note: Secret values must be set manually or via CLI:
# aws secretsmanager put-secret-value --secret-id swot-agent-api-keys --secret-string '{"GROQ_API_KEY":"...","GEMINI_API_KEY":"..."}'

output "secrets_arn" {
  value = aws_secretsmanager_secret.api_keys.arn
}
