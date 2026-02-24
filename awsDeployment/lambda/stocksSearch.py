# Lambda handler for GET /api/stocks/search endpoint
# Stock ticker autocomplete

import json
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def lambda_handler(event, context):
    """
    Searches stock tickers.

    Input: query parameter q (e.g., "App")
    Output: [{ "ticker": "AAPL", "name": "Apple Inc." }, ...]
    """
    try:
        # Get query parameter
        query_params = event.get('queryStringParameters', {}) or {}
        query = query_params.get('q', '').strip()

        if not query or len(query) < 1:
            return {
                'statusCode': 200,
                'headers': cors_headers(),
                'body': json.dumps([])
            }

        # Try to use the existing stock listings module
        try:
            from src.stock_listings import search_stocks, get_us_stock_listings
            stocks = get_us_stock_listings()
            results = search_stocks(query, stocks, max_results=20)
            # Convert to expected format (original uses 'symbol', frontend expects 'ticker')
            formatted = [{'ticker': r['symbol'], 'name': r['name']} for r in results]
        except Exception as e:
            print(f"Using fallback search due to: {e}")
            # Fallback to basic hardcoded list for common stocks
            formatted = search_fallback(query)

        return {
            'statusCode': 200,
            'headers': cors_headers(),
            'body': json.dumps(formatted)
        }

    except Exception as e:
        print(f"Error in stocks search handler: {e}")
        return {
            'statusCode': 500,
            'headers': cors_headers(),
            'body': json.dumps({'error': str(e)})
        }


def search_fallback(query: str) -> list:
    """Fallback search with popular stocks."""
    POPULAR_STOCKS = [
        {'ticker': 'AAPL', 'name': 'Apple Inc.'},
        {'ticker': 'MSFT', 'name': 'Microsoft Corporation'},
        {'ticker': 'GOOGL', 'name': 'Alphabet Inc.'},
        {'ticker': 'AMZN', 'name': 'Amazon.com Inc.'},
        {'ticker': 'META', 'name': 'Meta Platforms Inc.'},
        {'ticker': 'TSLA', 'name': 'Tesla Inc.'},
        {'ticker': 'NVDA', 'name': 'NVIDIA Corporation'},
        {'ticker': 'JPM', 'name': 'JPMorgan Chase & Co.'},
        {'ticker': 'V', 'name': 'Visa Inc.'},
        {'ticker': 'JNJ', 'name': 'Johnson & Johnson'},
        {'ticker': 'WMT', 'name': 'Walmart Inc.'},
        {'ticker': 'PG', 'name': 'Procter & Gamble Co.'},
        {'ticker': 'MA', 'name': 'Mastercard Inc.'},
        {'ticker': 'UNH', 'name': 'UnitedHealth Group Inc.'},
        {'ticker': 'HD', 'name': 'Home Depot Inc.'},
        {'ticker': 'DIS', 'name': 'Walt Disney Co.'},
        {'ticker': 'BAC', 'name': 'Bank of America Corp.'},
        {'ticker': 'NFLX', 'name': 'Netflix Inc.'},
        {'ticker': 'ADBE', 'name': 'Adobe Inc.'},
        {'ticker': 'CRM', 'name': 'Salesforce Inc.'},
        {'ticker': 'INTC', 'name': 'Intel Corporation'},
        {'ticker': 'AMD', 'name': 'Advanced Micro Devices Inc.'},
        {'ticker': 'CSCO', 'name': 'Cisco Systems Inc.'},
        {'ticker': 'ORCL', 'name': 'Oracle Corporation'},
        {'ticker': 'IBM', 'name': 'IBM Corporation'},
        {'ticker': 'UBER', 'name': 'Uber Technologies Inc.'},
        {'ticker': 'ABNB', 'name': 'Airbnb Inc.'},
        {'ticker': 'SQ', 'name': 'Block Inc.'},
        {'ticker': 'SHOP', 'name': 'Shopify Inc.'},
        {'ticker': 'SPOT', 'name': 'Spotify Technology S.A.'},
    ]

    query_lower = query.lower()
    results = []

    for stock in POPULAR_STOCKS:
        if (query_lower in stock['ticker'].lower() or
            query_lower in stock['name'].lower()):
            results.append(stock)
            if len(results) >= 10:
                break

    return results


def cors_headers():
    """Return CORS headers."""
    return {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
    }
