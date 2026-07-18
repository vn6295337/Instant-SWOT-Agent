"""Tests for the deterministic Researcher -> Analyzer data gate."""

from src.utils.data_gate import audit_extracted_metrics, scrub_suspect_metrics


def _healthy():
    return {
        "fundamentals": {"revenue": 89.5e9, "net_margin": 2.5, "eps": 2.49},
        "valuation": {"pe_trailing": {"value": 24.1}},
        "volatility": {"beta": 1.15, "vix": 16.73},
        "macro": {"gdp_growth": 2.1, "interest_rate": 3.63},
    }


def test_healthy_data_passes_clean():
    audit = audit_extracted_metrics(_healthy())
    assert audit["gaps"] == []
    assert audit["suspect"] == []


def test_empty_valuation_is_a_gap():
    # The MSFT run shipped an empty valuation basket with no flag anywhere
    data = _healthy()
    data["valuation"] = {}
    audit = audit_extracted_metrics(data)
    assert any(g.startswith("valuation:") for g in audit["gaps"])


def test_missing_fundamentals_below_minimum():
    data = _healthy()
    data["fundamentals"] = {"eps": 2.49}  # only 1 of required 2
    audit = audit_extracted_metrics(data)
    assert "fundamentals: revenue" in audit["gaps"]
    assert "fundamentals: net_margin" in audit["gaps"]


def test_impossible_magnitude_is_quarantined():
    data = _healthy()
    data["fundamentals"]["net_margin"] = 1218.0  # decimal-slip: 12.18 -> 1218
    audit = audit_extracted_metrics(data)
    assert ("fundamentals", "net_margin", 1218.0) in audit["suspect"]


def test_unusual_but_possible_values_pass():
    # Boeing's real D/E of 9.92 and hist vol of 34% must NOT be flagged
    data = _healthy()
    data["fundamentals"]["debt_to_equity"] = 9.92
    data["volatility"]["historical_volatility"] = 34.13
    audit = audit_extracted_metrics(data)
    assert audit["suspect"] == []


def test_scrub_removes_only_quarantined_values():
    data = _healthy()
    data["volatility"]["vix"] = 1673.0
    audit = audit_extracted_metrics(data)
    scrubbed = scrub_suspect_metrics(data, audit["suspect"])
    assert "vix" not in scrubbed["volatility"]
    assert scrubbed["volatility"]["beta"] == 1.15


def test_dict_wrapped_values_audited():
    data = _healthy()
    data["fundamentals"]["net_margin"] = {"value": 1218.0, "end_date": "2025-12-31"}
    audit = audit_extracted_metrics(data)
    assert ("fundamentals", "net_margin", 1218.0) in audit["suspect"]
