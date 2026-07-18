"""Edge-contract tests: SWOT parser routing and numeric validator tolerance."""

from src.services.swot_parser import parse_swot_text
from src.utils.numeric_validator import (
    matches_at_display_precision,
    validate_minimum_citations,
)

SAMPLE = """## Strengths
- [M01] Revenue: $89.5B (as of 2025-12-31) - Large scale supports contracts.
## Weaknesses
- [M07] Debt/Equity: 9.92 - Extremely high leverage.
- Reduce debt through asset sales or refinancing at lower rates.
- Implement cost-control initiatives to improve operating margin.
## Threats
- [M10] VIX: 16.7 - volatility risk.
- Maintain liquidity buffers to weather market turbulence.
## Data Quality Notes
- All financial metrics are sourced from FY 2025 SEC filings.
- News sentiment is based on 4 recent articles.
"""


def test_cited_lines_stay_in_quadrants():
    out = parse_swot_text(SAMPLE)
    assert out["strengths"] == [
        "[M01] Revenue: $89.5B (as of 2025-12-31) - Large scale supports contracts."
    ]
    assert len(out["weaknesses"]) == 1 and out["weaknesses"][0].startswith("[M07]")
    assert len(out["threats"]) == 1 and out["threats"][0].startswith("[M10]")


def test_uncited_lines_become_recommendations():
    out = parse_swot_text(SAMPLE)
    assert len(out["recommendations"]) == 3
    assert all(not r.startswith("[M") for r in out["recommendations"])


def test_data_quality_notes_separated_without_header_leak():
    out = parse_swot_text(SAMPLE)
    assert out["data_quality_notes"] == [
        "All financial metrics are sourced from FY 2025 SEC filings.",
        "News sentiment is based on 4 recent articles.",
    ]
    assert not any(
        line.startswith("#") for section in out.values() for line in section
    )


def test_display_precision_accepts_rounded_table_value():
    # "$2.2B" copied verbatim from a table displaying 2,237,000,000 as $2.2B
    assert matches_at_display_precision("$2.2B", 2.2e9, 2.237e9)


def test_display_precision_rejects_real_mismatch():
    assert not matches_at_display_precision("$2.2B", 2.2e9, 2.4e9)


def test_citation_coverage_counts_unique_refs_only():
    ref = {f"M{i:02d}": {} for i in range(1, 17)}
    result = validate_minimum_citations("[M01] x [M01] y [M02] z " * 3, ref)
    assert result["citations_found"] == 2
    assert result["ratio"] <= 1.0
