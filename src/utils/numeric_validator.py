"""
Deterministic numeric validation for SWOT analysis outputs.

Layer 4: Validates that cited metric values match the reference table.
Extracts [M##] citations from SWOT text and verifies against metric_reference dict.
"""

import re
from typing import Optional


# Pattern to match citations in NEW format: [M01] Revenue: $394.3B - insight
# Matches: [M##] followed by metric name, colon, and value
CITATION_PATTERN_NEW = re.compile(
    r'\[M(\d{2})\]\s*[^:]+:\s*(\$?[\d,]+\.?\d*[BMKTx%]?)',
    re.IGNORECASE
)

# Pattern to match citations in OLD format: $394.3B [M01] (kept for backwards compatibility)
CITATION_PATTERN_OLD = re.compile(
    r'([\d,$\.]+[BMK%]?)\s*\[M(\d{2})\]',
    re.IGNORECASE
)

# Combined pattern to find any [M##] reference (for citation counting)
CITATION_REF_PATTERN = re.compile(r'\[M(\d{2})\]', re.IGNORECASE)


def normalize_value(text: str) -> Optional[float]:
    """
    Normalize a value string to a float for comparison.

    Handles:
    - Currency: $394.3B -> 394300000000, $56.6M -> 56600000
    - Percentages: 25.3% -> 25.3
    - Plain numbers: 32.5 -> 32.5, 1,234 -> 1234

    Returns None if parsing fails.
    """
    if not text:
        return None

    # Remove whitespace and common formatting
    text = text.strip().replace(',', '').replace(' ', '')

    # Handle currency with B/M/K suffix
    if text.startswith('$'):
        text = text[1:]  # Remove $
        multiplier = 1
        if text.upper().endswith('B'):
            multiplier = 1e9
            text = text[:-1]
        elif text.upper().endswith('M'):
            multiplier = 1e6
            text = text[:-1]
        elif text.upper().endswith('K'):
            multiplier = 1e3
            text = text[:-1]
        try:
            return float(text) * multiplier
        except ValueError:
            return None

    # Handle percentages
    if text.endswith('%'):
        try:
            return float(text[:-1])
        except ValueError:
            return None

    # Plain number
    try:
        return float(text)
    except ValueError:
        return None


def values_match(found_value: float, expected_value: float, value_type: str = "unknown") -> bool:
    """
    Check if two values match within acceptable tolerance.

    Tolerances:
    - Currency (large numbers): ±1% relative
    - Percentages: ±0.1 absolute
    - Small decimals (ratios, etc.): ±0.05 absolute
    """
    if found_value is None or expected_value is None:
        return False

    # Large numbers (currency) - use relative tolerance
    if abs(expected_value) >= 1e6:
        tolerance = abs(expected_value) * 0.01  # 1%
        return abs(found_value - expected_value) <= tolerance

    # Small numbers - use absolute tolerance
    # Percentages and ratios
    if abs(expected_value) < 100:
        tolerance = 0.15  # Allow slight rounding differences
        return abs(found_value - expected_value) <= tolerance

    # Medium numbers
    tolerance = abs(expected_value) * 0.01
    return abs(found_value - expected_value) <= tolerance


def extract_citations(text: str) -> list[dict]:
    """
    Extract all [M##] citations from text.

    Supports both formats:
    - NEW: [M01] Revenue: $394.3B - insight
    - OLD: $394.3B [M01]

    Returns list of dicts:
    [
        {"ref_id": "M01", "cited_value": "$394.3B", "normalized": 394300000000.0},
        {"ref_id": "M02", "cited_value": "25.3%", "normalized": 25.3},
    ]
    """
    citations = []
    seen_refs = set()

    # Try NEW format first: [M##] Metric: Value
    for match in CITATION_PATTERN_NEW.finditer(text):
        ref_num = match.group(1)
        cited_value = match.group(2)
        ref_id = f"M{ref_num}"
        if ref_id not in seen_refs:
            normalized = normalize_value(cited_value)
            citations.append({
                "ref_id": ref_id,
                "cited_value": cited_value,
                "normalized": normalized
            })
            seen_refs.add(ref_id)

    # Also try OLD format: Value [M##]
    for match in CITATION_PATTERN_OLD.finditer(text):
        cited_value = match.group(1)
        ref_num = match.group(2)
        ref_id = f"M{ref_num}"
        if ref_id not in seen_refs:
            normalized = normalize_value(cited_value)
            citations.append({
                "ref_id": ref_id,
                "cited_value": cited_value,
                "normalized": normalized
            })
            seen_refs.add(ref_id)

    return citations


