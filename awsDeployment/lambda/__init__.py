# AWS Lambda handlers for SWOT Agent
#
# API Handlers:
#   - analyze.py      : POST /analyze - Starts workflow
#   - status.py       : GET /workflow/{id}/status - Returns status
#   - result.py       : GET /workflow/{id}/result - Returns result
#   - stocksSearch.py : GET /api/stocks/search - Stock autocomplete
#
# Step Functions Handlers:
#   - researcher.py   : Gathers data from external APIs
#   - analyzer.py     : Generates SWOT analysis
#   - critic.py       : Evaluates quality and assigns score
#   - complete.py     : Saves final result
#
# Helpers:
#   - secretsHelper.py : Fetches secrets from AWS Secrets Manager
