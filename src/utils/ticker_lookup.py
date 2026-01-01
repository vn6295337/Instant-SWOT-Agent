"""
Ticker Lookup - Maps company names to stock ticker symbols.
"""

import re
from typing import Optional

# Common company name to ticker mappings
TICKER_MAP = {
    # Tech Giants
    "apple": "AAPL",
    "microsoft": "MSFT",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "amazon": "AMZN",
    "meta": "META",
    "facebook": "META",
    "nvidia": "NVDA",
    "tesla": "TSLA",
    "netflix": "NFLX",
    "adobe": "ADBE",
    "salesforce": "CRM",
    "oracle": "ORCL",
    "intel": "INTC",
    "amd": "AMD",
    "ibm": "IBM",
    "cisco": "CSCO",
    "qualcomm": "QCOM",
    "broadcom": "AVGO",
    "paypal": "PYPL",
    "shopify": "SHOP",
    "zoom": "ZM",
    "uber": "UBER",
    "lyft": "LYFT",
    "airbnb": "ABNB",
    "palantir": "PLTR",
    "snowflake": "SNOW",
    "crowdstrike": "CRWD",
    "datadog": "DDOG",

    # Finance
    "jpmorgan": "JPM",
    "jp morgan": "JPM",
    "bank of america": "BAC",
    "wells fargo": "WFC",
    "goldman sachs": "GS",
    "morgan stanley": "MS",
    "citigroup": "C",
    "visa": "V",
    "mastercard": "MA",
    "american express": "AXP",
    "berkshire hathaway": "BRK.B",
    "blackrock": "BLK",
    "charles schwab": "SCHW",

    # Healthcare
    "johnson & johnson": "JNJ",
    "johnson and johnson": "JNJ",
    "pfizer": "PFE",
    "unitedhealth": "UNH",
    "eli lilly": "LLY",
    "merck": "MRK",
    "abbvie": "ABBV",
    "bristol-myers squibb": "BMY",
    "amgen": "AMGN",
    "gilead": "GILD",
    "moderna": "MRNA",
    "regeneron": "REGN",
    "biogen": "BIIB",
    "cvs health": "CVS",

    # Consumer
    "walmart": "WMT",
    "costco": "COST",
    "home depot": "HD",
    "target": "TGT",
    "lowes": "LOW",
    "nike": "NKE",
    "starbucks": "SBUX",
    "mcdonalds": "MCD",
    "coca-cola": "KO",
    "coca cola": "KO",
    "pepsi": "PEP",
    "pepsico": "PEP",
    "procter & gamble": "PG",
    "procter and gamble": "PG",
    "disney": "DIS",

    # Industrial
    "boeing": "BA",
    "caterpillar": "CAT",
    "general electric": "GE",
    "3m": "MMM",
    "honeywell": "HON",
    "lockheed martin": "LMT",
    "raytheon": "RTX",
    "union pacific": "UNP",
    "ups": "UPS",
    "fedex": "FDX",

    # Energy
    "exxon": "XOM",
    "exxonmobil": "XOM",
    "chevron": "CVX",
    "conocophillips": "COP",
    "schlumberger": "SLB",

    # Telecom
    "att": "T",
    "at&t": "T",
    "verizon": "VZ",
    "t-mobile": "TMUS",

    # Automotive
    "ford": "F",
    "general motors": "GM",
    "rivian": "RIVN",
    "lucid": "LCID",
}


def get_ticker(company_name: str) -> Optional[str]:
    """
    Get stock ticker symbol from company name.

    Args:
        company_name: Company name (e.g., 'Tesla', 'Apple Inc.')

    Returns:
        Ticker symbol (e.g., 'TSLA', 'AAPL') or None if not found
    """
    if not company_name:
        return None

    # Clean up the company name
    name = company_name.lower().strip()

    # Remove common suffixes
    suffixes = [
        " inc", " inc.", " incorporated",
        " corp", " corp.", " corporation",
        " ltd", " ltd.", " limited",
        " llc", " plc", " co", " co.",
        " company", " companies",
        " holdings", " group"
    ]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()

    # Check if input is already a ticker (all caps, 1-5 chars)
    if re.match(r'^[A-Z]{1,5}$', company_name.strip()):
        return company_name.strip().upper()

    # Look up in mapping
    if name in TICKER_MAP:
        return TICKER_MAP[name]

    # Try partial match
    for key, ticker in TICKER_MAP.items():
        if key in name or name in key:
            return ticker

    # If no match found, assume input might be ticker
    clean = re.sub(r'[^A-Za-z]', '', company_name).upper()
    if len(clean) <= 5:
        return clean

    return None


def normalize_company_name(company_name: str) -> str:
    """
    Normalize company name for display.

    Args:
        company_name: Raw company name input

    Returns:
        Cleaned company name
    """
    if not company_name:
        return ""

    # Title case
    name = company_name.strip().title()

    # Fix common acronyms
    replacements = {
        "Ibm": "IBM",
        "Amd": "AMD",
        "Att": "AT&T",
        "Ups": "UPS",
        "3M": "3M",
        "Jp Morgan": "JPMorgan",
        "Jpmorgan": "JPMorgan",
    }

    for old, new in replacements.items():
        name = name.replace(old, new)

    return name
