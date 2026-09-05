"""Human-readable ERP business-code helpers.

Internal database identifiers remain UUIDs. These helpers only generate stable,
human-readable business identifiers that are shown to administrators.
"""

from __future__ import annotations

import re

GENERIC_SCHOOL_WORDS = {
    "SCHOOL",
    "HIGH",
    "PUBLIC",
    "INTERNATIONAL",
    "ACADEMY",
    "COLLEGE",
    "EDUCATION",
    "EDUCATIONAL",
    "SOCIETY",
    "TRUST",
    "GROUP",
    "THE",
}


def _words(value: str) -> list[str]:
    return re.findall(r"[A-Z0-9]+", (value or "").upper())


def school_prefix(name: str) -> str:
    """Return the agreed two-letter school/organization prefix.

    Examples: AKSHARA SCHOOL -> AK, SRI VALLI SCHOOL -> SV.
    """
    meaningful = [w for w in _words(name) if w not in GENERIC_SCHOOL_WORDS]
    if not meaningful:
        meaningful = _words(name)
    if not meaningful:
        return "ER"
    if len(meaningful) >= 2 and len(meaningful[0]) <= 3:
        return (meaningful[0][0] + meaningful[1][0])[:2]
    word = meaningful[0]
    return (word[:2] if len(word) >= 2 else (word + "X"))[:2]


def area_short_code(area: str) -> str:
    """Suggest a 3-character area/village code.

    The UI allows the administrator to correct this suggestion before creation.
    We prefer consonants after the first character because common locality names
    such as RAZOLE naturally become RZL.
    """
    words = _words(area)
    text = "".join(words)
    if not text:
        return "LOC"
    if len(text) <= 3:
        return text.ljust(3, "X")
    first = text[0]
    consonants = [ch for ch in text[1:] if ch not in "AEIOU"]
    code = first + "".join(consonants[:2])
    if len(code) < 3:
        code += "".join(ch for ch in text[1:] if ch not in code)[: 3 - len(code)]
    return code[:3]


def normalize_area_code(value: str) -> str:
    code = "".join(_words(value))[:3]
    if len(code) < 2:
        raise ValueError("Area short code must contain at least 2 letters/numbers")
    return code


def format_organization_code(prefix: str, sequence: int) -> str:
    return f"{prefix}-ORG-{sequence:02d}"


def format_school_code(prefix: str, area_code: str, sequence: int) -> str:
    return f"{prefix}-{area_code}-{sequence:02d}"