def validate_citations(swot_text: str, metric_reference: dict) -> dict:
    """
    Validate all citations in SWOT text against metric_reference.

    Args:
        swot_text: The SWOT analysis output
        metric_reference: Dict from Layer 1 with format:
            {"M01": {"key": "revenue", "raw_value": 394328000000, "formatted": "..."}, ...}

    Returns:
        {
            "valid": bool,
            "citations_found": int,
            "mismatches": [
                "revenue [M01]: cited $56.6B, expected $394.3B",
                ...
            ],
            "missing_refs": ["M99"],  # Citations to non-existent refs
            "details": [...]  # Full details for each citation
        }
    """
    citations = extract_citations(swot_text)

    result = {
        "valid": True,
        "citations_found": len(citations),
        "mismatches": [],
        "missing_refs": [],
        "details": []
    }

    for citation in citations:
        ref_id = citation["ref_id"]
        cited_value = citation["cited_value"]
        cited_normalized = citation["normalized"]

        detail = {
            "ref_id": ref_id,
            "cited_value": cited_value,
            "cited_normalized": cited_normalized,
            "status": "unknown"
        }

        # Check if reference exists
        if ref_id not in metric_reference:
            result["missing_refs"].append(ref_id)
            result["valid"] = False
            detail["status"] = "missing_ref"
            detail["error"] = f"Reference {ref_id} not found in metric table"
            result["details"].append(detail)
            continue

        ref_entry = metric_reference[ref_id]
        expected_value = ref_entry.get("raw_value")
        metric_key = ref_entry.get("key", "unknown")
        expected_formatted = ref_entry.get("formatted", str(expected_value))

        detail["metric_key"] = metric_key
        detail["expected_value"] = expected_value
        detail["expected_formatted"] = expected_formatted

        # Check if values match
        if cited_normalized is None:
            result["mismatches"].append(
                f"{metric_key} [{ref_id}]: could not parse cited value '{cited_value}'"
            )
            result["valid"] = False
            detail["status"] = "parse_error"
        elif not values_match(cited_normalized, expected_value):
            # Format expected value for display
            if abs(expected_value) >= 1e9:
                expected_display = f"${expected_value/1e9:.1f}B"
            elif abs(expected_value) >= 1e6:
                expected_display = f"${expected_value/1e6:.0f}M"
            else:
                expected_display = expected_formatted.split(" (as of")[0] if " (as of" in expected_formatted else expected_formatted

            result["mismatches"].append(
                f"{metric_key} [{ref_id}]: cited {cited_value}, expected {expected_display}"
            )
            result["valid"] = False
            detail["status"] = "mismatch"
        else:
            detail["status"] = "valid"

        result["details"].append(detail)

    return result


def validate_numeric_accuracy(swot_text: str, metric_reference: dict) -> list[str]:
    """
    Main validation function for critic integration.

    Returns list of mismatch descriptions (empty if all valid).
    """
    if not metric_reference:
        return []

    result = validate_citations(swot_text, metric_reference)

    # Combine mismatches and missing refs
    errors = result["mismatches"].copy()
    for ref_id in result["missing_refs"]:
        errors.append(f"Invalid reference: {ref_id} not in metric table")

    return errors


# ============================================================
# LAYER 3: Uncited Number Detection
# ============================================================

# Pattern to match metric-like numbers (will filter out cited ones programmatically)
# Matches: $56.6B, $394M, 25.3%, 12.14, 0.84x, etc.
METRIC_NUMBER_PATTERN = re.compile(
    r'('
    r'\$[\d,]+\.?\d*[BMK]?'  # Currency: $56.6B, $394M, $1,234
    r'|'
    r'[\d,]+\.?\d*%'  # Percentage: 25.3%, 12%
    r'|'
    r'[\d,]+\.\d+x'  # Ratio with x: 1.5x, 12.3x
    r')',
    re.IGNORECASE
)

# Keywords that indicate a number is likely a metric value
METRIC_CONTEXT_KEYWORDS = [
    'revenue', 'income', 'profit', 'margin', 'cap', 'market cap', 'enterprise value',
    'p/e', 'pe ratio', 'p/b', 'pb ratio', 'p/s', 'ps ratio', 'ev/ebitda',
    'beta', 'volatility', 'vix', 'growth', 'yield', 'dividend',
    'debt', 'equity', 'assets', 'liabilities', 'cash flow', 'fcf',
    'eps', 'earnings', 'roi', 'roe', 'roa', 'ebitda',
    'gdp', 'inflation', 'unemployment', 'interest rate',
]


