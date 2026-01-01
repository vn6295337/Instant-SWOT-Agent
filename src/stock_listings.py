"""
US Stock Listings Module - Autocomplete data source.

Data Sources:
- NASDAQ Trader FTP files (nasdaqlisted.txt, otherlisted.txt)
- Cached locally with daily refresh

Includes: NYSE, NASDAQ, AMEX equities only
Excludes: OTC, ETFs, mutual funds, crypto, indices, international
"""

import csv
import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor

import requests

logger = logging.getLogger("stock-listings")

# Cache configuration
CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"
CACHE_FILE = CACHE_DIR / "us_stocks.json"
CACHE_EXPIRY_HOURS = 24

# NASDAQ Trader FTP URLs (publicly accessible)
NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"

# Exclusion patterns
EXCLUDED_SUFFIXES = {
    # ETFs, funds, notes, warrants, units, rights
    "ETF", "FUND", "TRUST", "NOTE", "WARRANT", "UNIT", "RIGHT",
    "PREFERRED", "DEBENTURE", "BOND", "REIT"
}

EXCLUDED_PATTERNS = [
    r'\bETF\b', r'\bETN\b', r'\bETP\b',
    r'\bFUND\b', r'\bTRUST\b', r'\bINDEX\b',
    r'WARRANT', r'RIGHTS?$', r'UNITS?$',
    r'PREFERRED', r'PFD', r'PRF',
    r'\bLP\b$', r'\bLLC\b$',
    r'DEPOSITARY', r'ADR$', r'ADS$',
]


def _is_common_stock(name: str, symbol: str) -> bool:
    """Filter to include only common stocks, exclude ETFs/funds/etc."""
    name_upper = name.upper()

    # Exclude based on patterns
    for pattern in EXCLUDED_PATTERNS:
        if re.search(pattern, name_upper):
            return False

    # Exclude symbols with special characters (warrants, units, etc.)
    if any(c in symbol for c in ['+', '.', '-', '$']):
        # Allow simple suffixes like BRK.A, BRK.B
        if not re.match(r'^[A-Z]+\.[A-Z]$', symbol):
            return False

    # Exclude very short company names (likely test symbols)
    if len(name) < 3:
        return False

    return True


def _parse_nasdaq_file(content: str, exchange: str) -> List[dict]:
    """Parse NASDAQ trader file format."""
    stocks = []
    lines = content.strip().split('\n')

    if not lines:
        return stocks

    # Skip header and footer
    for line in lines[1:]:
        if line.startswith('File Creation Time'):
            continue

        fields = line.split('|')
        if len(fields) < 2:
            continue

        if exchange == "NASDAQ":
            # nasdaqlisted.txt format: Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares
            symbol = fields[0].strip()
            name = fields[1].strip()
            is_etf = fields[6].strip().upper() == 'Y' if len(fields) > 6 else False
            is_test = fields[3].strip().upper() == 'Y' if len(fields) > 3 else False

            if is_etf or is_test:
                continue

        else:
            # otherlisted.txt format: ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol
            symbol = fields[0].strip()
            name = fields[1].strip()
            exch_code = fields[2].strip()
            is_etf = fields[4].strip().upper() == 'Y' if len(fields) > 4 else False
            is_test = fields[6].strip().upper() == 'Y' if len(fields) > 6 else False

            if is_etf or is_test:
                continue

            # Map exchange codes
            exchange = {
                'A': 'AMEX',
                'N': 'NYSE',
                'P': 'NYSE ARCA',
                'Z': 'BATS',
                'V': 'IEX'
            }.get(exch_code, exch_code)

            # Only include major US exchanges
            if exchange not in ['NYSE', 'AMEX', 'NYSE ARCA']:
                continue

        # Filter common stocks only
        if not _is_common_stock(name, symbol):
            continue

        stocks.append({
            "symbol": symbol,
            "name": name,
            "exchange": exchange
        })

    return stocks


