"""
Strategic confidence calculation service.
Computes confidence scores based on analysis quality and data coverage.
"""


def calculate_confidence(score: float, sources_available: list, sources_failed: list) -> dict:
    """
    Calculate strategic confidence based on score and data coverage.

    Args:
        score: Quality score from critic (0-10)
        sources_available: List of successfully fetched data sources
        sources_failed: List of failed data sources

    Returns:
        Dictionary with:
        - confidence: Overall confidence percentage (0-100)
        - readiness: Human-readable readiness label
        - level: Confidence level (high/medium/low)
        - score_contribution: Points from quality score
        - data_contribution: Points from data coverage
    """
    # Base confidence from score (0-10 -> 0-60%)
    score_confidence = (score / 10) * 60 if isinstance(score, (int, float)) else 30

    # Data coverage bonus (0-40%)
    total_sources = len(sources_available) + len(sources_failed)
    if total_sources > 0:
        coverage = len(sources_available) / total_sources
        data_confidence = coverage * 40
    else:
        data_confidence = 20

    total_confidence = score_confidence + data_confidence

    # Determine readiness label
    if total_confidence >= 75 and len(sources_failed) == 0:
        readiness = "Board-ready"
        level = "high"
    elif total_confidence >= 60:
        readiness = "Review recommended"
        level = "medium"
    else:
        readiness = "Exploratory"
        level = "low"

    return {
        "confidence": round(total_confidence),
        "readiness": readiness,
        "level": level,
        "score_contribution": round(score_confidence),
        "data_contribution": round(data_confidence)
    }
