from enum import StrEnum

import pytest

from troubleshooter.domain.codes import (
    Dimension,
    EscalationLevel,
    HealthLabel,
    InputClassification,
    RaciCode,
)

# Codes are a stored format: recorded samples depend on these exact strings.
EXPECTED_CODES: dict[type[StrEnum], list[str]] = {
    Dimension: ["schedule", "scope", "quality", "risk_control", "stakeholder_confidence"],
    HealthLabel: ["good", "problematic", "at_risk"],
    EscalationLevel: ["team", "pm", "sponsor", "steering"],
    RaciCode: ["R", "A", "C", "I"],
    InputClassification: ["troubled", "healthy", "too_thin", "off_topic"],
}


@pytest.mark.parametrize(("enum", "codes"), EXPECTED_CODES.items())
def test_codes_are_stable(enum: type[StrEnum], codes: list[str]) -> None:
    assert [member.value for member in enum] == codes


@pytest.mark.parametrize("enum", EXPECTED_CODES)
def test_member_is_found_by_its_code(enum: type[StrEnum]) -> None:
    for member in enum:
        assert enum(member.value) is member


@pytest.mark.parametrize("enum", EXPECTED_CODES)
def test_unknown_code_is_rejected(enum: type[StrEnum]) -> None:
    with pytest.raises(ValueError, match="not a valid"):
        enum("unknown")
