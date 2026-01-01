"""
Analysis Cache - Supabase PostgreSQL caching for final SWOT analysis results.

Caches Editor agent output with 24h TTL to avoid re-running the full pipeline.
Uses schema: asa.analysis_cache
"""

import os
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables (project .env first, then ~/.env for local overrides)
load_dotenv()  # Project .env or HF Space secrets
load_dotenv(os.path.expanduser("~/.env"))  # Local development overrides

logger = logging.getLogger("analysis-cache")

# Default TTL: 24 hours
DEFAULT_TTL_HOURS = 24

# Supabase PostgreSQL connection string
SUPABASE_DB_URL = os.getenv("PIPELINE_SUPABASE_URL")


def get_connection():
    """Get PostgreSQL connection to Supabase."""
    if not SUPABASE_DB_URL:
        raise RuntimeError("PIPELINE_SUPABASE_URL not set in environment")
    return psycopg2.connect(SUPABASE_DB_URL)


def get_cached_analysis(ticker: str) -> Optional[dict]:
    """
    Get cached analysis for a ticker if it exists and hasn't expired.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Cached analysis dict or None if not found/expired
    """
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Auto-cleanup: delete expired entries before checking cache
        cursor.execute("DELETE FROM asa.analysis_cache WHERE expires_at <= NOW()")
        deleted = cursor.rowcount
        if deleted > 0:
            conn.commit()
            logger.info(f"Auto-cleanup: removed {deleted} expired cache entries")

        cursor.execute("""
            SELECT data, expires_at
            FROM asa.analysis_cache
            WHERE ticker = %s AND expires_at > NOW()
        """, (ticker.upper(),))

        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row:
            data = row['data']
            if isinstance(data, str):
                data = json.loads(data)

            # Add cache metadata
            data["_cache_info"] = {
                "cached": True,
                "expires_at": row['expires_at'].isoformat() if row['expires_at'] else None
            }
            logger.info(f"Cache HIT for {ticker}")
            return data

        logger.info(f"Cache MISS for {ticker}")
        return None

    except Exception as e:
        logger.error(f"Cache read error for {ticker}: {e}")
        return None


def set_cached_analysis(ticker: str, company_name: str, data: dict, ttl_hours: int = DEFAULT_TTL_HOURS):
    """
    Store analysis result in cache.

    Args:
        ticker: Stock ticker symbol
        company_name: Company name
        data: Full analysis result dict (swot_data, score, critique, etc.)
        ttl_hours: Time-to-live in hours (default 24)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Auto-cleanup: delete expired entries before inserting new one
        cursor.execute("DELETE FROM asa.analysis_cache WHERE expires_at <= NOW()")
        deleted = cursor.rowcount
        if deleted > 0:
            logger.info(f"Auto-cleanup: removed {deleted} expired cache entries")

        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

        # Remove cache info before storing
        data_to_store = {k: v for k, v in data.items() if k != "_cache_info"}

        cursor.execute("""
            INSERT INTO asa.analysis_cache (ticker, company_name, data, created_at, expires_at)
            VALUES (%s, %s, %s, NOW(), %s)
            ON CONFLICT (ticker)
            DO UPDATE SET
                company_name = EXCLUDED.company_name,
                data = EXCLUDED.data,
                created_at = NOW(),
                expires_at = EXCLUDED.expires_at
        """, (ticker.upper(), company_name, json.dumps(data_to_store, default=str), expires_at))

        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"Cached analysis for {ticker} (expires: {expires_at})")

    except Exception as e:
        logger.error(f"Cache write error for {ticker}: {e}")


def clear_cache(ticker: Optional[str] = None):
    """
    Clear cache entries.

    Args:
        ticker: If provided, clear only this ticker. Otherwise clear all.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        if ticker:
            cursor.execute("DELETE FROM asa.analysis_cache WHERE ticker = %s", (ticker.upper(),))
            logger.info(f"Cleared cache for {ticker}")
        else:
            cursor.execute("DELETE FROM asa.analysis_cache")
            logger.info("Cleared all cache entries")

        conn.commit()
        cursor.close()
        conn.close()

    except Exception as e:
        logger.error(f"Cache clear error: {e}")


def clear_expired_cache() -> int:
    """Remove all expired cache entries. Returns count of deleted entries."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM asa.analysis_cache WHERE expires_at <= NOW()")
        deleted = cursor.rowcount

        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"Cleared {deleted} expired cache entries")
        return deleted

    except Exception as e:
        logger.error(f"Cache cleanup error: {e}")
        return 0


def get_cache_stats() -> dict:
    """Get cache statistics."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM asa.analysis_cache")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM asa.analysis_cache WHERE expires_at > NOW()")
        valid = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM asa.analysis_cache WHERE expires_at <= NOW()")
        expired = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return {
            "total_entries": total,
            "valid_entries": valid,
            "expired_entries": expired
        }

    except Exception as e:
        logger.error(f"Cache stats error: {e}")
        return {"total_entries": 0, "valid_entries": 0, "expired_entries": 0}
