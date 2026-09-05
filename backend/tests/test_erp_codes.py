from app.core.erp_codes import (
    area_short_code,
    format_organization_code,
    format_school_code,
    normalize_area_code,
    school_prefix,
)


def test_erp_code_standard_examples():
    assert school_prefix("AKSHARA SCHOOL") == "AK"
    assert school_prefix("SRI VALLI SCHOOL") == "SV"
    assert area_short_code("Razole") == "RZL"
    assert area_short_code("Pedana") == "PDN"
    assert normalize_area_code("r-z-l") == "RZL"
    assert format_organization_code("AK", 1) == "AK-ORG-01"
    assert format_school_code("AK", "RZL", 1) == "AK-RZL-01"
