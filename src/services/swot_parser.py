"""
SWOT text parsing service.
Extracts structured SWOT data from markdown/text reports.

Contract: within the four SWOT sections, only lines carrying an [M##]
citation are treated as SWOT items. Uncited bullets (typically action
recommendations the LLM appends) are diverted to `recommendations`, and any
"Data Quality Notes"-style section goes to `data_quality_notes` — neither
leaks into the quadrant tables.
"""

import re


# A SWOT item per the analyzer's required format: starts with [M##]
ITEM_PATTERN = re.compile(r'^\[?M\d{2}\]?', re.IGNORECASE)


def parse_swot_text(text: str) -> dict:
    """
    Parse SWOT text into structured sections.

    Args:
        text: Raw SWOT analysis text with sections marked by headers

    Returns:
        Dictionary with keys: strengths, weaknesses, opportunities, threats,
        recommendations, data_quality_notes. Each contains a list of strings.
    """
    sections = {
        "strengths": [],
        "weaknesses": [],
        "opportunities": [],
        "threats": [],
        "recommendations": [],
        "data_quality_notes": [],
    }

    current_section = None
    lines = text.split('\n')

    # Regex to match various bullet formats: -, *, •, numbered lists (1., 2.), etc.
    bullet_pattern = re.compile(r'^[\s]*[-*•]\s*(.+)$|^[\s]*\d+[.)]\s*(.+)$')

    swot_headers = [
        ('strength', 'strengths'),
        ('weakness', 'weaknesses'),
        ('opportunit', 'opportunities'),
        ('threat', 'threats'),
        ('recommendation', 'recommendations'),
        ('data quality', 'data_quality_notes'),
    ]

    for line in lines:
        line = line.strip()
        if not line:
            continue

        lower_line = line.lower()

        # Check for section headers (with various formats: ##, **, :, etc.)
        clean_lower = re.sub(r'[#*_:\[\]()]', '', lower_line).strip()

        header_matched = False
        for keyword, section_key in swot_headers:
            if keyword in clean_lower and len(clean_lower) < 50:
                current_section = section_key
                after_header = _extract_after_header(line, keyword)
                if after_header:
                    _route_item(sections, current_section, after_header)
                header_matched = True
                break
        if header_matched:
            continue

        # Unrecognized markdown header: never emit as content
        if line.startswith('#'):
            current_section = None
            continue

        # If we're in a section, try to extract content
        if current_section:
            match = bullet_pattern.match(line)
            if match:
                item = match.group(1) or match.group(2)
                if item and item.strip():
                    _route_item(sections, current_section, item.strip())
            elif not _is_header_line(line) and len(line) > 10:
                _route_item(sections, current_section, line)

    return sections


def _route_item(sections: dict, current_section: str, item: str):
    """
    Place an item per the edge contract: SWOT quadrants only accept
    [M##]-cited lines; uncited lines in a quadrant are recommendations.
    """
    if current_section in ("recommendations", "data_quality_notes"):
        sections[current_section].append(item)
    elif ITEM_PATTERN.match(item):
        sections[current_section].append(item)
    else:
        sections["recommendations"].append(item)


def _extract_after_header(line: str, keyword: str) -> str:
    """Extract content that appears after a section header on the same line."""
    lower = line.lower()
    idx = lower.find(keyword)
    if idx == -1:
        return ""

    end_idx = idx + len(keyword)
    while end_idx < len(line) and line[end_idx].isalpha():
        end_idx += 1

    remainder = line[end_idx:].strip()
    remainder = re.sub(r'^[:\-–—\s]+', '', remainder).strip()
    remainder = re.sub(r'^[#*_]+\s*', '', remainder).strip()

    if len(remainder) > 10 and not remainder.lower().startswith(('strength', 'weakness', 'opportunit', 'threat')):
        return remainder
    return ""


def _is_header_line(line: str) -> bool:
    """Check if a line appears to be a header rather than content."""
    clean = re.sub(r'[#*_:\-–—\[\]()]', '', line).strip()
    if len(clean) < 5:
        return True
    if line.rstrip().endswith(':'):
        return True
    return False
