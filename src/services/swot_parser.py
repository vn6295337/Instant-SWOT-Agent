"""
SWOT text parsing service.
Extracts structured SWOT data from markdown/text reports.
"""

import re


def parse_swot_text(text: str) -> dict:
    """
    Parse SWOT text into structured sections.

    Args:
        text: Raw SWOT analysis text with sections marked by headers

    Returns:
        Dictionary with keys: strengths, weaknesses, opportunities, threats
        Each containing a list of bullet points
    """
    sections = {
        "strengths": [],
        "weaknesses": [],
        "opportunities": [],
        "threats": []
    }

    current_section = None
    lines = text.split('\n')

    # Regex to match various bullet formats: -, *, •, numbered lists (1., 2.), etc.
    bullet_pattern = re.compile(r'^[\s]*[-*•]\s*(.+)$|^[\s]*\d+[.)]\s*(.+)$')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        lower_line = line.lower()

        # Check for section headers (with various formats: ##, **, :, etc.)
        # Clean the line of markdown formatting for header detection
        clean_lower = re.sub(r'[#*_:\[\]()]', '', lower_line).strip()

        if 'strength' in clean_lower and len(clean_lower) < 50:
            current_section = 'strengths'
            # Check if there's content after the header on same line
            after_header = _extract_after_header(line, 'strength')
            if after_header:
                sections[current_section].append(after_header)
            continue
        elif 'weakness' in clean_lower and len(clean_lower) < 50:
            current_section = 'weaknesses'
            after_header = _extract_after_header(line, 'weakness')
            if after_header:
                sections[current_section].append(after_header)
            continue
        elif 'opportunit' in clean_lower and len(clean_lower) < 50:
            current_section = 'opportunities'
            after_header = _extract_after_header(line, 'opportunit')
            if after_header:
                sections[current_section].append(after_header)
            continue
        elif 'threat' in clean_lower and len(clean_lower) < 50:
            current_section = 'threats'
            after_header = _extract_after_header(line, 'threat')
            if after_header:
                sections[current_section].append(after_header)
            continue

        # If we're in a section, try to extract content
        if current_section:
            # Try bullet pattern first
            match = bullet_pattern.match(line)
            if match:
                # Get whichever group matched
                item = match.group(1) or match.group(2)
                if item and item.strip():
                    sections[current_section].append(item.strip())
            elif not _is_header_line(line) and len(line) > 10:
                # Plain text line that's not a header - might be content
                # Only add if it looks like actual content (not too short)
                sections[current_section].append(line)

    return sections


def _extract_after_header(line: str, keyword: str) -> str:
    """Extract content that appears after a section header on the same line."""
    # Find where the keyword ends and check for content after
    lower = line.lower()
    idx = lower.find(keyword)
    if idx == -1:
        return ""

    # Find end of the header word
    end_idx = idx + len(keyword)
    # Skip past any trailing 's', 'es', 'ies' for plurals
    while end_idx < len(line) and line[end_idx].isalpha():
        end_idx += 1

    # Get remainder and clean it
    remainder = line[end_idx:].strip()
    # Remove common separators: :, -, etc.
    remainder = re.sub(r'^[:\-–—\s]+', '', remainder).strip()
    # Remove markdown formatting
    remainder = re.sub(r'^[#*_]+\s*', '', remainder).strip()

    # If there's substantial content, return it
    if len(remainder) > 10 and not remainder.lower().startswith(('strength', 'weakness', 'opportunit', 'threat')):
        return remainder
    return ""


def _is_header_line(line: str) -> bool:
    """Check if a line appears to be a header rather than content."""
    # Lines that are mostly formatting or very short are likely headers
    clean = re.sub(r'[#*_:\-–—\[\]()]', '', line).strip()
    if len(clean) < 5:
        return True
    # Lines ending with : are often headers
    if line.rstrip().endswith(':'):
        return True
    return False