def find_uncited_numbers(swot_text: str, metric_reference: dict) -> list[dict]:
    """
    Find numbers that look like metrics but don't have [M##] citations.

    Returns list of suspicious uncited numbers with context.
    """
    uncited = []

    # Get all cited positions to exclude (check both NEW and OLD patterns)
    cited_positions = set()

    # NEW format: [M##] Metric: Value
    for match in CITATION_PATTERN_NEW.finditer(swot_text):
        cited_positions.update(range(match.start(), match.end()))

    # OLD format: Value [M##]
    for match in CITATION_PATTERN_OLD.finditer(swot_text):
        cited_positions.update(range(match.start(), match.end()))

    # Find all metric-like numbers
    for match in METRIC_NUMBER_PATTERN.finditer(swot_text):
        # Skip if this position overlaps with a citation
        if any(pos in cited_positions for pos in range(match.start(), match.end())):
            continue

        value_str = match.group(1)
        normalized = normalize_value(value_str)

        if normalized is None:
            continue

        # Get surrounding context (50 chars before and after)
        start = max(0, match.start() - 50)
        end = min(len(swot_text), match.end() + 50)
        context = swot_text[start:end].replace('\n', ' ')

        # Check if context contains metric-related keywords
        context_lower = context.lower()
        has_metric_context = any(kw in context_lower for kw in METRIC_CONTEXT_KEYWORDS)

        # Check if value matches any known metric (within tolerance)
        matches_known_metric = False
        matched_metric_key = None
        for ref_id, ref_entry in metric_reference.items():
            expected = ref_entry.get("raw_value")
            if expected and values_match(normalized, expected):
                matches_known_metric = True
                matched_metric_key = ref_entry.get("key")
                break

        # Flag as suspicious if it looks like a metric
        if has_metric_context or matches_known_metric:
            uncited.append({
                "value": value_str,
                "normalized": normalized,
                "position": match.start(),
                "context": context.strip(),
                "has_metric_context": has_metric_context,
                "matches_known_metric": matches_known_metric,
                "matched_metric_key": matched_metric_key,
            })

    return uncited


def validate_uncited_numbers(swot_text: str, metric_reference: dict) -> list[str]:
    """
    Validate that metric-like numbers have proper citations.

    Returns list of warnings for uncited numbers that should have citations.
    """
    if not metric_reference:
        return []

    uncited = find_uncited_numbers(swot_text, metric_reference)
    warnings = []

    for item in uncited:
        if item["matches_known_metric"]:
            # This number matches a known metric - MUST have citation
            warnings.append(
                f"Uncited metric value: {item['value']} appears to be {item['matched_metric_key']} - add [M##] citation"
            )
        elif item["has_metric_context"]:
            # Number in metric context without citation - suspicious
            warnings.append(
                f"Uncited number in metric context: {item['value']} - verify source or add citation"
            )

    return warnings


def get_citation_count(swot_text: str) -> int:
    """Count the number of [M##] citations in the text."""
    return len(CITATION_REF_PATTERN.findall(swot_text))


def validate_minimum_citations(swot_text: str, metric_reference: dict, min_ratio: float = 0.5) -> dict:
    """
    Check if SWOT has enough citations relative to available metrics.

    Args:
        swot_text: The SWOT analysis output
        metric_reference: Available metrics
        min_ratio: Minimum ratio of citations to available metrics (default 0.5 = 50%)

    Returns:
        {
            "valid": bool,
            "citations_found": int,
            "metrics_available": int,
            "ratio": float,
            "message": str
        }
    """
    citations_found = get_citation_count(swot_text)
    metrics_available = len(metric_reference) if metric_reference else 0

    if metrics_available == 0:
        return {
            "valid": True,
            "citations_found": citations_found,
            "metrics_available": 0,
            "ratio": 0,
            "message": "No metrics available for citation"
        }

    ratio = citations_found / metrics_available
    valid = ratio >= min_ratio

    if valid:
        message = f"Citation coverage: {citations_found}/{metrics_available} ({ratio:.0%})"
    else:
        message = f"Insufficient citations: {citations_found}/{metrics_available} ({ratio:.0%}) - minimum {min_ratio:.0%} required"

    return {
        "valid": valid,
        "citations_found": citations_found,
        "metrics_available": metrics_available,
        "ratio": ratio,
        "message": message
    }
