"""
Stock search route handlers.
Provides stock ticker autocomplete functionality.
"""

from fastapi import APIRouter, HTTPException, Query

from src.stock_listings import get_us_stock_listings, search_stocks

router = APIRouter()

# Stock listings cache (loaded once at startup)
STOCK_LISTINGS: list = []


async def load_stock_listings():
    """Load stock listings on startup."""
    global STOCK_LISTINGS
    try:
        STOCK_LISTINGS = get_us_stock_listings()
        print(f"Loaded {len(STOCK_LISTINGS)} US stock listings")
    except Exception as e:
        print(f"Warning: Could not load stock listings: {e}")


@router.get("/api/stocks/search")
async def search_stocks_endpoint(q: str = Query(..., min_length=1, max_length=50)):
    """Search US stock listings by symbol or company name."""
    global STOCK_LISTINGS

    if not STOCK_LISTINGS:
        # Fallback: try loading if not already loaded
        try:
            STOCK_LISTINGS = get_us_stock_listings()
        except Exception:
            raise HTTPException(status_code=503, detail="Stock listings not available")

    results = search_stocks(q, STOCK_LISTINGS, max_results=10)

    return {
        "query": q,
        "results": [
            {
                "symbol": r["symbol"],
                "name": r["name"],
                "exchange": r["exchange"],
                "match_type": r.get("match_type", "unknown")
            }
            for r in results
        ]
    }
