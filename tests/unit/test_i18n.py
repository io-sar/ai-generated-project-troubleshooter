from enum import StrEnum
from pathlib import Path
from typing import Any

import pytest
import yaml

import troubleshooter.i18n
from troubleshooter.domain import codes
from troubleshooter.i18n import keys, t

CATALOG_DIR = Path(troubleshooter.i18n.__file__).parent

CODE_SECTIONS: dict[str, type[StrEnum]] = {
    "project_type": codes.ProjectType,
    "dimension": codes.Dimension,
    "health_label": codes.HealthLabel,
    "escalation": codes.EscalationLevel,
    "raci": codes.RaciCode,
    "input_classification": codes.InputClassification,
    "badge": codes.ReportSource,
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


class _DuplicateKeyLoader(yaml.SafeLoader):
    """Fails on a repeated key, which plain YAML loading silently overwrites."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        seen: set[Any] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            assert key not in seen, f"duplicate key {key!r} on line {key_node.start_mark.line + 1}"
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


@pytest.mark.parametrize("catalog", sorted(CATALOG_DIR.glob("*.yaml")), ids=lambda p: p.name)
def test_catalog_has_no_duplicate_keys(catalog: Path) -> None:
    yaml.load(catalog.read_text(encoding="utf-8"), Loader=_DuplicateKeyLoader)  # noqa: S506


def test_code_translates_by_value() -> None:
    assert t(f"health_label.{codes.HealthLabel.AT_RISK}") == "At Risk"
    assert t(f"raci.{codes.RaciCode.ACCOUNTABLE}") == "Accountable"
