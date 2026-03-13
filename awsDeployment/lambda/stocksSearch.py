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
                'body': json.dumps({'query': '', 'results': []})
            }

        # Try to use the existing stock listings module
        try:
            from src.stock_listings import search_stocks, get_us_stock_listings
            stocks = get_us_stock_listings()
            results = search_stocks(query, stocks, max_results=20)
            # Convert to frontend expected format
            formatted = [{
                'symbol': r['symbol'],
                'name': r['name'],
                'exchange': r.get('exchange', 'NASDAQ'),
                'match_type': r.get('match_type', 'partial')
            } for r in results]
        except Exception as e:
            print(f"Using fallback search due to: {e}")
            # Fallback to basic hardcoded list for common stocks
            formatted = search_fallback(query)

        return {
            'statusCode': 200,
            'headers': cors_headers(),
            'body': json.dumps({'query': query, 'results': formatted})
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
        {'symbol': 'AAPL', 'name': 'Apple Inc.', 'exchange': 'NASDAQ'},
        {'symbol': 'MSFT', 'name': 'Microsoft Corporation', 'exchange': 'NASDAQ'},
        {'symbol': 'GOOGL', 'name': 'Alphabet Inc.', 'exchange': 'NASDAQ'},
        {'symbol': 'AMZN', 'name': 'Amazon.com Inc.', 'exchange': 'NASDAQ'},
        {'symbol': 'META', 'name': 'Meta Platforms Inc.', 'exchange': 'NASDAQ'},
        {'symbol': 'TSLA', 'name': 'Tesla Inc.', 'exchange': 'NASDAQ'},
        {'symbol': 'NVDA', 'name': 'NVIDIA Corporation', 'exchange': 'NASDAQ'},
        {'symbol': 'JPM', 'name': 'JPMorgan Chase & Co.', 'exchange': 'NYSE'},
        {'symbol': 'V', 'name': 'Visa Inc.', 'exchange': 'NYSE'},
        {'symbol': 'JNJ', 'name': 'Johnson & Johnson', 'exchange': 'NYSE'},
        {'symbol': 'WMT', 'name': 'Walmart Inc.', 'exchange': 'NYSE'},
        {'symbol': 'PG', 'name': 'Procter & Gamble Co.', 'exchange': 'NYSE'},
        {'symbol': 'MA', 'name': 'Mastercard Inc.', 'exchange': 'NYSE'},
        {'symbol': 'UNH', 'name': 'UnitedHealth Group Inc.', 'exchange': 'NYSE'},
        {'symbol': 'HD', 'name': 'Home Depot Inc.', 'exchange': 'NYSE'},
        {'symbol': 'DIS', 'name': 'Walt Disney Co.', 'exchange': 'NYSE'},
        {'symbol': 'BAC', 'name': 'Bank of America Corp.', 'exchange': 'NYSE'},
        {'symbol': 'NFLX', 'name': 'Netflix Inc.', 'exchange': 'NASDAQ'},
        {'symbol': 'ADBE', 'name': 'Adobe Inc.', 'exchange': 'NASDAQ'},
        {'symbol': 'CRM', 'name': 'Salesforce Inc.', 'exchange': 'NYSE'},
        {'symbol': 'INTC', 'name': 'Intel Corporation', 'exchange': 'NASDAQ'},
        {'symbol': 'AMD', 'name': 'Advanced Micro Devices Inc.', 'exchange': 'NASDAQ'},
        {'symbol': 'CSCO', 'name': 'Cisco Systems Inc.', 'exchange': 'NASDAQ'},
        {'symbol': 'ORCL', 'name': 'Oracle Corporation', 'exchange': 'NYSE'},
        {'symbol': 'IBM', 'name': 'IBM Corporation', 'exchange': 'NYSE'},
        {'symbol': 'UBER', 'name': 'Uber Technologies Inc.', 'exchange': 'NYSE'},
        {'symbol': 'ABNB', 'name': 'Airbnb Inc.', 'exchange': 'NASDAQ'},
        {'symbol': 'SQ', 'name': 'Block Inc.', 'exchange': 'NYSE'},
        {'symbol': 'SHOP', 'name': 'Shopify Inc.', 'exchange': 'NYSE'},
        {'symbol': 'SPOT', 'name': 'Spotify Technology S.A.', 'exchange': 'NYSE'},
    ]

    query_lower = query.lower()
    results = []

    for stock in POPULAR_STOCKS:
        if (query_lower in stock['symbol'].lower() or
            query_lower in stock['name'].lower()):
            match_type = 'exact' if query_lower == stock['symbol'].lower() else 'partial'
            results.append({**stock, 'match_type': match_type})
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
