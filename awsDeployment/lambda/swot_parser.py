# SWOT text parser - extracts structured data from markdown report
import re


def parse_swot_text(text: str) -> dict:
    """
    Parse SWOT text into structured sections.

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

    # Regex to match various bullet formats
    bullet_pattern = re.compile(r'^[\s]*[-*•]\s*(.+)$|^[\s]*\d+[.)]\s*(.+)$')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        lower_line = line.lower()
        clean_lower = re.sub(r'[#*_:\[\]()]', '', lower_line).strip()

        # Detect section headers
        if 'strength' in clean_lower and len(clean_lower) < 50:
            current_section = 'strengths'
            continue
        elif 'weakness' in clean_lower and len(clean_lower) < 50:
            current_section = 'weaknesses'
            continue
        elif 'opportunit' in clean_lower and len(clean_lower) < 50:
            current_section = 'opportunities'
            continue
        elif 'threat' in clean_lower and len(clean_lower) < 50:
            current_section = 'threats'
            continue

        # Skip other headers
        if line.startswith('#') or line.startswith('**'):
            if current_section and not any(word in lower_line for word in ['strength', 'weakness', 'opportunit', 'threat']):
                current_section = None
            continue

        # Extract bullet content
        if current_section:
            bullet_match = bullet_pattern.match(line)
            if bullet_match:
                content = bullet_match.group(1) or bullet_match.group(2)
                if content and len(content) > 5:
                    sections[current_section].append(content.strip())
            elif not line.startswith('|') and len(line) > 10:
                # Non-bullet line content (paragraph)
                sections[current_section].append(line)

    return sections