def _fetch_listings() -> List[dict]:
    """Fetch stock listings from NASDAQ trader files."""
    stocks = []

    try:
        # Fetch NASDAQ listed
        logger.info("Fetching NASDAQ listings...")
        resp = requests.get(NASDAQ_LISTED_URL, timeout=30)
        resp.raise_for_status()
        nasdaq_stocks = _parse_nasdaq_file(resp.text, "NASDAQ")
        stocks.extend(nasdaq_stocks)
        logger.info(f"Parsed {len(nasdaq_stocks)} NASDAQ stocks")

        # Fetch other exchanges (NYSE, AMEX)
        logger.info("Fetching NYSE/AMEX listings...")
        resp = requests.get(OTHER_LISTED_URL, timeout=30)
        resp.raise_for_status()
        other_stocks = _parse_nasdaq_file(resp.text, "OTHER")
        stocks.extend(other_stocks)
        logger.info(f"Parsed {len(other_stocks)} NYSE/AMEX stocks")

    except Exception as e:
        logger.error(f"Error fetching listings: {e}")
        # Return cached data if available
        if CACHE_FILE.exists():
            return _load_cache()
        raise

    # Remove duplicates by symbol
    seen = set()
    unique_stocks = []
    for stock in stocks:
        if stock["symbol"] not in seen:
            seen.add(stock["symbol"])
            unique_stocks.append(stock)

    return unique_stocks


def _enrich_with_market_cap(stocks: List[dict], max_workers: int = 10) -> List[dict]:
    """
    Enrich stock data with market cap for ranking.
    Uses yfinance in parallel for speed.
    Only enriches top stocks by name length (proxy for major companies).
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("yfinance not installed, skipping market cap enrichment")
        for stock in stocks:
            stock["market_cap"] = 0
        return stocks

    def fetch_market_cap(symbol: str) -> Optional[float]:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return info.get("marketCap", 0) or 0
        except:
            return 0

    # For performance, only fetch market cap for a subset
    # In production, this would be pre-computed and cached
    logger.info("Enriching with market cap data (sampling)...")

    # Sample: fetch for symbols with short names (likely major companies)
    symbols_to_fetch = [s["symbol"] for s in stocks if len(s["symbol"]) <= 4][:200]

    market_caps = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(fetch_market_cap, symbols_to_fetch))
        for symbol, cap in zip(symbols_to_fetch, results):
            market_caps[symbol] = cap

    # Apply market caps
    for stock in stocks:
        stock["market_cap"] = market_caps.get(stock["symbol"], 0)

    return stocks


def _save_cache(stocks: List[dict]):
    """Save stocks to cache file."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_data = {
        "updated_at": datetime.now().isoformat(),
        "count": len(stocks),
        "stocks": stocks
    }
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache_data, f)
    logger.info(f"Cached {len(stocks)} stocks to {CACHE_FILE}")


def _load_cache() -> List[dict]:
    """Load stocks from cache file."""
    if not CACHE_FILE.exists():
        return []

    with open(CACHE_FILE, 'r') as f:
        cache_data = json.load(f)

    return cache_data.get("stocks", [])


def _is_cache_valid() -> bool:
    """Check if cache exists and is not expired."""
    if not CACHE_FILE.exists():
        return False

    try:
        with open(CACHE_FILE, 'r') as f:
            cache_data = json.load(f)

        updated_at = datetime.fromisoformat(cache_data.get("updated_at", ""))
        expiry = updated_at + timedelta(hours=CACHE_EXPIRY_HOURS)
        return datetime.now() < expiry
    except:
        return False


def get_us_stock_listings(force_refresh: bool = False) -> List[dict]:
    """
    Get list of US stock listings.

    Returns list of dicts with: symbol, name, exchange, market_cap
    Cached for 24 hours.
    """
    if not force_refresh and _is_cache_valid():
        logger.info("Loading stocks from cache")
        return _load_cache()

    logger.info("Fetching fresh stock listings...")
    stocks = _fetch_listings()

    # Sort by market cap (descending) then alphabetically
    stocks.sort(key=lambda x: (-x.get("market_cap", 0), x["symbol"]))

    _save_cache(stocks)
    return stocks


