from enum import StrEnum

import pytest

from troubleshooter.domain import codes
from troubleshooter.i18n import keys, t

CODE_SECTIONS: dict[str, type[StrEnum]] = {
    "project_type": codes.ProjectType,
    "dimension": codes.Dimension,
    "health_label": codes.HealthLabel,
    "escalation": codes.EscalationLevel,
    "raci": codes.RaciCode,
    "input_classification": codes.InputClassification,
}


def test_returns_text_for_a_key() -> None:
    assert t("app.title") == "AI Project Troubleshooter"


def test_fills_placeholders() -> None:
    assert t("app.version", version="1.2.3") == "Version 1.2.3"


def test_missing_key_names_the_key() -> None:
    with pytest.raises(KeyError, match=r"app\.nope"):
        t("app.nope")


def test_section_key_is_not_text() -> None:
    with pytest.raises(KeyError):
        t("app")


def test_missing_placeholder_fails() -> None:
    with pytest.raises(KeyError, match="version"):
        t("app.version", other="x")


def test_forgotten_placeholder_fails_instead_of_showing_braces() -> None:
    with pytest.raises(KeyError, match="version"):
        t("app.version")


@pytest.mark.parametrize("section", CODE_SECTIONS)
def test_every_code_has_display_text(section: str) -> None:
    missing = {code.value for code in CODE_SECTIONS[section]} - {
        key.removeprefix(f"{section}.") for key in keys() if key.startswith(f"{section}.")
    }
    assert not missing


def test_code_translates_by_value() -> None:
    assert t(f"health_label.{codes.HealthLabel.AT_RISK}") == "At Risk"
    assert t(f"raci.{codes.RaciCode.ACCOUNTABLE}") == "Accountable"
