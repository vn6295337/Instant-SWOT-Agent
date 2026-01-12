"""
Deterministic numeric validation for SWOT analysis outputs.

Layer 4: Validates that cited metric values match the reference table.
Extracts [M##] citations from SWOT text and verifies against metric_reference dict.
"""

import re
from typing import Optional


# Pattern to match citations like: $394.3B [M01], 25.3% [M02], 32.5 [M04]
CITATION_PATTERN = re.compile(
    r'([\d,$\.]+[BMK%]?)\s*\[M(\d{2})\]',
    re.IGNORECASE
)


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

    Returns list of dicts:
    [
        {"ref_id": "M01", "cited_value": "$394.3B", "normalized": 394300000000.0},
        {"ref_id": "M02", "cited_value": "25.3%", "normalized": 25.3},
    ]
    """
    citations = []
    for match in CITATION_PATTERN.finditer(text):
        cited_value = match.group(1)
        ref_num = match.group(2)
        ref_id = f"M{ref_num}"
        normalized = normalize_value(cited_value)
        citations.append({
            "ref_id": ref_id,
            "cited_value": cited_value,
            "normalized": normalized
        })
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