def search_stocks(
    query: str,
    stocks: List[dict],
    max_results: int = 10,
    min_query_length: int = 1
) -> List[dict]:
    """
    Search stocks by name or symbol.

    Features:
    - Case-insensitive matching
    - Matches start of symbol (higher priority) or contains in name
    - Returns results ranked by: exact match > symbol prefix > name contains > market cap

    Args:
        query: Search string
        stocks: List of stock dicts
        max_results: Maximum results to return
        min_query_length: Minimum query length to trigger search

    Returns:
        List of matching stocks with 'match_type' and 'match_indices' for highlighting
    """
    if not query or len(query) < min_query_length:
        return []

    query_upper = query.upper().strip()
    query_lower = query.lower().strip()
    results = []

    for stock in stocks:
        symbol = stock["symbol"].upper()
        name = stock["name"]
        name_lower = name.lower()

        match_type = None
        match_indices = []

        # Priority 1: Exact symbol match
        if symbol == query_upper:
            match_type = "exact_symbol"
            match_indices = list(range(len(query)))

        # Priority 2: Symbol starts with query
        elif symbol.startswith(query_upper):
            match_type = "symbol_prefix"
            match_indices = list(range(len(query)))

        # Priority 3: Symbol contains query
        elif query_upper in symbol:
            match_type = "symbol_contains"
            start = symbol.find(query_upper)
            match_indices = list(range(start, start + len(query)))

        # Priority 4: Name starts with query
        elif name_lower.startswith(query_lower):
            match_type = "name_prefix"
            match_indices = list(range(len(query)))

        # Priority 5: Name contains query (word boundary preferred)
        elif query_lower in name_lower:
            match_type = "name_contains"
            start = name_lower.find(query_lower)
            match_indices = list(range(start, start + len(query)))

        if match_type:
            results.append({
                **stock,
                "match_type": match_type,
                "match_indices": match_indices
            })

    # Sort by match priority, then market cap
    priority = {
        "exact_symbol": 0,
        "symbol_prefix": 1,
        "symbol_contains": 2,
        "name_prefix": 3,
        "name_contains": 4
    }

    results.sort(key=lambda x: (
        priority.get(x["match_type"], 99),
        -x.get("market_cap", 0),
        x["symbol"]
    ))

    return results[:max_results]


def highlight_match(text: str, query: str, is_symbol: bool = False) -> str:
    """
    Return text with HTML highlighting for matched portions.

    Args:
        text: Original text
        query: Search query
        is_symbol: If True, match from start; if False, match anywhere

    Returns:
        HTML string with <mark> tags around matches
    """
    if not query:
        return text

    query_lower = query.lower()
    text_lower = text.lower()

    if query_lower not in text_lower:
        return text

    start = text_lower.find(query_lower)
    end = start + len(query)

    return f"{text[:start]}<mark>{text[start:end]}</mark>{text[end:]}"


# Pre-load function for Streamlit caching
def init_stock_listings():
    """Initialize stock listings (call once at app start)."""
    return get_us_stock_listings()


if __name__ == "__main__":
    # Test the module
    logging.basicConfig(level=logging.INFO)

    print("Fetching US stock listings...")
    stocks = get_us_stock_listings(force_refresh=True)
    print(f"Total stocks: {len(stocks)}")

    # Test search
    test_queries = ["AAPL", "Apple", "TSLA", "Micro", "goo"]
    for q in test_queries:
        results = search_stocks(q, stocks, max_results=5)
        print(f"\nSearch '{q}':")
        for r in results:
            print(f"  {r['symbol']:6} | {r['name'][:40]:40} | {r['exchange']} | {r['match_type']}")
